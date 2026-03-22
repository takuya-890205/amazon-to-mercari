"""Amazon購入履歴をPlaywrightで開き、商品選択でStreamlitに戻すランナー

Streamlitのサブプロセスとして起動される。
商品の「出品する」ボタンをクリックすると、Playwrightのrouteでインターセプトし、
ユーザーのデフォルトブラウザでStreamlitアプリを開く。
"""

import os
import sys
import shutil
import time
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

AMAZON_ORDER_HISTORY_URL = "https://www.amazon.co.jp/gp/your-account/order-history"

# 選択通知用のプレフィックス（document.titleに書き込む）
SELECTED_PREFIX = "MERCARI_SELECT:"

# 商品リンクの横に「出品する」ボタンを追加するJS
INJECT_JS = """
(() => {
	const SELECTED_PREFIX = '__SELECTED_PREFIX__';

	function extractProductUrl(href) {
		const dpMatch = href.match(/\\/dp\\/([A-Z0-9]{10})/);
		if (dpMatch) return 'https://www.amazon.co.jp/dp/' + dpMatch[1];
		const gpMatch = href.match(/\\/gp\\/product\\/([A-Z0-9]{10})/);
		if (gpMatch) return 'https://www.amazon.co.jp/dp/' + gpMatch[1];
		return null;
	}

	function addOverlay(link, productUrl) {
		if (link.dataset.mercariBtn) return;
		link.dataset.mercariBtn = '1';

		// 画像リンクにはボタンを付けない
		if (link.querySelector('img')) return;

		// テキストが短すぎるリンクもスキップ
		if (link.textContent.trim().length < 5) return;

		const btn = document.createElement('span');
		btn.textContent = '出品';
		btn.style.cssText = `
			display: inline-block; margin-left: 8px; vertical-align: middle;
			background: #FF5252; color: white; padding: 2px 8px;
			border-radius: 4px; font-size: 11px; font-weight: bold;
			cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.3);
			transition: background 0.2s; white-space: nowrap;
		`;
		btn.addEventListener('mouseenter', () => btn.style.background = '#D32F2F');
		btn.addEventListener('mouseleave', () => btn.style.background = '#FF5252');
		btn.addEventListener('click', (e) => {
			e.preventDefault();
			e.stopPropagation();
			btn.textContent = '送信済み';
			btn.style.background = '#4CAF50';
			// タイトルにURLを書き込んでPython側に通知
			document.title = SELECTED_PREFIX + productUrl;
		});
		link.after(btn);
	}

	function processLinks() {
		document.querySelectorAll('a[href*="/dp/"], a[href*="/gp/product/"]').forEach(link => {
			const productUrl = extractProductUrl(link.getAttribute('href'));
			if (productUrl) addOverlay(link, productUrl);
		});
	}

	function init() {
		if (!location.hostname.includes('amazon.co.jp')) return;
		processLinks();
		const observer = new MutationObserver(() => processLinks());
		observer.observe(document.body, { childList: true, subtree: true });
	}

	if (document.body) {
		init();
	} else {
		document.addEventListener('DOMContentLoaded', init);
	}
})();
"""


def main():
	streamlit_port = int(sys.argv[1]) if len(sys.argv) > 1 else 8501
	streamlit_url = f"http://localhost:{streamlit_port}"
	js_code = INJECT_JS.replace("__SELECTED_PREFIX__", SELECTED_PREFIX)

	from playwright.sync_api import sync_playwright

	profile_dir = os.path.join(
		os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
		"chrome_profile_pw",
	)
	os.makedirs(profile_dir, exist_ok=True)

	pw = sync_playwright().start()

	# Chrome実行パスを探す
	chrome_path = None
	if sys.platform == "win32":
		for name in ["chrome.exe", "chrome"]:
			found = shutil.which(name)
			if found:
				chrome_path = found
				break
		if not chrome_path:
			default = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
			if os.path.exists(default):
				chrome_path = default

	kwargs = {
		"user_data_dir": profile_dir,
		"headless": False,
		"args": [
			"--disable-blink-features=AutomationControlled",
			"--no-sandbox",
		],
		"viewport": {"width": 1280, "height": 900},
		"timeout": 30000,
	}
	if chrome_path:
		kwargs["executable_path"] = chrome_path

	try:
		context = pw.chromium.launch_persistent_context(**kwargs)
	except Exception:
		chromium_profile = os.path.join(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
			"chromium_profile_pw",
		)
		os.makedirs(chromium_profile, exist_ok=True)
		context = pw.chromium.launch_persistent_context(
			user_data_dir=chromium_profile,
			headless=False,
			viewport={"width": 1280, "height": 900},
			timeout=30000,
		)

	page = context.pages[0] if context.pages else context.new_page()

	# ページ読み込み時に自動でJSを注入
	context.add_init_script(js_code)

	page.goto(AMAZON_ORDER_HISTORY_URL, wait_until="domcontentloaded", timeout=60000)
	# 初回は手動でも注入
	try:
		page.evaluate(js_code)
	except Exception:
		pass

	# タイトルの変化を監視して商品選択を検知
	selected_url = None
	while selected_url is None:
		try:
			# ページ遷移中はtitle()が失敗するのでリトライ
			try:
				title = page.title()
			except Exception:
				time.sleep(0.5)
				continue
			if title.startswith(SELECTED_PREFIX):
				selected_url = title[len(SELECTED_PREFIX):]
				break
			time.sleep(0.3)
		except KeyboardInterrupt:
			break
		except Exception:
			# コンテキスト自体が閉じられたかチェック
			try:
				page.evaluate("1")
				time.sleep(0.5)
			except Exception:
				# ブラウザが本当に閉じられた
				break

	# 商品が選択された場合、ファイルにURLを書き込む（Streamlit側がポーリングで検知）
	if selected_url:
		data_dir = os.path.join(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
			"data",
		)
		os.makedirs(data_dir, exist_ok=True)
		url_file = os.path.join(data_dir, ".selected_amazon_url")
		with open(url_file, "w", encoding="utf-8") as f:
			f.write(selected_url)

	# クリーンアップ
	try:
		context.close()
	except Exception:
		pass
	pw.stop()


if __name__ == "__main__":
	main()

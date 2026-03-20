"""Playwrightでメルカリ出品フォームに自動入力"""

import os
import sys
import subprocess
import time
from pathlib import Path

from scraper.product_data import MercariDraft

# メルカリ出品ページURL
MERCARI_SELL_URL = "https://jp.mercari.com/sell/create"

# 待機時間設定
WAIT_TIMEOUT = 15000  # ms
INPUT_DELAY = 0.5


def _is_wsl() -> bool:
	"""WSL環境かどうかを判定"""
	# Windowsネイティブなら確実にWSLではない
	if sys.platform == "win32":
		return False
	try:
		with open("/proc/version", "r") as f:
			return "microsoft" in f.read().lower()
	except Exception:
		return False


def _find_windows_chrome() -> str:
	"""Windows側Chromeのパスを探す"""
	paths = [
		"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
		"/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
	]
	for p in paths:
		if os.path.exists(p):
			return p
	return ""


class MercariFiller:
	"""メルカリ出品フォームに商品情報を自動入力（Playwright版）"""

	def __init__(self, on_progress=None):
		self.page = None
		self.browser = None
		self.context = None
		self.playwright = None
		self._on_progress = on_progress or (lambda msg: None)

	def _progress(self, message: str) -> None:
		print(message)
		self._on_progress(message)

	def _launch_browser(self):
		from playwright.sync_api import sync_playwright

		profile_dir = os.path.join(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
			"chrome_profile_pw",
		)
		os.makedirs(profile_dir, exist_ok=True)

		self.playwright = sync_playwright().start()

		if _is_wsl():
			# WSL環境: CDP接続方式でWindows Chromeに接続
			self._launch_wsl_chrome(profile_dir)
		elif sys.platform == "win32":
			# Windows環境: persistent_contextで直接起動
			self._launch_windows_chrome(profile_dir)
		else:
			# Linux/Mac: Playwright内蔵Chromiumを使用
			self._launch_builtin_chromium()

	def _launch_windows_chrome(self, profile_dir: str):
		"""Windows環境: persistent_contextで起動"""
		chrome_path = None
		import shutil
		for name in ["chrome.exe", "chrome"]:
			found = shutil.which(name)
			if found:
				chrome_path = found
				break
		if not chrome_path:
			# デフォルトパス
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
			self.context = self.playwright.chromium.launch_persistent_context(**kwargs)
			self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
		except Exception as e:
			self._progress(f"  Chrome起動失敗（{e}）、内蔵Chromiumで再試行...")
			# Chromeがロック中等の場合、内蔵Chromiumにフォールバック
			self._launch_builtin_chromium()

	def _launch_wsl_chrome(self, profile_dir: str):
		"""WSL環境: Windows Chromeを--remote-debugging-portで起動しCDP接続"""
		chrome_path = _find_windows_chrome()
		if not chrome_path:
			raise RuntimeError("Windows側のChromeが見つかりません")

		# Windowsパスに変換
		win_profile = subprocess.check_output(
			["wslpath", "-w", profile_dir], text=True
		).strip()

		port = 9222
		# 既に起動済みかチェック
		import urllib.request
		try:
			urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
			already_running = True
		except Exception:
			already_running = False

		if not already_running:
			subprocess.Popen(
				[
					chrome_path,
					f"--remote-debugging-port={port}",
					f"--user-data-dir={win_profile}",
					"--disable-blink-features=AutomationControlled",
					"--no-first-run",
					"--no-default-browser-check",
					"about:blank",
				],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
			)
			# 起動待機
			for _ in range(10):
				time.sleep(1)
				try:
					urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
					break
				except Exception:
					continue
			else:
				raise RuntimeError(
					"Chrome のデバッグポートに接続できません。\n"
					"Chromeを全て閉じてから再試行してください。"
				)

		self.browser = self.playwright.chromium.connect_over_cdp(
			f"http://localhost:{port}", timeout=15000
		)
		self.context = self.browser.contexts[0]
		self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

	def _launch_builtin_chromium(self):
		"""Playwright内蔵Chromiumで起動（プロファイル付き）"""
		profile_dir = os.path.join(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
			"chromium_profile_pw",
		)
		os.makedirs(profile_dir, exist_ok=True)

		self.context = self.playwright.chromium.launch_persistent_context(
			user_data_dir=profile_dir,
			headless=False,
			args=[
				"--disable-blink-features=AutomationControlled",
				"--no-sandbox",
			],
			viewport={"width": 1280, "height": 900},
			timeout=30000,
		)
		self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

	def fill_listing(self, draft: MercariDraft, wait_for_close: bool = True) -> None:
		"""メルカリ出品フォームに情報を入力"""
		try:
			self._progress("ブラウザを起動中...")
			self._launch_browser()

			self._progress("メルカリ出品ページを開いています...")
			self.page.goto(MERCARI_SELL_URL, wait_until="domcontentloaded", timeout=30000)
			try:
				self.page.wait_for_load_state("networkidle", timeout=15000)
			except Exception:
				pass
			time.sleep(2)
			self._progress("メルカリ出品ページを読み込みました")

			# ログイン確認
			if "login" in self.page.url.lower():
				self._progress("ログインを待機中...（ブラウザでログインしてください）")
				for _ in range(120):
					time.sleep(1)
					if "login" not in self.page.url.lower():
						break
				time.sleep(2)

			# AI自動入力トグルをOFF
			self._disable_ai_assist()

			# 画像アップロード
			if draft.image_paths:
				self._progress(f"画像をアップロード中...（{len(draft.image_paths)}枚）")
				self._upload_images(draft.image_paths)

			# タイトル入力
			self._progress("タイトルを入力中...")
			self._fill_text_field(
				'input[name="name"], input[data-testid="product-name"]',
				draft.title,
			)

			# 商品の状態選択
			if draft.condition:
				self._progress(f"商品の状態を選択中...（{draft.condition}）")
				self._select_condition(draft.condition)

			# 説明文入力
			self._progress("説明文を入力中...")
			self._fill_text_field(
				'textarea[name="description"], textarea[data-testid="product-description"]',
				draft.description,
			)

			# 配送料の負担
			self._progress("配送設定を入力中...")
			self._select_dropdown("shippingPayer", draft.shipping_payer)

			# 配送の方法
			if draft.shipping_method:
				self._select_shipping_method(draft.shipping_method)

			# 発送元の地域
			self._select_dropdown("shippingFromArea", draft.shipping_from)

			# 発送までの日数
			self._select_dropdown("shippingDuration", draft.shipping_days)

			# 価格入力
			self._progress("価格を入力中...")
			self._fill_text_field(
				'input[name="price"], input[data-testid="product-price"]',
				str(draft.price),
			)

			self._progress("自動入力が完了しました！内容を確認して出品してください。")

			if wait_for_close:
				print("ブラウザを閉じるまでこのまま待機します...")
				input("Enterキーを押すとブラウザを閉じます...")

		except Exception as e:
			print(f"自動入力エラー: {e}")
			raise
		finally:
			if wait_for_close:
				self._cleanup()

	def _cleanup(self):
		"""ブラウザリソースを解放"""
		try:
			if self.context and not self.browser:
				# persistent_contextの場合はcontextを閉じる
				self.context.close()
		except Exception:
			pass
		try:
			if self.browser:
				self.browser.close()
		except Exception:
			pass
		try:
			if self.playwright:
				self.playwright.stop()
		except Exception:
			pass

	def _disable_ai_assist(self) -> None:
		"""「商品名と説明文を自動入力」トグルをOFFにする"""
		try:
			result = self.page.evaluate("""
				() => {
					const allEls = document.querySelectorAll('input[type="checkbox"], input[role="switch"], [role="switch"]');
					for (const el of allEls) {
						const rect = el.getBoundingClientRect();
						if (rect.width > 0 && rect.height > 0) {
							if (el.checked || el.getAttribute('aria-checked') === 'true') {
								el.click();
								return true;
							}
						}
					}
					return false;
				}
			""")
			if result:
				time.sleep(1)
				self._progress("  AI自動入力トグルをOFFにしました")
		except Exception:
			pass

	def _upload_images(self, image_paths: list[str]) -> None:
		"""画像をアップロード"""
		try:
			file_input = self.page.query_selector('input[type="file"]')
			if file_input:
				absolute_paths = [
					str(Path(p).resolve()) for p in image_paths
					if Path(p).exists()
				]
				if absolute_paths:
					file_input.set_input_files(absolute_paths)
					time.sleep(3)
					self._progress(f"  画像 {len(absolute_paths)}枚をアップロードしました")
					self._close_image_modal()
			else:
				self._progress("  画像アップロード要素が見つかりませんでした")
		except Exception as e:
			self._progress(f"  画像アップロードエラー: {e}")

	def _close_image_modal(self) -> None:
		"""画像アップロード後のモーダルを処理"""
		try:
			next_btn = self.page.wait_for_selector("button:has-text('次へ')", timeout=5000)
			if next_btn:
				next_btn.click()
				self._progress("  画像モーダルを閉じました")
				time.sleep(2)
		except Exception:
			pass

		try:
			time.sleep(1)
			skip_btn = self.page.query_selector("text=スキップ")
			if skip_btn and skip_btn.is_visible():
				skip_btn.click()
				self._progress("  AI出品サポートをスキップしました")
				time.sleep(2)
		except Exception:
			pass

	def _fill_text_field(self, selector: str, value: str) -> None:
		"""テキストフィールドに値を入力"""
		selectors = [s.strip() for s in selector.split(",")]
		for sel in selectors:
			try:
				el = self.page.wait_for_selector(sel, timeout=WAIT_TIMEOUT)
				if el:
					el.click()
					time.sleep(0.2)
					el.fill(value)
					time.sleep(INPUT_DELAY)
					return
			except Exception:
				continue
		print(f"  入力エラー: {selector}")

	def _select_condition(self, condition: str) -> None:
		"""商品の状態を選択"""
		try:
			# 商品の状態リンクを探す（複数のセレクタで試行）
			cond_link = None
			for sel in [
				'[data-testid="item-condition"] a',
				"a:has-text('商品の状態を選択する')",
				"a:has-text('商品の状態')",
				"text=商品の状態を選択する",
			]:
				cond_link = self.page.query_selector(sel)
				if cond_link:
					break

			if not cond_link:
				self._progress("  商品の状態リンクが見つかりません（スキップ）")
				return

			cond_link.scroll_into_view_if_needed()
			time.sleep(0.3)
			cond_link.click()
			time.sleep(3)

			# 選択肢を探す（複数のセレクタパターンで試行）
			found = False
			for link_sel in [
				'a[href*="sell/conditions"]',
				'a[href*="condition"]',
				'li a',
				'[role="radio"]',
				'[role="option"]',
				'label',
			]:
				links = self.page.query_selector_all(link_sel)
				for link in links:
					link_text = (link.text_content() or "").strip()
					if condition in link_text or link_text in condition:
						link.scroll_into_view_if_needed()
						time.sleep(0.3)
						link.click()
						self._wait_for_sell_create(10)
						self._progress(f"  商品の状態を選択しました: {condition}")
						found = True
						break
				if found:
					break

			if not found:
				# デバッグ用スクリーンショット保存
				try:
					self.page.screenshot(path="debug_condition_select.png")
				except Exception:
					pass
				self._progress(f"  商品の状態「{condition}」が見つかりません（スキップ）")
				# 戻るボタンまたはブラウザバックで出品ページに戻る
				back_btn = self.page.query_selector("button:has-text('戻る')")
				if back_btn:
					back_btn.click()
				else:
					self.page.go_back()
				self._wait_for_sell_create(10)
		except Exception as e:
			self._progress(f"  商品の状態選択エラー: {e}（スキップ）")

	def _select_dropdown(self, name: str, value: str) -> None:
		"""select要素またはカスタムドロップダウンから値を選択"""
		if not value:
			return

		# 表示名マッピング（name属性 → 画面上のラベル）
		label_map = {
			"shippingPayer": "配送料の負担",
			"shippingFromArea": "発送元の地域",
			"shippingDuration": "発送までの日数",
		}
		display_label = label_map.get(name, name)

		try:
			# 方法1: 標準の<select>要素
			select_el = self.page.query_selector(f'select[name="{name}"]')
			if select_el:
				select_el.scroll_into_view_if_needed()
				time.sleep(0.3)
				options = self.page.query_selector_all(f'select[name="{name}"] option')
				for opt in options:
					opt_text = opt.text_content().strip()
					if opt_text == value or value in opt_text:
						select_el.select_option(label=opt_text)
						time.sleep(INPUT_DELAY)
						self._progress(f"  {display_label} を選択しました: {opt_text}")
						return
				self._progress(f"  {display_label} の選択肢「{value}」が見つかりませんでした")
				return

			# 方法2: data-testid付きのリンク/ボタン型ドロップダウン
			trigger = None
			for sel in [
				f'[data-testid="{name}"] a',
				f'[data-testid="{name}"] button',
				f'[data-testid="{name}"]',
				f"a:has-text('{display_label}')",
				f"button:has-text('{display_label}')",
			]:
				trigger = self.page.query_selector(sel)
				if trigger:
					break

			# ラベルテキストから探す
			if not trigger:
				all_elements = self.page.query_selector_all("a, button, [role='button']")
				for el in all_elements:
					text = (el.text_content() or "").strip()
					if display_label in text and len(text) < 50:
						trigger = el
						break

			if trigger:
				trigger.scroll_into_view_if_needed()
				time.sleep(0.3)
				trigger.click()
				time.sleep(2)

				# 選択肢を探す
				found = False
				for opt_sel in [
					"a", "li a", "li", "[role='option']",
					"[role='radio']", "label", "button",
				]:
					items = self.page.query_selector_all(opt_sel)
					for item in items:
						item_text = (item.text_content() or "").strip()
						if item_text == value or (value in item_text and len(item_text) < 30):
							item.scroll_into_view_if_needed()
							time.sleep(0.3)
							item.click()
							time.sleep(1)
							self._progress(f"  {display_label} を選択しました: {value}")
							found = True
							break
					if found:
						break

				if not found:
					self._progress(f"  {display_label}「{value}」が見つかりませんでした（スキップ）")
					# 出品ページに戻る
					if "sell/create" not in self.page.url:
						self.page.go_back()
						self._wait_for_sell_create(5)
			else:
				self._progress(f"  {display_label} の入力要素が見つかりません（スキップ）")
		except Exception as e:
			self._progress(f"  {display_label} 選択エラー: {e}（スキップ）")

	def _select_shipping_method(self, method: str) -> None:
		"""配送の方法を選択"""
		try:
			link = self.page.query_selector('[data-testid="shipping-method-link"] a')
			if not link:
				link = self.page.query_selector("a:has-text('配送の方法を選択する')")
			if link:
				link.scroll_into_view_if_needed()
				time.sleep(0.3)
				link.click()
				time.sleep(2)

				labels = self.page.query_selector_all("label, [role='radio']")
				for label in labels:
					text = label.text_content().strip()
					if method in text:
						label.scroll_into_view_if_needed()
						time.sleep(0.3)
						label.click()
						self._progress(f"  配送方法「{text.split(chr(10))[0]}」を選択")
						break

				time.sleep(1)
				self._click_submit_button("更新する")
		except Exception as e:
			self._progress(f"  配送の方法選択エラー: {e}")

	def _click_submit_button(self, text: str) -> None:
		"""送信ボタンをクリック"""
		try:
			self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
			time.sleep(1)
			btn = self.page.query_selector(f"button:has-text('{text}')")
			if btn and btn.is_visible():
				btn.click()
				self._progress(f"  「{text}」をクリックしました")
			self._wait_for_sell_create(10)
		except Exception as e:
			self._progress(f"  ボタンクリックエラー: {e}")

	def _wait_for_sell_create(self, timeout: int = 30) -> bool:
		"""出品フォームに戻るまで待機"""
		for _ in range(timeout):
			time.sleep(1)
			if "sell/create" in self.page.url:
				time.sleep(1)
				return True
		return False

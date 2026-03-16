"""Playwrightでメルカリ出品フォームに自動入力"""

import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from scraper.product_data import MercariDraft
from utils.browser_overlay import show_status, hide_status

# メルカリ出品ページURL
MERCARI_SELL_URL = "https://jp.mercari.com/sell/create"

# 待機時間設定
WAIT_TIMEOUT = 15000  # ms
INPUT_DELAY = 0.5

# Windows側Chromeのパス候補
_CHROME_PATHS = [
	"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
	"/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
]


def _find_chrome() -> str:
	for p in _CHROME_PATHS:
		if os.path.exists(p):
			return p
	raise FileNotFoundError("Windows側のChromeが見つかりません")


class MercariFiller:
	"""メルカリ出品フォームに商品情報を自動入力（Playwright版）"""

	def __init__(self, on_progress=None):
		self.page = None
		self.browser = None
		self.playwright = None
		self._on_progress = on_progress or (lambda msg: None)

	def _progress(self, message: str) -> None:
		print(message)
		self._on_progress(message)
		if self.page:
			show_status(self.page, message)

	def _launch_browser(self):
		chrome_path = _find_chrome()
		profile_dir = os.path.join(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
			"chrome_profile_pw",
		)
		os.makedirs(profile_dir, exist_ok=True)

		self.playwright = sync_playwright().start()
		context = self.playwright.chromium.launch_persistent_context(
			user_data_dir=profile_dir,
			executable_path=chrome_path,
			headless=False,
			args=[
				"--disable-blink-features=AutomationControlled",
				"--no-sandbox",
			],
			viewport={"width": 1280, "height": 900},
		)
		self.browser = context
		self.page = context.pages[0] if context.pages else context.new_page()

	def fill_listing(self, draft: MercariDraft, wait_for_close: bool = True) -> None:
		"""メルカリ出品フォームに情報を入力"""
		try:
			self._launch_browser()

			self.page.goto(MERCARI_SELL_URL)
			self.page.wait_for_load_state("networkidle")
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
				if self.browser:
					self.browser.close()
				if self.playwright:
					self.playwright.stop()

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
		# 「次へ」ボタン
		try:
			next_btn = self.page.wait_for_selector("button:has-text('次へ')", timeout=5000)
			if next_btn:
				next_btn.click()
				self._progress("  画像モーダルを閉じました")
				time.sleep(2)
		except Exception:
			pass

		# AI出品サポートの「スキップ」
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
			# 「商品の状態を選択する」リンクをクリック
			cond_link = self.page.query_selector('[data-testid="item-condition"] a')
			if not cond_link:
				cond_link = self.page.query_selector("a:has-text('商品の状態を選択する')")
			if cond_link:
				cond_link.scroll_into_view_if_needed()
				time.sleep(0.3)
				cond_link.click()
				time.sleep(2)

				# 状態名を含むリンクをクリック
				links = self.page.query_selector_all('a[href*="sell/conditions"]')
				for link in links:
					link_text = link.text_content().strip()
					if condition in link_text or link_text in condition:
						link.scroll_into_view_if_needed()
						time.sleep(0.3)
						link.click()
						self._wait_for_sell_create(10)
						print(f"  商品の状態を選択しました: {condition}")
						return
				print(f"  商品の状態「{condition}」が見つかりませんでした")
				self._wait_for_sell_create(60)
		except Exception as e:
			print(f"  商品の状態選択エラー: {e}")

	def _select_dropdown(self, name: str, value: str) -> None:
		"""select要素から値を選択"""
		if not value:
			return
		try:
			select_el = self.page.query_selector(f'select[name="{name}"]')
			if select_el:
				select_el.scroll_into_view_if_needed()
				time.sleep(0.3)
				# optionのテキストで選択
				options = self.page.query_selector_all(f'select[name="{name}"] option')
				for opt in options:
					opt_text = opt.text_content().strip()
					if opt_text == value or value in opt_text:
						select_el.select_option(label=opt_text)
						time.sleep(INPUT_DELAY)
						print(f"  {name} を選択しました: {opt_text}")
						return
				print(f"  {name} の選択肢「{value}」が見つかりませんでした")
		except Exception as e:
			print(f"  {name} 選択エラー: {e}")

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

				# ラジオボタンのラベルから選択
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

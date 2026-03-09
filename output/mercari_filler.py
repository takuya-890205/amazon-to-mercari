"""Seleniumでメルカリ出品フォームに自動入力"""

import os
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from scraper.product_data import MercariDraft
from utils.browser_overlay import show_status, hide_status

# メルカリ出品ページURL
MERCARI_SELL_URL = "https://jp.mercari.com/sell/create"

# 待機時間設定
WAIT_TIMEOUT = 15
INPUT_DELAY = 0.5


class MercariFiller:
	"""メルカリ出品フォームに商品情報を自動入力"""

	def __init__(self, chrome_profile: str | None = None, on_progress=None):
		"""初期化。ユーザーのChromeプロファイルを使用してログイン状態を維持

		Args:
			chrome_profile: Chromeプロファイルパス
			on_progress: 進捗コールバック関数 (message: str) -> None
		"""
		self.chrome_profile = chrome_profile or self._get_default_profile()
		self.driver = None
		self._on_progress = on_progress or (lambda msg: None)

	def _progress(self, message: str) -> None:
		"""進捗を通知（ブラウザ上にも表示）"""
		print(message)
		self._on_progress(message)
		if self.driver:
			show_status(self.driver, message)

	def _get_default_profile(self) -> str:
		"""デフォルトのChromeプロファイルパスを取得"""
		local_app_data = os.environ.get("LOCALAPPDATA", "")
		return os.path.join(local_app_data, "Google", "Chrome", "User Data")

	def _create_driver(self) -> webdriver.Chrome:
		"""Chromeドライバーを作成"""
		options = Options()
		# 専用プロファイルディレクトリを使用（メインChromeとの競合を回避）
		# メルカリのログイン状態は初回ログイン後このプロファイルに保存される
		profile_dir = os.path.join(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
			"chrome_profile",
		)
		os.makedirs(profile_dir, exist_ok=True)
		options.add_argument(f"--user-data-dir={profile_dir}")
		# 自動化検出を無効化
		options.add_argument("--disable-blink-features=AutomationControlled")
		options.add_experimental_option("excludeSwitches", ["enable-automation"])
		options.add_experimental_option("useAutomationExtension", False)

		service = Service(ChromeDriverManager().install())
		driver = webdriver.Chrome(service=service, options=options)
		driver.maximize_window()
		return driver

	def fill_listing(self, draft: MercariDraft, wait_for_close: bool = True) -> None:
		"""メルカリ出品フォームに情報を入力

		Args:
			draft: メルカリ出品下書きデータ
			wait_for_close: Trueの場合はEnterキー待機後にブラウザを閉じる（CLI用）。
			                Falseの場合はブラウザを開いたまま返す（Streamlit用）。
		"""
		try:
			self.driver = self._create_driver()
			wait = WebDriverWait(self.driver, WAIT_TIMEOUT)

			# メルカリ出品ページを開く
			self.driver.get(MERCARI_SELL_URL)
			time.sleep(3)
			self._progress("メルカリ出品ページを読み込みました")

			# ログイン確認
			if "login" in self.driver.current_url.lower():
				self._progress("ログインを待機中...（ブラウザでログインしてください）")
				for _ in range(120):
					time.sleep(1)
					if "login" not in self.driver.current_url.lower():
						break
				time.sleep(2)

			# 「商品名と説明文を自動入力」トグルをOFFにする（AI出品サポートを無効化）
			self._disable_ai_assist()

			# 画像アップロード
			if draft.image_paths:
				self._progress(f"画像をアップロード中...（{len(draft.image_paths)}枚）")
				self._upload_images(draft.image_paths, wait)

			# タイトル入力
			self._progress("タイトルを入力中...")
			self._fill_text_field(
				wait,
				'input[name="name"], input[data-testid="product-name"]',
				draft.title,
			)

			# カテゴリー・ブランドは手動入力（自動選択の精度が低いためスキップ）

			# 商品の状態選択
			if draft.condition:
				self._progress(f"商品の状態を選択中...（{draft.condition}）")
				self._select_condition(draft.condition, wait)

			# 説明文入力
			self._progress("説明文を入力中...")
			self._fill_text_field(
				wait,
				'textarea[name="description"], textarea[data-testid="product-description"]',
				draft.description,
			)

			# 配送料の負担（select）
			self._progress("配送設定を入力中...")
			self._select_dropdown("shippingPayer", draft.shipping_payer)

			# 配送の方法（リンク遷移型）
			if draft.shipping_method:
				self._select_shipping_method(draft.shipping_method, wait)

			# 発送元の地域（select）
			self._select_dropdown("shippingFromArea", draft.shipping_from)

			# 発送までの日数（select）
			self._select_dropdown("shippingDuration", draft.shipping_days)

			# 価格入力
			self._progress("価格を入力中...")
			self._fill_text_field(
				wait,
				'input[name="price"], input[data-testid="product-price"]',
				str(draft.price),
			)

			self._progress("自動入力が完了しました！内容を確認して出品してください。")
			# 完了メッセージを5秒後に自動で消す
			if self.driver:
				from utils.browser_overlay import auto_hide_status
				auto_hide_status(self.driver, 5000)

			if wait_for_close:
				# CLI用: ユーザーが手動で確認・出品するまで待機
				print("ブラウザを閉じるまでこのまま待機します...")
				input("Enterキーを押すとブラウザを閉じます...")

		except Exception as e:
			print(f"自動入力エラー: {e}")
			raise
		finally:
			# wait_for_close=Falseの場合はブラウザを開いたままにする
			if wait_for_close and self.driver:
				self.driver.quit()

	def _click_by_text(self, text: str, tag: str = "*", timeout: int = 5) -> bool:
		"""指定テキストを含む要素をクリック（子孫テキストも検索）"""
		try:
			# contains(., ...) で子孫テキストも含めて検索
			xpath = f"//{tag}[contains(., '{text}')]"
			elements = WebDriverWait(self.driver, timeout).until(
				EC.presence_of_all_elements_located((By.XPATH, xpath))
			)
			# 最も深い（テキストに最も近い）クリック可能な要素を選択
			best = None
			for el in elements:
				try:
					if el.is_displayed() and el.is_enabled():
						# より具体的な要素を優先（innerTextが短い＝より深い）
						if best is None or len(el.text.strip()) <= len(best.text.strip()):
							best = el
				except Exception:
					continue
			if best:
				self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", best)
				time.sleep(0.3)
				best.click()
				time.sleep(INPUT_DELAY)
				return True
			return False
		except Exception:
			return False

	def _select_category(self, categories: list[str], wait: WebDriverWait) -> None:
		"""カテゴリーを検索ボックスで選択（検索→候補クリック方式）"""
		try:
			# 「カテゴリーを選択する」リンクをクリック → /sell/categories に遷移
			try:
				cat_link = self.driver.find_element(
					By.CSS_SELECTOR, '[data-testid="category-link"] a'
				)
				self.driver.execute_script(
					"arguments[0].scrollIntoView({block: 'center'});", cat_link
				)
				time.sleep(0.3)
				cat_link.click()
			except Exception:
				if not self._click_by_text("カテゴリーを選択する", tag="a"):
					print("  カテゴリー選択ボタンが見つかりませんでした")
					return

			# カテゴリーページの読み込みを待機
			time.sleep(2)

			# 検索ボックスを見つける
			try:
				search_input = WebDriverWait(self.driver, 10).until(
					EC.presence_of_element_located(
						(By.CSS_SELECTOR, "input.merInputNode")
					)
				)
			except Exception:
				print("  カテゴリー検索ボックスが見つかりませんでした")
				self._wait_for_sell_create(60)
				return

			# まずAIサジェスト（「こちらのカテゴリーですか？」）をチェック
			selected = False
			ai_candidates = self._find_category_candidates()
			if ai_candidates:
				self._progress(f"  AIサジェスト {len(ai_candidates)}件を検出")
				target = ai_candidates[0]
				candidate_text = target.text.strip().split("\n")[0]
				self._progress(f"  候補「{candidate_text}」を選択中...")
				self.driver.execute_script(
					"arguments[0].scrollIntoView({block: 'center'});", target
				)
				time.sleep(0.3)
				self.driver.execute_script("arguments[0].click();", target)
				selected = True

			# AIサジェストがなければ検索ボックスで検索
			if not selected:
				search_terms = [c.strip() for c in reversed(categories) if c.strip()]
				for term in search_terms:
					# 確実にフィールドをクリア
					search_input.click()
					time.sleep(0.2)
					search_input.send_keys(Keys.CONTROL + "a")
					time.sleep(0.1)
					search_input.send_keys(Keys.DELETE)
					time.sleep(0.3)

					search_input.send_keys(term)
					self._progress(f"  「{term}」で検索中...")
					time.sleep(2)

					candidates = self._find_category_candidates()
					if candidates:
						target = candidates[0]
						candidate_text = target.text.strip().split("\n")[0]
						self._progress(f"  候補「{candidate_text}」を選択中...")
						self.driver.execute_script(
							"arguments[0].scrollIntoView({block: 'center'});", target
						)
						time.sleep(0.3)
						self.driver.execute_script("arguments[0].click();", target)
						selected = True
						break

			# 出品フォームに戻るまで待機
			if selected:
				self._wait_for_sell_create(10)

			if "sell/create" in self.driver.current_url:
				print(f"  カテゴリーを選択しました: {' > '.join(categories)}")
			else:
				print("  カテゴリーの自動選択に失敗しました。手動で選択してください。")
				self._wait_for_sell_create(60)
		except Exception as e:
			print(f"  カテゴリー選択エラー: {e}")

	def _wait_for_sell_create(self, timeout: int = 30) -> bool:
		"""出品フォーム（/sell/create）に戻るまで待機"""
		for _ in range(timeout):
			time.sleep(1)
			if "sell/create" in self.driver.current_url:
				time.sleep(1)
				return True
		return False

	def _find_category_candidates(self) -> list:
		"""カテゴリー候補要素を取得（AIサジェスト + 検索結果）"""
		# data-testid="merActionRow" の候補
		candidates = self.driver.find_elements(
			By.CSS_SELECTOR, '[data-testid="merActionRow"]'
		)
		if not candidates:
			# フォールバック: sell/createへのリンクで候補テキストがあるもの
			candidates = [
				a for a in self.driver.find_elements(By.CSS_SELECTOR, "a")
				if "sell/create" in (a.get_attribute("href") or "")
				and a.text.strip()
				and a.is_displayed()
			]
		return candidates

	def _select_brand(self, brand: str, wait: WebDriverWait) -> None:
		"""ブランドを検索・選択"""
		# ブランド名のクリーニング（Amazonのテキストアーティファクト除去）
		import re
		brand = re.sub(r"のストアを表示$", "", brand)
		brand = re.sub(r"^ストアを?訪問\s*", "", brand)
		brand = re.sub(r"^(ブランド|Brand)\s*[:：]\s*", "", brand)
		brand = brand.strip()
		if not brand:
			return
		try:
			# 「ブランドを選択する」リンクをクリック
			try:
				brand_link = self.driver.find_element(
					By.CSS_SELECTOR, '[data-testid="brand"] a, a[href*="sell/brands"]'
				)
				self.driver.execute_script(
					"arguments[0].scrollIntoView({block: 'center'});", brand_link
				)
				time.sleep(0.3)
				brand_link.click()
			except Exception:
				if not self._click_by_text("ブランド", tag="a"):
					self._progress("  ブランド選択ボタンが見つかりませんでした")
					return

			time.sleep(2)

			# 検索ボックスにブランド名を入力
			try:
				search_input = WebDriverWait(self.driver, 5).until(
					EC.presence_of_element_located(
						(By.CSS_SELECTOR, "input.merInputNode, input[placeholder*='ブランド']")
					)
				)
				search_input.click()
				time.sleep(0.2)
				search_input.send_keys(brand)
				self._progress(f"  「{brand}」で検索中...")
				time.sleep(2)

				# 検索候補から最初の一致をクリック
				candidates = self.driver.find_elements(
					By.CSS_SELECTOR, '[data-testid="merActionRow"]'
				)
				if not candidates:
					candidates = [
						a for a in self.driver.find_elements(By.CSS_SELECTOR, "a")
						if "sell/create" in (a.get_attribute("href") or "")
						and a.text.strip()
						and a.is_displayed()
					]

				if candidates:
					target = candidates[0]
					candidate_text = target.text.strip().split("\n")[0]
					self._progress(f"  ブランド候補「{candidate_text}」を選択")
					self.driver.execute_script("arguments[0].click();", target)
					self._wait_for_sell_create(10)
				else:
					self._progress(f"  ブランド「{brand}」の候補が見つかりませんでした")
					self._wait_for_sell_create(30)
			except Exception:
				self._progress("  ブランド検索ボックスが見つかりませんでした")
				self._wait_for_sell_create(30)
		except Exception as e:
			self._progress(f"  ブランド選択エラー: {e}")

	def _select_condition(self, condition: str, wait: WebDriverWait) -> None:
		"""商品の状態を選択（別ページ遷移型）"""
		try:
			# 「商品の状態を選択する」リンクをクリック → /sell/conditions に遷移
			try:
				cond_link = self.driver.find_element(
					By.CSS_SELECTOR, '[data-testid="item-condition"] a'
				)
				self.driver.execute_script(
					"arguments[0].scrollIntoView({block: 'center'});", cond_link
				)
				time.sleep(0.3)
				cond_link.click()
			except Exception:
				if not self._click_by_text("商品の状態を選択する", tag="a"):
					print("  商品の状態選択ボタンが見つかりませんでした")
					return

			time.sleep(2)

			# 状態名を含むリンクをクリック
			try:
				links = WebDriverWait(self.driver, 8).until(
					EC.presence_of_all_elements_located(
						(By.CSS_SELECTOR, 'a[href*="sell/conditions"]')
					)
				)
				clicked = False
				for link in links:
					link_text = link.text.strip()
					if condition in link_text or link_text in condition:
						self.driver.execute_script(
							"arguments[0].scrollIntoView({block: 'center'});", link
						)
						time.sleep(0.3)
						link.click()
						clicked = True
						break
				if clicked:
					# 出品フォームに戻るまで待機
					for _ in range(10):
						time.sleep(1)
						if "sell/create" in self.driver.current_url:
							break
					time.sleep(1)
					print(f"  商品の状態を選択しました: {condition}")
				else:
					print(f"  商品の状態「{condition}」が見つかりませんでした（手動で選択してください）")
					for _ in range(60):
						time.sleep(1)
						if "sell/create" in self.driver.current_url:
							break
			except Exception:
				# リンク形式ではない場合、テキストクリックを試行
				if self._click_by_text(condition, timeout=5):
					print(f"  商品の状態を選択しました: {condition}")
				else:
					print(f"  商品の状態「{condition}」が見つかりませんでした（手動で選択してください）")
		except Exception as e:
			print(f"  商品の状態選択エラー: {e}")

	def _select_dropdown(self, name: str, value: str) -> None:
		"""select要素から値を選択"""
		if not value:
			return
		try:
			select_el = self.driver.find_element(
				By.CSS_SELECTOR, f'select[name="{name}"]'
			)
			self.driver.execute_script(
				"arguments[0].scrollIntoView({block: 'center'});", select_el
			)
			time.sleep(0.3)
			# option要素からテキストが一致するものを選択
			options = select_el.find_elements(By.TAG_NAME, "option")
			for opt in options:
				opt_text = opt.text.strip()
				if opt_text == value or value in opt_text:
					opt.click()
					time.sleep(INPUT_DELAY)
					print(f"  {name} を選択しました: {opt_text}")
					return
			print(f"  {name} の選択肢「{value}」が見つかりませんでした")
		except Exception as e:
			print(f"  {name} 選択エラー: {e}")

	def _select_shipping_method(self, method: str, wait: WebDriverWait) -> None:
		"""配送の方法を選択（ラジオボタン + 更新ボタン方式）"""
		try:
			# 「配送の方法を選択する」リンクをクリック
			try:
				link = self.driver.find_element(
					By.CSS_SELECTOR, '[data-testid="shipping-method-link"] a'
				)
				self.driver.execute_script(
					"arguments[0].scrollIntoView({block: 'center'});", link
				)
				time.sleep(0.3)
				link.click()
			except Exception:
				if not self._click_by_text("配送の方法を選択する", tag="a"):
					self._progress("  配送の方法選択ボタンが見つかりませんでした")
					return

			time.sleep(2)

			# ラジオボタンから配送方法を選択
			selected = False
			# テキストを含む要素をクリック（ラジオボタンのラベル）
			all_els = self.driver.find_elements(By.CSS_SELECTOR, "label, [role='radio'], input[type='radio']")
			for el in all_els:
				try:
					text = el.text.strip()
					if method in text or text in method:
						self.driver.execute_script(
							"arguments[0].scrollIntoView({block: 'center'});", el
						)
						time.sleep(0.3)
						self.driver.execute_script("arguments[0].click();", el)
						selected = True
						self._progress(f"  配送方法「{text.split(chr(10))[0]}」を選択")
						break
				except Exception:
					continue

			# フォールバック: テキストマッチで探す
			if not selected:
				for el in self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{method}')]"):
					try:
						if el.is_displayed():
							self.driver.execute_script("arguments[0].click();", el)
							selected = True
							break
					except Exception:
						continue

			time.sleep(1)

			# 「更新する」ボタンをクリック（画面下部にあるのでスクロール）
			self._click_submit_button("更新する")
		except Exception as e:
			self._progress(f"  配送の方法選択エラー: {e}")

	def _click_submit_button(self, text: str) -> None:
		"""ページ下部の送信ボタン（更新する等）をクリックして出品フォームに戻る"""
		try:
			# ページ最下部にスクロール
			self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
			time.sleep(1)

			# JavaScriptで直接テキスト一致するボタン/リンクを探してクリック
			clicked = self.driver.execute_script(f"""
				const targetText = '{text}';
				// button, a, div, span 等すべてのクリック可能要素から探す
				const candidates = document.querySelectorAll('button, a, [role="button"], input[type="submit"]');
				for (const el of candidates) {{
					const elText = el.textContent.trim();
					if (elText === targetText || elText.includes(targetText)) {{
						const rect = el.getBoundingClientRect();
						if (rect.width > 0 && rect.height > 0) {{
							el.scrollIntoView({{block: 'center'}});
							el.click();
							return true;
						}}
					}}
				}}
				return false;
			""")

			if clicked:
				self._progress(f"  「{text}」をクリックしました")
			else:
				self._progress(f"  「{text}」ボタンが見つかりませんでした")

			self._wait_for_sell_create(10)
		except Exception as e:
			self._progress(f"  ボタンクリックエラー: {e}")

	def _disable_ai_assist(self) -> None:
		"""「商品名と説明文を自動入力」トグルをOFFにする"""
		try:
			# トグルのチェック状態を確認してOFFにする
			toggle = self.driver.execute_script("""
				// 「商品名と説明文を自動入力」テキスト付近のトグルを探す
				const allEls = document.querySelectorAll('input[type="checkbox"], input[role="switch"], [role="switch"]');
				for (const el of allEls) {
					const rect = el.getBoundingClientRect();
					if (rect.width > 0 && rect.height > 0) {
						// チェックされているトグルを返す
						if (el.checked || el.getAttribute('aria-checked') === 'true') {
							return el;
						}
					}
				}
				return null;
			""")
			if toggle:
				self.driver.execute_script("arguments[0].click();", toggle)
				time.sleep(1)
				self._progress("  AI自動入力トグルをOFFにしました")
			else:
				# テキストから探すフォールバック
				els = self.driver.find_elements(By.XPATH, "//*[contains(text(), '自動入力')]")
				for el in els:
					try:
						# 親要素や隣接要素からトグルを見つける
						parent = el.find_element(By.XPATH, "./ancestor::*[3]")
						switches = parent.find_elements(By.CSS_SELECTOR, '[role="switch"], input[type="checkbox"]')
						for sw in switches:
							if sw.is_displayed():
								self.driver.execute_script("arguments[0].click();", sw)
								time.sleep(1)
								self._progress("  AI自動入力トグルをOFFにしました")
								return
					except Exception:
						continue
		except Exception:
			pass

	def _upload_images(self, image_paths: list[str], wait: WebDriverWait) -> None:
		"""画像をアップロード"""
		try:
			# ファイル入力要素を探す
			file_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
			if file_inputs:
				file_input = file_inputs[0]
				# 複数画像を一度に送信
				absolute_paths = [
					str(Path(p).resolve()) for p in image_paths
					if Path(p).exists()
				]
				if absolute_paths:
					file_input.send_keys("\n".join(absolute_paths))
					time.sleep(3)
					self._progress(f"  画像 {len(absolute_paths)}枚をアップロードしました")

					# 画像プレビューモーダルの「次へ」ボタンを処理
					self._close_image_modal()
			else:
				self._progress("  画像アップロード要素が見つかりませんでした")
		except Exception as e:
			self._progress(f"  画像アップロードエラー: {e}")

	def _close_image_modal(self) -> None:
		"""画像アップロード後のモーダル群を処理"""
		# 1. 画像プレビューモーダルの「次へ」ボタン
		try:
			next_btn = WebDriverWait(self.driver, 5).until(
				EC.element_to_be_clickable(
					(By.XPATH, "//button[contains(text(), '次へ')]")
				)
			)
			next_btn.click()
			self._progress("  画像モーダルを閉じました")
			time.sleep(2)
		except Exception:
			pass

		# 2. 「AI出品サポート」ダイアログの「スキップ」or「×」で閉じる
		try:
			time.sleep(1)
			skipped = False
			# 表示されている要素から「スキップ」テキストを探す
			for el in self.driver.find_elements(By.XPATH, "//*[contains(text(), 'スキップ')]"):
				try:
					if el.is_displayed():
						self.driver.execute_script("arguments[0].click();", el)
						skipped = True
						break
				except Exception:
					continue

			# 見つからなければ「×」ボタン（モーダルの閉じるボタン）を試す
			if not skipped:
				for el in self.driver.find_elements(By.XPATH, "//*[contains(text(), '×')]"):
					try:
						if el.is_displayed():
							self.driver.execute_script("arguments[0].click();", el)
							skipped = True
							break
					except Exception:
						continue

			if skipped:
				self._progress("  AI出品サポートをスキップしました")
				time.sleep(2)
		except Exception:
			pass

	def _fill_text_field(
		self,
		wait: WebDriverWait,
		selector: str,
		value: str,
	) -> None:
		"""テキストフィールドに値を入力"""
		try:
			# 複数のセレクタを試行
			selectors = [s.strip() for s in selector.split(",")]
			element = None

			for sel in selectors:
				try:
					element = wait.until(
						EC.presence_of_element_located((By.CSS_SELECTOR, sel))
					)
					if element:
						break
				except Exception:
					continue

			if element:
				element.clear()
				time.sleep(INPUT_DELAY)
				element.send_keys(value)
				time.sleep(INPUT_DELAY)
		except Exception as e:
			print(f"  入力エラー ({selector}): {e}")

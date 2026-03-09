"""Amazon購入履歴からの商品取得"""

import os
import re
import time
from dataclasses import dataclass

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from utils.browser_overlay import show_status, hide_status


@dataclass
class OrderItem:
	"""購入履歴の1商品"""
	asin: str
	title: str
	price: int | None
	image_url: str
	order_date: str
	url: str


class OrderHistoryScraper:
	"""Amazon購入履歴スクレイパー（ブラウザ表示・ログイン対応）"""

	def __init__(self, on_progress=None):
		self.driver = None
		self._on_progress = on_progress or (lambda msg: None)

	def _progress(self, message: str) -> None:
		"""進捗を通知（ブラウザ上にも表示）"""
		print(message)
		self._on_progress(message)
		if self.driver:
			show_status(self.driver, message)

	def _create_driver(self) -> webdriver.Chrome:
		"""chrome_profileを使ったChromeドライバーを作成（ブラウザ表示あり）"""
		options = Options()
		profile_dir = os.path.join(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
			"chrome_profile",
		)
		os.makedirs(profile_dir, exist_ok=True)
		options.add_argument(f"--user-data-dir={profile_dir}")
		options.add_argument("--disable-blink-features=AutomationControlled")
		options.add_experimental_option("excludeSwitches", ["enable-automation"])
		options.add_experimental_option("useAutomationExtension", False)
		service = Service(ChromeDriverManager().install())
		driver = webdriver.Chrome(service=service, options=options)
		driver.maximize_window()
		return driver

	def fetch_orders(self, max_pages: int = 3) -> list[OrderItem]:
		"""購入履歴を取得（複数ページ対応）

		Args:
			max_pages: 取得する最大ページ数（デフォルト3ページ）
		"""
		try:
			self.driver = self._create_driver()
			self.driver.get("https://www.amazon.co.jp/gp/your-account/order-history")

			# 注文履歴ページが表示されるまで待機
			self._progress("ページ読み込み中...（ログイン画面が出たら手動でログインしてください）")
			if not self._wait_for_orders_page():
				self._progress("購入履歴ページの読み込みに失敗しました")
				return []

			all_items = []
			seen_asins = set()

			for page_num in range(max_pages):
				self._progress(f"ページ {page_num + 1}/{max_pages} を解析中...")
				page_items = self._parse_orders(seen_asins)
				all_items.extend(page_items)

				# 次のページがあるか確認して移動
				if page_num < max_pages - 1:
					has_next = self.driver.execute_script("""
						const nextLink = document.querySelector('.a-pagination .a-last a');
						if (nextLink) {
							nextLink.click();
							return true;
						}
						return false;
					""")
					if not has_next:
						self._progress("最後のページに達しました")
						break
					# ページ読み込み待機（バーを早期に再表示）
					self._wait_for_next_page(page_num + 2, max_pages)

			self._progress(f"合計{len(all_items)}件の商品を取得しました")
			# 完了後にバーを消す
			if self.driver:
				hide_status(self.driver)
			return all_items
		finally:
			if self.driver:
				self.driver.quit()
				self.driver = None

	def _wait_for_orders_page(self, timeout: int = 180) -> bool:
		"""注文履歴ページが表示されるまで待機"""
		msg = "ページ読み込み中...（ログイン画面が出たら手動でログインしてください）"
		for _ in range(timeout):
			time.sleep(1)
			try:
				# DOMが使える状態ならバーを表示し続ける
				show_status(self.driver, msg)
			except Exception:
				pass
			url = self.driver.current_url.lower()
			if "order-history" in url or "your-orders" in url:
				has_orders = self.driver.execute_script(
					"return document.querySelectorAll('a[href*=\"/dp/\"]').length > 0"
				)
				if has_orders:
					return True
		return False

	def _wait_for_next_page(self, next_page_num: int, max_pages: int, timeout: int = 30) -> bool:
		"""次ページの読み込みを待機しつつ、DOMが使えるようになったらすぐバーを表示"""
		msg = f"ページ {next_page_num}/{max_pages} を読み込み中..."
		for _ in range(timeout):
			time.sleep(0.5)
			try:
				# DOMが利用可能ならバーを即注入
				show_status(self.driver, msg)
				url = self.driver.current_url.lower()
				if "order-history" in url or "your-orders" in url:
					has_orders = self.driver.execute_script(
						"return document.querySelectorAll('a[href*=\"/dp/\"]').length > 0"
					)
					if has_orders:
						return True
			except Exception:
				pass
		return False

	def _parse_orders(self, seen_asins: set) -> list[OrderItem]:
		"""ページから注文情報を抽出"""
		items = self.driver.execute_script("""
			const results = [];
			const orderCards = document.querySelectorAll('.order-card.js-order-card');

			orderCards.forEach(card => {
				// 注文日を取得（ヘッダー内の日付テキスト）
				let orderDate = '';
				const dateSpans = card.querySelectorAll('.order-header span.a-color-secondary');
				for (const span of dateSpans) {
					const text = span.textContent.trim();
					if (text.match(/\\d{4}年\\d{1,2}月\\d{1,2}日/) && text.length < 20) {
						orderDate = text;
						break;
					}
				}

				// 注文合計金額を取得
				let orderPrice = '';
				const priceSpans = card.querySelectorAll('.order-header__header-list-item span.a-color-secondary');
				for (const span of priceSpans) {
					const text = span.textContent.trim();
					if (text.match(/^[¥￥]/)) {
						orderPrice = text;
						break;
					}
				}

				// 各商品を取得
				const titleLinks = card.querySelectorAll('.yohtmlc-product-title a.a-link-normal');
				const imageLinks = card.querySelectorAll('.product-image a.a-link-normal img');

				titleLinks.forEach((link, i) => {
					const href = link.getAttribute('href') || '';
					const title = link.textContent.trim();
					// ASINを抽出
					const asinMatch = href.match(/\\/dp\\/([A-Z0-9]{10})/);
					if (!asinMatch || !title) return;

					const asin = asinMatch[1];
					const imgSrc = (i < imageLinks.length) ? (imageLinks[i].getAttribute('src') || '') : '';

					results.push({
						asin: asin,
						title: title,
						price: orderPrice,
						image_url: imgSrc,
						order_date: orderDate,
						url: 'https://www.amazon.co.jp/dp/' + asin
					});
				});
			});

			return results;
		""")

		order_items = []
		for item in items:
			# 重複排除
			if item["asin"] in seen_asins:
				continue
			seen_asins.add(item["asin"])

			# 価格をintに変換
			price = None
			price_text = item.get("price", "")
			if price_text:
				price_match = re.search(r"[\d,]+", price_text)
				if price_match:
					price = int(price_match.group().replace(",", ""))

			order_items.append(OrderItem(
				asin=item["asin"],
				title=item["title"],
				price=price,
				image_url=item["image_url"],
				order_date=item["order_date"],
				url=item["url"],
			))

		return order_items

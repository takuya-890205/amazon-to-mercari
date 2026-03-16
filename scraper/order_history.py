"""Amazon購入履歴からの商品取得（Playwright版）"""

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright

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


# Windows側Chromeのパス候補
_CHROME_PATHS = [
	"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
	"/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
]


def _find_chrome() -> str:
	"""利用可能なChromeパスを返す"""
	for p in _CHROME_PATHS:
		if os.path.exists(p):
			return p
	raise FileNotFoundError("Windows側のChromeが見つかりません")


class OrderHistoryScraper:
	"""Amazon購入履歴スクレイパー（Playwright + Windows Chrome）"""

	def __init__(self, on_progress=None):
		self.page = None
		self.browser = None
		self.playwright = None
		self._on_progress = on_progress or (lambda msg: None)

	def _progress(self, message: str) -> None:
		"""進捗を通知"""
		print(message)
		self._on_progress(message)
		if self.page:
			show_status(self.page, message)

	def _launch_browser(self):
		"""Windows Chrome をPlaywright経由で起動"""
		chrome_path = _find_chrome()
		profile_dir = os.path.join(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
			"chrome_profile_pw",
		)
		os.makedirs(profile_dir, exist_ok=True)

		self.playwright = sync_playwright().start()
		# persistent_contextでプロファイルを保持（ログイン状態維持）
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

	def fetch_orders(self, max_pages: int = 3) -> list[OrderItem]:
		"""購入履歴を取得"""
		try:
			self._launch_browser()
			self.page.goto("https://www.amazon.co.jp/gp/your-account/order-history")

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

				if page_num < max_pages - 1:
					has_next = self.page.evaluate("""
						() => {
							const nextLink = document.querySelector('.a-pagination .a-last a');
							if (nextLink) {
								nextLink.click();
								return true;
							}
							return false;
						}
					""")
					if not has_next:
						self._progress("最後のページに達しました")
						break
					self._wait_for_next_page(page_num + 2, max_pages)

			self._progress(f"合計{len(all_items)}件の商品を取得しました")
			if self.page:
				hide_status(self.page)
			return all_items
		finally:
			if self.browser:
				self.browser.close()
			if self.playwright:
				self.playwright.stop()
			self.page = None
			self.browser = None
			self.playwright = None

	def _wait_for_orders_page(self, timeout: int = 180) -> bool:
		"""注文履歴ページが表示されるまで待機"""
		msg = "ページ読み込み中...（ログイン画面が出たら手動でログインしてください）"
		for _ in range(timeout):
			time.sleep(1)
			try:
				show_status(self.page, msg)
			except Exception:
				pass
			url = self.page.url.lower()
			if "order-history" in url or "your-orders" in url:
				has_orders = self.page.evaluate(
					"() => document.querySelectorAll('a[href*=\"/dp/\"]').length > 0"
				)
				if has_orders:
					return True
		return False

	def _wait_for_next_page(self, next_page_num: int, max_pages: int, timeout: int = 30) -> bool:
		"""次ページの読み込みを待機"""
		msg = f"ページ {next_page_num}/{max_pages} を読み込み中..."
		for _ in range(timeout):
			time.sleep(0.5)
			try:
				show_status(self.page, msg)
				url = self.page.url.lower()
				if "order-history" in url or "your-orders" in url:
					has_orders = self.page.evaluate(
						"() => document.querySelectorAll('a[href*=\"/dp/\"]').length > 0"
					)
					if has_orders:
						return True
			except Exception:
				pass
		return False

	def _parse_orders(self, seen_asins: set) -> list[OrderItem]:
		"""ページから注文情報を抽出"""
		items = self.page.evaluate("""
			() => {
				const results = [];
				const orderCards = document.querySelectorAll('.order-card.js-order-card');

				orderCards.forEach(card => {
					let orderDate = '';
					const dateSpans = card.querySelectorAll('.order-header span.a-color-secondary');
					for (const span of dateSpans) {
						const text = span.textContent.trim();
						if (text.match(/\\d{4}年\\d{1,2}月\\d{1,2}日/) && text.length < 20) {
							orderDate = text;
							break;
						}
					}

					let orderPrice = '';
					const priceSpans = card.querySelectorAll('.order-header__header-list-item span.a-color-secondary');
					for (const span of priceSpans) {
						const text = span.textContent.trim();
						if (text.match(/^[¥￥]/)) {
							orderPrice = text;
							break;
						}
					}

					const titleLinks = card.querySelectorAll('.yohtmlc-product-title a.a-link-normal');
					const imageLinks = card.querySelectorAll('.product-image a.a-link-normal img');

					titleLinks.forEach((link, i) => {
						const href = link.getAttribute('href') || '';
						const title = link.textContent.trim();
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
			}
		""")

		order_items = []
		for item in items:
			if item["asin"] in seen_asins:
				continue
			seen_asins.add(item["asin"])

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

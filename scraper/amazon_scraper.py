"""Amazon.co.jpから商品情報を取得するスクレイパー（requests + BeautifulSoup版）"""

import json
import re
import time

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

from config import ASIN_PATTERN, SELECTORS, REQUEST_TIMEOUT
from scraper.product_data import AmazonProduct, SearchResult
from scraper.user_agents import get_headers


class AmazonScraper:
	"""Amazon.co.jpから商品情報を取得（requests + BeautifulSoup使用）"""

	def __init__(self):
		self.session = requests.Session()
		self.session.headers.update(get_headers())

	def scrape(self, url: str) -> AmazonProduct:
		"""URLから商品情報を取得"""
		asin = self._extract_asin(url)
		html = self._fetch_page(url)
		return self._parse_product(html, url, asin)

	def search(self, keyword: str, max_results: int = 20) -> list[SearchResult]:
		"""キーワードでAmazon.co.jpを検索し、商品リストを返す"""
		search_url = f"https://www.amazon.co.jp/s?k={quote_plus(keyword)}"
		html = self._fetch_page(search_url)
		return self._parse_search_results(html, max_results)

	def _parse_search_results(self, html: str, max_results: int) -> list[SearchResult]:
		"""検索結果ページをパースして商品リストを返す"""
		soup = BeautifulSoup(html, "lxml")
		results = []

		items = soup.select('div[data-component-type="s-search-result"]')
		for item in items[:max_results]:
			asin = item.get("data-asin", "")
			if not asin:
				continue

			# タイトル
			title_el = item.select_one("h2 span") or item.select_one("h2")
			title = title_el.get_text(strip=True) if title_el else ""
			if not title:
				continue

			# 価格
			price = None
			price_el = item.select_one(".a-price .a-offscreen")
			if price_el:
				numbers = re.findall(r"[\d,]+", price_el.get_text(strip=True))
				if numbers:
					try:
						price = int(numbers[0].replace(",", ""))
					except ValueError:
						pass

			# 画像
			img_el = item.select_one(".s-image")
			image_url = img_el.get("src", "") if img_el else ""

			# URL
			url = f"https://www.amazon.co.jp/dp/{asin}"

			# 評価
			rating = None
			rating_el = item.select_one(".a-icon-alt")
			if rating_el:
				match = re.search(r"([\d.]+)", rating_el.get_text(strip=True))
				if match:
					try:
						rating = float(match.group(1))
					except ValueError:
						pass

			results.append(SearchResult(
				asin=asin,
				title=title,
				price=price,
				image_url=image_url,
				url=url,
				rating=rating,
			))

		return results

	def _extract_asin(self, url: str) -> str:
		"""URLからASINを抽出"""
		match = re.search(ASIN_PATTERN, url)
		if match:
			return match.group(1)
		raise ValueError(f"URLからASINを抽出できません: {url}")

	def _fetch_page(self, url: str) -> str:
		"""requestsでページを取得"""
		response = self.session.get(url, timeout=REQUEST_TIMEOUT)
		response.raise_for_status()
		response.encoding = response.apparent_encoding
		return response.text

	def _parse_product(self, html: str, url: str, asin: str) -> AmazonProduct:
		"""HTMLをパースしてAmazonProductに変換"""
		soup = BeautifulSoup(html, "lxml")

		return AmazonProduct(
			asin=asin,
			url=url,
			title=self._parse_title(soup),
			price=self._parse_price(soup),
			description=self._parse_description(soup),
			bullet_points=self._parse_bullet_points(soup),
			specifications=self._parse_specifications(soup),
			image_urls=self._parse_images(soup, html),
			category_breadcrumb=self._parse_category(soup),
			brand=self._parse_brand(soup),
			rating=self._parse_rating(soup),
			review_count=self._parse_review_count(soup),
		)

	def _find_first(self, soup: BeautifulSoup, selectors: list[str]) -> str:
		"""セレクタチェーンから最初にヒットした要素のテキストを返す"""
		for selector in selectors:
			element = soup.select_one(selector)
			if element and element.get_text(strip=True):
				return element.get_text(strip=True)
		return ""

	def _parse_title(self, soup: BeautifulSoup) -> str:
		"""タイトルを取得"""
		return self._find_first(soup, SELECTORS["title"])

	def _parse_price(self, soup: BeautifulSoup) -> int | None:
		"""価格を取得（円単位の整数）"""
		for selector in SELECTORS["price"]:
			element = soup.select_one(selector)
			if element:
				text = element.get_text(strip=True)
				numbers = re.findall(r"[\d,]+", text)
				if numbers:
					try:
						return int(numbers[0].replace(",", ""))
					except ValueError:
						continue
		return None

	def _parse_images(self, soup: BeautifulSoup, html: str) -> list[str]:
		"""商品画像URLを取得（高解像度版を優先）"""
		image_urls = []

		# JavaScriptのcolorImagesデータから高解像度画像を取得
		pattern = r"'colorImages':\s*\{.*?'initial':\s*(\[.*?\])"
		match = re.search(pattern, html, re.DOTALL)
		if match:
			try:
				images_data = json.loads(match.group(1))
				for img in images_data:
					url = img.get("hiRes") or img.get("large") or img.get("main")
					if url and url not in image_urls:
						image_urls.append(url)
			except (json.JSONDecodeError, KeyError):
				pass

		# フォールバック: imgタグから取得
		if not image_urls:
			for selector in SELECTORS["images"]:
				elements = soup.select(selector)
				for el in elements:
					src = el.get("data-old-hires") or el.get("src") or ""
					if src and "sprite" not in src and src not in image_urls:
						if "._AC_" in src or "._SL" in src:
							src = re.sub(r"\._[A-Z]+_[A-Z]+\d+_\.", "._AC_SL1500_.", src)
						image_urls.append(src)

		return image_urls[:10]

	def _parse_bullet_points(self, soup: BeautifulSoup) -> list[str]:
		"""箇条書き特徴を取得"""
		points = []
		for selector in SELECTORS["bullet_points"]:
			elements = soup.select(selector)
			for el in elements:
				text = el.get_text(strip=True)
				if text and len(text) > 2:
					points.append(text)
			if points:
				break
		return points

	def _parse_description(self, soup: BeautifulSoup) -> str:
		"""商品説明を取得"""
		return self._find_first(soup, SELECTORS["description"])

	def _parse_specifications(self, soup: BeautifulSoup) -> dict[str, str]:
		"""仕様（スペック表）を取得"""
		specs = {}
		for selector in SELECTORS["specifications"]:
			elements = soup.select(selector)
			for el in elements:
				th = el.select_one("th")
				td = el.select_one("td")
				if th and td:
					key = th.get_text(strip=True)
					value = td.get_text(strip=True)
					if key and value:
						specs[key] = value
				else:
					text = el.get_text(strip=True)
					if ":" in text:
						parts = text.split(":", 1)
						specs[parts[0].strip()] = parts[1].strip()
					elif "\n" in text:
						parts = text.split("\n", 1)
						key = parts[0].strip().rstrip(":")
						value = parts[1].strip() if len(parts) > 1 else ""
						if key and value:
							specs[key] = value
			if specs:
				break
		return specs

	def _parse_category(self, soup: BeautifulSoup) -> list[str]:
		"""カテゴリパンくずリストを取得"""
		categories = []
		for selector in SELECTORS["category"]:
			elements = soup.select(selector)
			for el in elements:
				text = el.get_text(strip=True)
				if text and text not in categories:
					categories.append(text)
			if categories:
				break
		return categories

	def _parse_brand(self, soup: BeautifulSoup) -> str:
		"""ブランド名を取得"""
		brand = self._find_first(soup, SELECTORS["brand"])
		if brand:
			brand = re.sub(r"^(ブランド|Brand)\s*[:：]\s*", "", brand)
			brand = re.sub(r"^ストアを?訪問\s*", "", brand)
			brand = re.sub(r"のストアを表示$", "", brand)
		return brand.strip()

	def _parse_rating(self, soup: BeautifulSoup) -> float | None:
		"""評価（星の数）を取得"""
		el = soup.select_one("#acrPopover .a-icon-alt")
		if el:
			text = el.get_text(strip=True)
			match = re.search(r"([\d.]+)", text)
			if match:
				try:
					return float(match.group(1))
				except ValueError:
					pass
		return None

	def _parse_review_count(self, soup: BeautifulSoup) -> int | None:
		"""レビュー数を取得"""
		el = soup.select_one("#acrCustomerReviewText")
		if el:
			text = el.get_text(strip=True)
			numbers = re.findall(r"[\d,]+", text)
			if numbers:
				try:
					return int(numbers[0].replace(",", ""))
				except ValueError:
					pass
		return None

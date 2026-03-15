"""Gemini APIを使ったメルカリ向け出品テキスト生成"""

import json
import os

from dotenv import load_dotenv

from generator.prompts import UNIFIED_LISTING_PROMPT
from scraper.product_data import AmazonProduct, MercariDraft

load_dotenv()


class ListingGenerator:
	"""Gemini API経由でメルカリ出品テキストを一括生成"""

	def __init__(self):
		self.api_key = os.getenv("GEMINI_API_KEY", "")
		if not self.api_key:
			raise RuntimeError(
				"GEMINI_API_KEY が設定されていません。\n"
				"1. https://aistudio.google.com/apikey でAPIキーを取得\n"
				"2. .env ファイルに GEMINI_API_KEY=your_key を設定"
			)

	def generate(
		self,
		product: AmazonProduct,
		condition: str = "新品、未使用",
		additional_notes: str = "",
	) -> MercariDraft:
		"""商品情報からメルカリ出品下書きを一括生成"""
		# プロンプトを構築
		bullet_text = "\n".join(f"・{bp}" for bp in product.bullet_points[:5])
		spec_text = "\n".join(f"・{k}: {v}" for k, v in list(product.specifications.items())[:10])
		category_text = " > ".join(product.category_breadcrumb) if product.category_breadcrumb else "不明"

		prompt = UNIFIED_LISTING_PROMPT.format(
			title=product.title,
			brand=product.brand or "不明",
			price=product.price or "不明",
			category=category_text,
			description=product.description or "なし",
			bullet_points=bullet_text or "なし",
			specifications=spec_text or "なし",
			condition=condition,
			additional_notes=f"補足: {additional_notes}" if additional_notes else "",
		)

		# Gemini API呼び出し
		response_text = self._call_gemini(prompt)

		# JSONパース
		result = self._parse_response(response_text)

		return MercariDraft(
			title=result.get("title", product.title[:40]),
			description=result.get("description", ""),
			category=result.get("category", product.category_breadcrumb[:3]),
			brand=product.brand or "",
			condition=condition,
			hashtags=result.get("hashtags", []),
			source_url=product.url,
		)

	def _call_gemini(self, prompt: str) -> str:
		"""Gemini APIを呼び出してテキスト生成"""
		import google.generativeai as genai

		genai.configure(api_key=self.api_key)
		model = genai.GenerativeModel("gemini-2.0-flash")

		response = model.generate_content(
			prompt,
			generation_config=genai.types.GenerationConfig(
				temperature=0.7,
				max_output_tokens=2048,
			),
		)

		return response.text

	def _parse_response(self, text: str) -> dict:
		"""Gemini APIのレスポンスからJSONを抽出してパース"""
		text = text.strip()

		# ```json ... ``` ブロックを抽出
		if "```json" in text:
			text = text.split("```json")[1].split("```")[0].strip()
		elif "```" in text:
			text = text.split("```")[1].split("```")[0].strip()

		# 直接JSONの場合
		try:
			return json.loads(text)
		except json.JSONDecodeError:
			# { から } までを切り出してリトライ
			start = text.find("{")
			end = text.rfind("}") + 1
			if start >= 0 and end > start:
				try:
					return json.loads(text[start:end])
				except json.JSONDecodeError:
					pass

		print("警告: JSONパースに失敗しました。デフォルト値を使用します。")
		return {}

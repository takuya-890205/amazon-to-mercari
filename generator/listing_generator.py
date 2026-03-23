"""Gemini APIを使ったメルカリ向け出品テキスト生成"""

import json
import os

from dotenv import load_dotenv

from generator.prompts import UNIFIED_LISTING_PROMPT
from scraper.product_data import AmazonProduct, MercariDraft

load_dotenv()

# デフォルトモデル（無料枠で高速）
GEMINI_MODEL = "gemini-2.5-flash"


class ListingGenerator:
	"""Gemini API経由でメルカリ出品テキストを一括生成"""

	def __init__(self, api_key: str = ""):
		from utils.api_key import get_api_key
		self.api_key = api_key or get_api_key()
		if not self.api_key:
			raise RuntimeError(
				"GEMINI_API_KEY が設定されていません。\n"
				"1. https://aistudio.google.com/apikey でAPIキーを取得\n"
				"2. サイドバーの「API設定」からAPIキーを入力してください"
			)

	def generate(
		self,
		product: AmazonProduct,
		condition: str = "新品、未使用",
		additional_notes: str = "",
		description_header: str = "",
		description_footer: str = "",
	) -> MercariDraft:
		"""商品情報からメルカリ出品下書きを一括生成"""
		# プロンプトを構築
		bullet_text = "\n".join(f"・{bp}" for bp in product.bullet_points[:5])
		spec_text = "\n".join(f"・{k}: {v}" for k, v in list(product.specifications.items())[:10])
		category_text = " > ".join(product.category_breadcrumb) if product.category_breadcrumb else "不明"

		# テンプレート指示を組み立て
		tpl_parts = []
		if description_header:
			tpl_parts.append(f"説明文の冒頭に次の内容を含めてください: 「{description_header.strip()}」")
		if description_footer:
			tpl_parts.append(f"説明文の末尾に次の内容を含めてください: 「{description_footer.strip()}」")
		template_instructions = "\n".join(tpl_parts) if tpl_parts else "特になし"

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
			template_instructions=template_instructions,
		)

		# Gemini API呼び出し
		response_text = self._call_gemini(prompt)

		# JSONパース
		result = self._parse_response(response_text)

		# タイトル40文字、説明文1000文字を保証
		title = result.get("title", product.title)
		if len(title) > 40:
			# 40文字以内で意味が通る位置で切る
			title = title[:40]
			# スペースや区切り文字の位置で切り直す
			for sep in [" ", "　", "/", "・", "｜", "|"]:
				pos = title.rfind(sep)
				if 20 <= pos:
					title = title[:pos]
					break
		description = result.get("description", "")[:1000]

		return MercariDraft(
			title=title,
			description=description,
			category=result.get("category", product.category_breadcrumb[:3]),
			brand=product.brand or "",
			condition=condition,
			hashtags=result.get("hashtags", []),
			source_url=product.url,
		)

	def _call_gemini(self, prompt: str) -> str:
		"""Gemini APIを呼び出してテキスト生成"""
		from google import genai

		client = genai.Client(api_key=self.api_key)
		response = client.models.generate_content(
			model=GEMINI_MODEL,
			contents=prompt,
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

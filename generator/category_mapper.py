"""Amazon → メルカリ カテゴリマッピング"""

import json
import os

from dotenv import load_dotenv

from generator.prompts import CATEGORY_PROMPT
from scraper.product_data import AmazonProduct

load_dotenv()

# キーワードベースの静的マッピング（Amazonキーワード → メルカリカテゴリ）
KEYWORD_MAPPING = {
	# スマホ・タブレット・パソコン
	"ノートパソコン": ["スマホ・タブレット・パソコン", "パソコン", "ノートPC"],
	"ノートPC": ["スマホ・タブレット・パソコン", "パソコン", "ノートPC"],
	"タブレット": ["スマホ・タブレット・パソコン", "タブレット", "タブレット本体"],
	"iPad": ["スマホ・タブレット・パソコン", "タブレット", "タブレット本体"],
	"スマートフォン": ["スマホ・タブレット・パソコン", "スマートフォン", "スマートフォン本体"],
	"iPhone": ["スマホ・タブレット・パソコン", "スマートフォン", "スマートフォン本体"],
	"モニター": ["スマホ・タブレット・パソコン", "パソコン周辺機器", "モニター"],
	"キーボード": ["スマホ・タブレット・パソコン", "パソコン周辺機器", "キーボード"],
	"マウス": ["スマホ・タブレット・パソコン", "パソコン周辺機器", "マウス"],
	"充電器": ["スマホ・タブレット・パソコン", "スマホアクセサリー", "充電器"],
	"モバイルバッテリー": ["スマホ・タブレット・パソコン", "スマホアクセサリー", "モバイルバッテリー"],

	# テレビ・オーディオ・カメラ
	"イヤホン": ["テレビ・オーディオ・カメラ", "オーディオ", "イヤホン"],
	"ヘッドホン": ["テレビ・オーディオ・カメラ", "オーディオ", "ヘッドホン"],
	"ヘッドフォン": ["テレビ・オーディオ・カメラ", "オーディオ", "ヘッドホン"],
	"スピーカー": ["テレビ・オーディオ・カメラ", "オーディオ", "スピーカー"],
	"カメラ": ["テレビ・オーディオ・カメラ", "カメラ", "デジタルカメラ"],
	"デジタルカメラ": ["テレビ・オーディオ・カメラ", "カメラ", "デジタルカメラ"],
	"一眼レフ": ["テレビ・オーディオ・カメラ", "カメラ", "一眼レフカメラ"],
	"ミラーレス": ["テレビ・オーディオ・カメラ", "カメラ", "ミラーレス一眼"],
	"テレビ": ["テレビ・オーディオ・カメラ", "テレビ", "テレビ"],

	# 生活家電・空調
	"掃除機": ["生活家電・空調", "生活家電", "掃除機"],
	"空気清浄機": ["生活家電・空調", "空調", "空気清浄機"],
	"エアコン": ["生活家電・空調", "空調", "エアコン"],
	"ドライヤー": ["生活家電・空調", "美容家電", "ドライヤー"],

	# ゲーム・おもちゃ・グッズ
	"フィギュア": ["ゲーム・おもちゃ・グッズ", "フィギュア", "その他"],
	"プラモデル": ["ゲーム・おもちゃ・グッズ", "おもちゃ", "プラモデル"],
	"ゲーム": ["ゲーム・おもちゃ・グッズ", "テレビゲーム", "ソフト"],
	"Nintendo Switch": ["ゲーム・おもちゃ・グッズ", "テレビゲーム", "本体"],
	"PS5": ["ゲーム・おもちゃ・グッズ", "テレビゲーム", "本体"],
	"PlayStation": ["ゲーム・おもちゃ・グッズ", "テレビゲーム", "本体"],
	"トレカ": ["ゲーム・おもちゃ・グッズ", "トレーディングカード", "その他"],
	"レゴ": ["ゲーム・おもちゃ・グッズ", "おもちゃ", "知育玩具"],

	# 本・雑誌・漫画
	"本": ["本・雑誌・漫画", "本", "その他"],
	"漫画": ["本・雑誌・漫画", "漫画", "全巻セット"],
	"コミック": ["本・雑誌・漫画", "漫画", "少年漫画"],
	"参考書": ["本・雑誌・漫画", "本", "参考書"],

	# コスメ・美容
	"化粧品": ["コスメ・美容", "メイクアップ", "その他"],
	"ファンデーション": ["コスメ・美容", "ベースメイク", "ファンデーション"],
	"香水": ["コスメ・美容", "香水", "香水"],
	"スキンケア": ["コスメ・美容", "スキンケア", "その他"],

	# スポーツ
	"ゴルフ": ["スポーツ", "ゴルフ", "クラブ"],
	"テニス": ["スポーツ", "テニス", "ラケット"],
	"サッカー": ["スポーツ", "サッカー", "ボール"],
	"野球": ["スポーツ", "野球", "グローブ"],
	"ランニングシューズ": ["スポーツ", "ランニング", "シューズ"],

	# アウトドア・釣り・旅行用品
	"キャンプ": ["アウトドア・釣り・旅行用品", "キャンプ", "テント"],
	"釣り": ["アウトドア・釣り・旅行用品", "釣り", "ロッド"],
	"自転車": ["車・バイク・自転車", "自転車", "自転車本体"],

	# ファッション
	"スニーカー": ["ファッション", "靴", "スニーカー"],
	"時計": ["ファッション", "時計", "腕時計"],
	"腕時計": ["ファッション", "時計", "腕時計"],

	# 家具・インテリア
	"クッション": ["家具・インテリア", "インテリア小物", "クッション"],

	# キッチン・日用品・その他
	"フライパン": ["キッチン・日用品・その他", "キッチン用品", "調理器具"],
	"食器": ["キッチン・日用品・その他", "キッチン用品", "食器"],
}


class CategoryMapper:
	"""Amazon → メルカリ カテゴリ変換"""

	def map_category(self, product: AmazonProduct) -> list[str]:
		"""ルールベースでカテゴリを推定"""
		search_text = f"{product.title} {product.brand} {' '.join(product.category_breadcrumb)}"

		for keyword, mercari_category in KEYWORD_MAPPING.items():
			if keyword in search_text:
				return mercari_category

		if product.category_breadcrumb:
			return product.category_breadcrumb[:3]

		return ["その他", "その他", "その他"]

	def map_with_ai(self, product: AmazonProduct) -> list[str]:
		"""Gemini APIでカテゴリを推定（フォールバック用）"""
		api_key = os.getenv("GEMINI_API_KEY", "")
		if not api_key:
			return self.map_category(product)

		prompt = CATEGORY_PROMPT.format(
			title=product.title,
			brand=product.brand or "不明",
			amazon_category=" > ".join(product.category_breadcrumb) if product.category_breadcrumb else "不明",
		)

		try:
			import google.generativeai as genai
			genai.configure(api_key=api_key)
			model = genai.GenerativeModel("gemini-2.0-flash")
			response = model.generate_content(prompt)
			text = response.text.strip()

			start = text.find("{")
			end = text.rfind("}") + 1
			if start >= 0 and end > start:
				parsed = json.loads(text[start:end])
				return parsed.get("category", self.map_category(product))
		except Exception as e:
			print(f"カテゴリ推定エラー: {e}")

		return self.map_category(product)

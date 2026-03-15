"""Amazon → メルカリ出品下書き生成 CLIツール"""

import argparse
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from config import CONDITION_CHOICES, SHIPPING_DAYS_CHOICES
from generator.price_calculator import calculate_price
from output.draft_exporter import to_json, to_text
from scraper.amazon_scraper import AmazonScraper
from scraper.product_data import MercariDraft


def create_basic_draft(product, condition, region, shipping_method, shipping_size, shipping_days):
	"""AIなしの基本的な下書きを作成"""
	# 価格計算
	if product.price:
		breakdown = calculate_price(
			product.price,
			condition=condition,
			shipping_method=shipping_method,
			shipping_size=shipping_size,
		)
		price = breakdown.suggested_price
	else:
		breakdown = None
		price = 0

	# タイトル（40文字以内に切り詰め）
	title = product.title[:40] if product.title else "商品名なし"

	# 説明文（基本テンプレート）
	desc_parts = [product.title, ""]
	if product.bullet_points:
		desc_parts.append("【特徴】")
		for bp in product.bullet_points[:5]:
			desc_parts.append(f"・{bp}")
		desc_parts.append("")
	if product.brand:
		desc_parts.append(f"ブランド: {product.brand}")
	desc_parts.extend([
		"",
		f"商品の状態: {condition}",
		"",
		"※ Amazon商品ページから情報を取得して作成した下書きです。",
	])
	description = "\n".join(desc_parts)[:1000]

	return MercariDraft(
		title=title,
		description=description,
		category=product.category_breadcrumb[:3],
		condition=condition,
		shipping_payer="送料込み(出品者負担)",
		shipping_method=shipping_method,
		shipping_from=region,
		shipping_days=shipping_days,
		price=price,
		price_breakdown=breakdown,
		image_paths=[],
		hashtags=[],
		source_url=product.url,
	)


def main():
	parser = argparse.ArgumentParser(
		description="Amazon商品ページ → メルカリ出品下書き生成",
	)
	parser.add_argument("url", help="Amazon商品ページURL")
	parser.add_argument(
		"--condition",
		default="新品、未使用",
		choices=CONDITION_CHOICES,
		help="商品の状態",
	)
	parser.add_argument("--region", default="東京都", help="発送元の地域")
	parser.add_argument(
		"--shipping-method",
		default="らくらくメルカリ便",
		help="配送方法",
	)
	parser.add_argument("--shipping-size", default="60サイズ", help="配送サイズ")
	parser.add_argument(
		"--shipping-days",
		default="2~3日で発送",
		choices=SHIPPING_DAYS_CHOICES,
		help="発送までの日数",
	)
	parser.add_argument("--output", "-o", default=None, help="JSON出力ファイルパス")
	parser.add_argument("--ai", action="store_true", help="Gemini AIでテキスト生成")
	parser.add_argument("--images", action="store_true", help="画像をダウンロード")
	parser.add_argument("--ui", action="store_true", help="Streamlit UIを起動")

	args = parser.parse_args()

	# Streamlit UI起動
	if args.ui:
		import subprocess
		app_path = Path(__file__).parent / "app.py"
		subprocess.run(["streamlit", "run", str(app_path)])
		return

	# Amazon商品情報を取得
	print(f"Amazon商品情報を取得中: {args.url}")
	scraper = AmazonScraper()
	try:
		product = scraper.scrape(args.url)
	except Exception as e:
		print(f"エラー: 商品情報の取得に失敗しました - {e}")
		sys.exit(1)

	print(f"  タイトル: {product.title}")
	print(f"  価格: ¥{product.price:,}" if product.price else "  価格: 取得不可")
	print(f"  ブランド: {product.brand}" if product.brand else "")
	print(f"  画像: {len(product.image_urls)}枚")
	print(f"  仕様: {len(product.specifications)}項目")

	# AIで出品テキスト生成
	if args.ai:
		try:
			from generator.listing_generator import ListingGenerator
			print("\nGemini AIで出品テキストを生成中...")
			generator = ListingGenerator()
			draft = generator.generate(product, condition=args.condition)
			if product.price:
				draft.price_breakdown = calculate_price(
					product.price,
					condition=args.condition,
					shipping_method=args.shipping_method,
					shipping_size=args.shipping_size,
				)
				draft.price = draft.price_breakdown.suggested_price
			draft.shipping_from = args.region
			draft.shipping_method = args.shipping_method
			draft.shipping_days = args.shipping_days
			draft.source_url = product.url
		except Exception as e:
			print(f"AI生成エラー: {e}")
			print("基本テンプレートで下書きを作成します。")
			draft = create_basic_draft(
				product, args.condition, args.region,
				args.shipping_method, args.shipping_size, args.shipping_days,
			)
	else:
		draft = create_basic_draft(
			product, args.condition, args.region,
			args.shipping_method, args.shipping_size, args.shipping_days,
		)

	# 画像ダウンロード
	if args.images and product.image_urls:
		try:
			from image.image_processor import ImageProcessor
			print(f"\n画像をダウンロード中 ({len(product.image_urls)}枚)...")
			processor = ImageProcessor()
			draft.image_paths = processor.process_images(
				product.image_urls, product.asin,
			)
			print(f"  保存完了: {len(draft.image_paths)}枚")
		except Exception as e:
			print(f"画像ダウンロードエラー: {e}")

	# 出力
	print("\n" + to_text(draft))

	# JSON保存
	output_path = args.output or f"draft_{product.asin}.json"
	to_json(draft, output_path)
	print(f"\nJSON保存: {output_path}")


if __name__ == "__main__":
	main()

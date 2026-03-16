"""メルカリ下書きデータの出力"""

import json
from dataclasses import asdict
from pathlib import Path

from scraper.product_data import MercariDraft


def to_json(draft: MercariDraft, output_path: str | None = None) -> str:
	"""JSON形式で出力（ファイル保存 or 文字列返却）"""
	data = asdict(draft)
	json_str = json.dumps(data, ensure_ascii=False, indent=2)

	if output_path:
		Path(output_path).write_text(json_str, encoding="utf-8")

	return json_str


def to_text(draft: MercariDraft) -> str:
	"""コピペ用テキスト形式に変換"""
	lines = [
		"=" * 50,
		"【メルカリ出品下書き】",
		"=" * 50,
		"",
		f"■ タイトル: {draft.title}",
		"",
		"■ 説明文:",
		draft.description,
		"",
		f"■ カテゴリ: {' > '.join(draft.category)}",
		f"■ 商品の状態: {draft.condition}",
		f"■ 配送料の負担: {draft.shipping_payer}",
		f"■ 配送方法: {draft.shipping_method}",
		f"■ 発送元: {draft.shipping_from}",
		f"■ 発送日数: {draft.shipping_days}",
		f"■ 価格: ¥{draft.price:,}",
	]

	if draft.price_breakdown:
		pb = draft.price_breakdown
		lines.extend([
			"",
			"--- 価格内訳 ---",
			f"  Amazon価格: ¥{pb.amazon_price:,}",
			f"  出品価格:   ¥{pb.suggested_price:,}",
			f"  手数料(10%): -¥{pb.mercari_fee:,}",
			f"  送料:       -¥{pb.shipping_cost:,}",
			f"  推定利益:    ¥{pb.estimated_profit:,}",
		])

	if draft.hashtags:
		lines.extend([
			"",
			f"■ ハッシュタグ: {' '.join('#' + t for t in draft.hashtags)}",
		])

	if draft.image_paths:
		lines.extend([
			"",
			f"■ 画像: {len(draft.image_paths)}枚",
			*[f"  - {p}" for p in draft.image_paths],
		])

	lines.extend([
		"",
		f"■ 元URL: {draft.source_url}",
		"=" * 50,
	])

	return "\n".join(lines)


def to_clipboard(draft: MercariDraft) -> bool:
	"""タイトルと説明文をクリップボードにコピー"""
	try:
		import pyperclip
		text = f"{draft.title}\n\n{draft.description}"
		pyperclip.copy(text)
		return True
	except ImportError:
		print("pyperclipがインストールされていません: pip install pyperclip")
		return False

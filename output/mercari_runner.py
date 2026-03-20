"""メルカリ転記をサブプロセスとして実行するランナー

Streamlit内ではasyncioイベントループの制約でPlaywrightが起動できないため、
別プロセスとして実行する。
"""

import json
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.product_data import MercariDraft
from output.mercari_filler import MercariFiller


def main():
	if len(sys.argv) < 2:
		print("ERROR:ドラフトデータ（JSON）を引数で指定してください", flush=True)
		sys.exit(1)

	draft_data = json.loads(sys.argv[1])

	draft = MercariDraft(
		title=draft_data.get("title", ""),
		description=draft_data.get("description", ""),
		category=draft_data.get("category", []),
		brand=draft_data.get("brand", ""),
		condition=draft_data.get("condition", "新品、未使用"),
		shipping_payer=draft_data.get("shipping_payer", "送料込み(出品者負担)"),
		shipping_method=draft_data.get("shipping_method", "らくらくメルカリ便"),
		shipping_from=draft_data.get("shipping_from", "東京都"),
		shipping_days=draft_data.get("shipping_days", "2~3日で発送"),
		price=draft_data.get("price", 0),
		image_paths=draft_data.get("image_paths", []),
		hashtags=draft_data.get("hashtags", []),
		source_url=draft_data.get("source_url", ""),
	)

	def on_progress(msg):
		# PROGRESS:プレフィックスで親プロセスに進捗を伝える
		print(f"PROGRESS:{msg}", flush=True)

	filler = MercariFiller(on_progress=on_progress)
	filler.fill_listing(draft, wait_for_close=False)
	print("DONE:メルカリ出品フォームに入力しました。", flush=True)

	# ブラウザを開いたまま維持し、ユーザーが閉じるまで待機
	if filler.page:
		try:
			filler.page.wait_for_event("close", timeout=0)
		except Exception:
			pass
	filler._cleanup()


if __name__ == "__main__":
	main()

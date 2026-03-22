"""Amazon → メルカリ出品下書き生成 Streamlit UI"""

import os
import signal
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from config import (
	CONDITION_CHOICES,
	MERCARI_PRICE_MIN,
	MERCARI_PRICE_MAX,
	PREFECTURES,
	SHIPPING_DAYS_CHOICES,
	SHIPPING_METHODS,
	load_template,
	save_template,
)
from generator.price_calculator import calculate_price, suggest_price_range
from output.draft_exporter import to_json, to_text
from scraper.amazon_scraper import AmazonScraper
from scraper.product_data import MercariDraft


st.set_page_config(
	page_title="Amazon → メルカリ 出品下書き生成",
	page_icon="🛒",
	layout="wide",
)

st.title("Amazon → メルカリ 出品下書き生成")

# サイドバーをコンパクトにするCSS
st.markdown("""<style>
	[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
	[data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stTextInput,
	[data-testid="stSidebar"] .stTextArea { margin-bottom: -0.5rem; }
	[data-testid="stSidebar"] hr { margin: 0.3rem 0; }
	[data-testid="stSidebar"] .stExpander { margin-bottom: -0.5rem; }
</style>""", unsafe_allow_html=True)


# --- セッション状態の初期化 ---
if "product" not in st.session_state:
	st.session_state.product = None
if "draft" not in st.session_state:
	st.session_state.draft = None
if "images_downloaded" not in st.session_state:
	st.session_state.images_downloaded = False
if "last_fetched_url" not in st.session_state:
	st.session_state.last_fetched_url = ""

# テンプレート読み込み
template = load_template()


# --- サイドバー ---
with st.sidebar:
	st.header("設定")

	# ファイル経由で購入履歴から選んだURLを受け取る
	_selected_url_file = Path(__file__).parent / "data" / ".selected_amazon_url"

	# 購入履歴のポーリング中にファイルを検知したらURLを取得してrerun
	if _selected_url_file.exists():
		_url_from_history = _selected_url_file.read_text(encoding="utf-8").strip()
		_selected_url_file.unlink()
		if _url_from_history:
			st.session_state.amazon_url_from_history = _url_from_history
			st.session_state.waiting_for_history = False
			st.rerun()

	# セッション状態にURLがあればtext_inputのデフォルト値にする
	_default_url = st.session_state.pop("amazon_url_from_history", "")
	amazon_url = st.text_input(
		"Amazon商品URL（Enterで開始）",
		value=_default_url,
		placeholder="https://www.amazon.co.jp/dp/XXXXXXXXXX",
	)

	if st.button("📦 購入履歴から選ぶ", use_container_width=True):
		import subprocess as _sp
		runner_path = str(Path(__file__).parent / "scraper" / "amazon_history_runner.py")
		env = os.environ.copy()
		env["PYTHONIOENCODING"] = "utf-8"
		_sp.Popen(
			[sys.executable, "-X", "utf8", runner_path, "8501"],
			stdout=_sp.DEVNULL,
			stderr=_sp.DEVNULL,
			stdin=_sp.DEVNULL,
			env=env,
			creationflags=_sp.DETACHED_PROCESS if sys.platform == "win32" else 0,
		)
		st.session_state.waiting_for_history = True
		st.rerun()

	# 購入履歴からの選択を待機中：ファイルを1秒ごとにポーリング
	if st.session_state.get("waiting_for_history", False):
		st.info("Amazon購入履歴をブラウザで開いています。商品の「出品する」ボタンをクリックしてください。")

		@st.fragment(run_every=1)
		def _poll_selected_url():
			if _selected_url_file.exists():
				_url = _selected_url_file.read_text(encoding="utf-8").strip()
				_selected_url_file.unlink()
				if _url:
					st.session_state.amazon_url_from_history = _url
					st.session_state.waiting_for_history = False
					st.rerun()
		_poll_selected_url()

	# URLが有効なら自動でフェッチ開始（Enterで確定された時点で発動）
	_is_valid_url = bool(amazon_url and ("amazon.co.jp" in amazon_url or "amzn" in amazon_url))
	_auto_fetch = _is_valid_url and (amazon_url != st.session_state.get("last_fetched_url", ""))
	fetch_button = _auto_fetch

	st.divider()

	# 商品の状態
	condition_idx = CONDITION_CHOICES.index(template["condition"]) if template["condition"] in CONDITION_CHOICES else 0
	condition = st.selectbox("商品の状態", CONDITION_CHOICES, index=condition_idx)

	# 補足コメント
	additional_notes = st.text_area(
		"補足コメント（AIに反映）",
		height=68,
		placeholder="例: 水没歴ありのジャンク品、付属品なし",
	)

	# オプション
	col_ai, col_img = st.columns(2)
	with col_ai:
		use_ai = st.checkbox("AI生成", value=template.get("use_ai", True))
	with col_img:
		download_images = st.checkbox("画像DL", value=template.get("download_images", True))

	# --- 配送設定 ---
	method_keys = list(SHIPPING_METHODS.keys())
	method_idx = method_keys.index(template["shipping_method"]) if template["shipping_method"] in method_keys else 0
	shipping_method = st.selectbox("配送方法", method_keys, index=method_idx)

	size_options = list(SHIPPING_METHODS[shipping_method].keys())
	size_idx = size_options.index(template["shipping_size"]) if template["shipping_size"] in size_options else 0
	shipping_size = st.selectbox("サイズ", size_options, index=size_idx)

	with st.expander("発送元・日数"):
		pref_idx = PREFECTURES.index(template["shipping_from"]) if template["shipping_from"] in PREFECTURES else 12
		shipping_from = st.selectbox("発送元", PREFECTURES, index=pref_idx)

		days_idx = SHIPPING_DAYS_CHOICES.index(template["shipping_days"]) if template["shipping_days"] in SHIPPING_DAYS_CHOICES else 1
		shipping_days = st.selectbox("発送日数", SHIPPING_DAYS_CHOICES, index=days_idx)

	# --- テンプレート・API設定（折りたたみ） ---
	with st.expander("テンプレート・API設定"):
		tpl_header = st.text_input(
			"説明文ヘッダー",
			value=template.get("description_header", ""),
			placeholder="例: 【即日発送】【送料無料】",
		)
		tpl_footer = st.text_input(
			"説明文フッター",
			value=template.get("description_footer", ""),
			placeholder="例: ご質問はお気軽にコメントください。",
		)

		st.divider()

		_api_key_file = Path(__file__).parent / "data" / ".gemini_api_key"
		_api_key_file.parent.mkdir(exist_ok=True)
		_saved_key = _api_key_file.read_text(encoding="utf-8").strip() if _api_key_file.exists() else ""
		_env_key = os.getenv("GEMINI_API_KEY", "")

		gemini_key_input = st.text_input(
			"Gemini APIキー" + (" ✅" if (_saved_key or _env_key) else ""),
			value=_saved_key,
			type="password",
			placeholder="AIxxxxxxxxx...",
			help="https://aistudio.google.com/apikey で無料取得",
		)
		if gemini_key_input != _saved_key:
			_api_key_file.write_text(gemini_key_input, encoding="utf-8")
			st.rerun()

		st.divider()

		if st.button("現在の設定をデフォルトとして保存", use_container_width=True):
			new_template = {
				"condition": condition,
				"shipping_method": shipping_method,
				"shipping_size": shipping_size,
				"shipping_from": shipping_from,
				"shipping_days": shipping_days,
				"description_header": tpl_header,
				"description_footer": tpl_footer,
				"use_ai": use_ai,
				"download_images": download_images,
			}
			save_template(new_template)
			st.success("保存しました")

	# 有効なAPIキーを決定（UI入力 > 環境変数）
	_active_api_key = _saved_key or _env_key


# --- 商品情報取得 ---
if fetch_button and amazon_url:
	st.session_state.last_fetched_url = amazon_url
	with st.spinner("Amazon商品情報を取得中..."):
		try:
			scraper = AmazonScraper()
			st.session_state.product = scraper.scrape(amazon_url)
			st.session_state.images_downloaded = False
			st.success("商品情報を取得しました")
		except Exception as e:
			st.error(f"取得エラー: {e}")
			st.session_state.product = None

	# AIで出品テキスト生成
	if st.session_state.product and use_ai:
		with st.spinner("Gemini AIで出品テキストを生成中..."):
			try:
				from generator.listing_generator import ListingGenerator
				generator = ListingGenerator(api_key=_active_api_key)
				draft = generator.generate(
					st.session_state.product,
					condition=condition,
					additional_notes=additional_notes,
					description_header=tpl_header,
					description_footer=tpl_footer,
				)
				# 価格・配送情報を設定
				if st.session_state.product.price:
					breakdown = calculate_price(
						st.session_state.product.price,
						condition=condition,
						shipping_method=shipping_method,
						shipping_size=shipping_size,
					)
					draft.price = breakdown.suggested_price
					draft.price_breakdown = breakdown
				draft.shipping_payer = "送料込み(出品者負担)"
				draft.shipping_method = shipping_method
				draft.shipping_from = shipping_from
				draft.shipping_days = shipping_days
				draft.source_url = amazon_url

				st.session_state.draft = draft
			except Exception as e:
				st.warning(f"AI生成エラー: {e}。基本テンプレートを使用します。")
				use_ai = False

	# AIなしの場合は基本テンプレート
	if st.session_state.product and not use_ai:
		from main import create_basic_draft
		draft = create_basic_draft(
			st.session_state.product,
			condition, shipping_from, shipping_method, shipping_size, shipping_days,
		)
		# テンプレートのヘッダー・フッターを適用
		desc = draft.description
		if tpl_header:
			desc = tpl_header.strip() + "\n\n" + desc
		if tpl_footer:
			desc = desc.rstrip() + "\n" + tpl_footer.strip()
		draft.description = desc[:1000]
		st.session_state.draft = draft

	# 画像ダウンロード
	if st.session_state.product and download_images and st.session_state.product.image_urls:
		with st.spinner("画像をダウンロード中..."):
			try:
				from image.image_processor import ImageProcessor
				processor = ImageProcessor()
				image_paths = processor.process_images(
					st.session_state.product.image_urls,
					st.session_state.product.asin,
				)
				if st.session_state.draft:
					st.session_state.draft.image_paths = image_paths
				st.session_state.images_downloaded = True
			except Exception as e:
				st.warning(f"画像ダウンロードエラー: {e}")

	# 下書き生成完了後にページを再描画
	if st.session_state.draft:
		st.rerun()


# --- メインエリア: 商品詳細 + 下書き編集 ---
product = st.session_state.product
draft = st.session_state.draft

if product and draft:
	col_amazon, col_mercari = st.columns(2)

	# 左: Amazon商品プレビュー
	with col_amazon:
		st.subheader("Amazon 商品情報")

		# 画像ギャラリー
		if product.image_urls:
			display_urls = product.image_urls[:5]
			if len(display_urls) >= 3:
				img_cols = st.columns(3)
			else:
				img_cols = st.columns(len(display_urls))
			for i, url in enumerate(display_urls):
				with img_cols[i % len(img_cols)]:
					st.image(url, use_container_width=True)

		st.markdown(f"**タイトル:** {product.title}")
		st.markdown(f"**価格:** ¥{product.price:,}" if product.price else "**価格:** 取得不可")
		if product.brand:
			st.markdown(f"**ブランド:** {product.brand}")
		if product.rating:
			st.markdown(f"**評価:** {'⭐' * int(product.rating)} ({product.rating})")
		if product.category_breadcrumb:
			st.markdown(f"**カテゴリ:** {' > '.join(product.category_breadcrumb)}")

		if product.bullet_points:
			with st.expander("特徴", expanded=False):
				for bp in product.bullet_points:
					st.markdown(f"- {bp}")

		if product.specifications:
			with st.expander("仕様", expanded=False):
				for k, v in product.specifications.items():
					st.markdown(f"- **{k}:** {v}")

	# 右: メルカリ出品プレビュー（編集可能）
	with col_mercari:
		st.subheader("メルカリ 出品下書き")

		edited_title = st.text_input(
			"タイトル (最大40文字)",
			value=draft.title,
			max_chars=40,
		)

		edited_description = st.text_area(
			"説明文 (最大1000文字)",
			value=draft.description,
			height=250,
			max_chars=1000,
		)

		edited_category = st.text_input(
			"カテゴリ",
			value=" > ".join(draft.category),
		)

		# 価格設定
		if product.price:
			low, mid, high = suggest_price_range(product.price, condition)
			edited_price = st.slider(
				"出品価格",
				min_value=MERCARI_PRICE_MIN,
				max_value=min(high * 2, MERCARI_PRICE_MAX),
				value=mid,
				step=100,
			)

			# 価格内訳表示
			fee = int(edited_price * 0.10)
			shipping_cost = SHIPPING_METHODS.get(shipping_method, {}).get(shipping_size, 750)
			profit = edited_price - fee - shipping_cost
			st.markdown(
				f"手数料(10%): -¥{fee:,} | 送料: -¥{shipping_cost:,} | "
				f"**利益: ¥{profit:,}**"
			)
		else:
			edited_price = st.number_input("出品価格", min_value=300, value=1000, step=100)

		# ハッシュタグ
		if draft.hashtags:
			st.markdown("**ハッシュタグ:** " + " ".join(f"`#{t}`" for t in draft.hashtags))

		# ダウンロード済み画像（選択式）
		if draft.image_paths:
			if "selected_images" not in st.session_state or len(st.session_state.selected_images) != len(draft.image_paths):
				st.session_state.selected_images = [False] * len(draft.image_paths)

			selected_count = sum(st.session_state.selected_images)
			st.markdown(f"**画像:** {selected_count}/{len(draft.image_paths)}枚 選択中")

			with st.expander("画像を選択", expanded=True):
				sel_cols = st.columns(2)
				with sel_cols[0]:
					if st.button("すべて選択", use_container_width=True):
						st.session_state.selected_images = [True] * len(draft.image_paths)
						st.rerun()
				with sel_cols[1]:
					if st.button("すべて解除", use_container_width=True):
						st.session_state.selected_images = [False] * len(draft.image_paths)
						st.rerun()

				img_cols2 = st.columns(min(3, len(draft.image_paths)))
				for i, path in enumerate(draft.image_paths):
					with img_cols2[i % len(img_cols2)]:
						st.image(path, use_container_width=True)
						st.session_state.selected_images[i] = st.checkbox(
							f"画像{i+1}",
							value=st.session_state.selected_images[i],
							key=f"img_sel_{i}",
						)

	# --- 編集内容をドラフトに反映 ---
	draft.title = edited_title
	draft.description = edited_description
	draft.category = [c.strip() for c in edited_category.split(">")]
	draft.price = edited_price

	# --- アクションボタン ---
	st.divider()
	action_cols = st.columns(4)

	with action_cols[0]:
		if st.button("📋 テキストをコピー", use_container_width=True):
			try:
				from output.draft_exporter import to_clipboard
				if to_clipboard(draft):
					st.success("クリップボードにコピーしました")
				else:
					st.warning("pyperclipをインストールしてください")
			except Exception as e:
				st.error(f"コピーエラー: {e}")

	with action_cols[1]:
		json_str = to_json(draft)
		st.download_button(
			"💾 JSONダウンロード",
			data=json_str,
			file_name=f"draft_{product.asin}.json",
			mime="application/json",
			use_container_width=True,
		)

	with action_cols[2]:
		text_str = to_text(draft)
		st.download_button(
			"📄 テキストダウンロード",
			data=text_str,
			file_name=f"draft_{product.asin}.txt",
			mime="text/plain",
			use_container_width=True,
		)

	with action_cols[3]:
		# Playwright がインストール済みか確認
		try:
			import playwright
			_pw_available = True
		except ImportError:
			_pw_available = False

		if _pw_available:
			if st.button("🛒 メルカリに転記", use_container_width=True):
				# 選択された画像のみをドラフトに設定
				if draft.image_paths and "selected_images" in st.session_state:
					draft.image_paths = [
						p for p, sel in zip(draft.image_paths, st.session_state.selected_images) if sel
					]
				progress_container = st.empty()
				try:
					import json as _json
					import subprocess as _sp
					from dataclasses import asdict

					draft_json = _json.dumps(asdict(draft), ensure_ascii=False, default=str)
					runner_path = str(Path(__file__).parent / "output" / "mercari_runner.py")

					progress_container.info("⏳ ブラウザを起動中...")
					env = os.environ.copy()
					env["PYTHONIOENCODING"] = "utf-8"
					proc = _sp.Popen(
						[sys.executable, "-X", "utf8", runner_path, draft_json],
						stdout=_sp.PIPE,
						stderr=_sp.PIPE,
						text=True,
						encoding="utf-8",
						errors="replace",
						env=env,
					)

					# サブプロセスの出力をリアルタイム表示
					success = False
					error_lines = []
					for line in proc.stdout:
						line = line.strip()
						if line.startswith("PROGRESS:"):
							progress_container.info(f"⏳ {line[9:]}")
						elif line.startswith("DONE:"):
							success = True
							break
						elif line.startswith("ERROR:"):
							error_lines.append(line[6:])

					if success:
						# サブプロセスはブラウザを開いたまま維持する（ユーザーが閉じるまで）
						progress_container.success("メルカリ出品フォームに入力しました。内容を確認して出品してください。")
					else:
						proc.wait()
						stderr = proc.stderr.read()
						error_msg = "\n".join(error_lines) or stderr or "不明なエラー"
						progress_container.error(f"自動入力エラー")
						if stderr:
							st.code(stderr, language="text")
				except Exception as e:
					import traceback
					error_detail = traceback.format_exc()
					progress_container.error(f"自動入力エラー: {e}")
					st.code(error_detail, language="text")
		else:
			st.button("🛒 メルカリに転記", use_container_width=True, disabled=True,
				help="pip install playwright && playwright install chromium を実行してください")

elif not st.session_state.product:
	st.info("サイドバーにAmazon商品URLを入力してください。")

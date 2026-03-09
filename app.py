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
)
from generator.price_calculator import calculate_price, suggest_price_range
from output.draft_exporter import to_json, to_text
from scraper.amazon_scraper import AmazonScraper
from scraper.product_data import MercariDraft


st.set_page_config(
	page_title="Amazon → メルカリ 出品入力サポート",
	page_icon="🛒",
	layout="wide",
)

st.title("Amazon → メルカリ 出品入力サポート")


# --- セッション状態の初期化 ---
if "product" not in st.session_state:
	st.session_state.product = None
if "draft" not in st.session_state:
	st.session_state.draft = None
if "images_downloaded" not in st.session_state:
	st.session_state.images_downloaded = False
if "selected_url" not in st.session_state:
	st.session_state.selected_url = ""
if "order_items" not in st.session_state:
	st.session_state.order_items = None
if "last_fetched_url" not in st.session_state:
	st.session_state.last_fetched_url = ""


# --- サイドバー ---
with st.sidebar:
	st.header("設定")

	st.subheader("商品の指定方法")
	input_mode = st.radio(
		"商品の指定方法",
		["購入履歴から選択", "URLから取得"],
		horizontal=True,
		label_visibility="collapsed",
	)

	if input_mode == "購入履歴から選択":
		order_button = st.button("履歴を取得して右に表示", type="primary", use_container_width=True)
		amazon_url = ""
	else:
		order_button = False
		amazon_url = st.text_input(
			"Amazon商品URL",
			value=st.session_state.selected_url,
			placeholder="https://www.amazon.co.jp/dp/XXXXXXXXXX",
			label_visibility="collapsed",
		)
		st.markdown("URLが分からない場合:")
		st.link_button("購入履歴からURLを探す", "https://www.amazon.co.jp/gp/your-account/order-history", use_container_width=True)

	# URL入力で自動取得（新しいURLが入力されたら自動フェッチ）
	fetch_button = False
	if amazon_url and amazon_url != st.session_state.last_fetched_url:
		# amazon.co.jpのURLかチェック
		if "amazon.co.jp" in amazon_url or "amzn" in amazon_url:
			fetch_button = True

	st.divider()

	condition = st.selectbox("商品の状態", CONDITION_CHOICES)

	shipping_method = st.selectbox(
		"配送方法",
		list(SHIPPING_METHODS.keys()),
	)

	# 選択した配送方法に応じたサイズ選択
	size_options = list(SHIPPING_METHODS[shipping_method].keys())
	shipping_size = st.selectbox("配送サイズ", size_options)

	shipping_from = st.selectbox("発送元", PREFECTURES, index=12)  # 東京都
	shipping_days = st.selectbox("発送までの日数", SHIPPING_DAYS_CHOICES, index=1)

	use_llm = st.checkbox("Claude APIで説明文を生成", value=True)
	download_images = st.checkbox("画像をダウンロード", value=True)

	# 閉じるボタン
	st.divider()
	if st.button("アプリを終了", use_container_width=True):
		os.kill(os.getpid(), signal.SIGTERM)


# --- 購入履歴取得処理 ---
if order_button:
	progress_container = st.empty()
	try:
		def update_order_progress(msg):
			progress_container.info(f"⏳ {msg}")

		from scraper.order_history import OrderHistoryScraper
		scraper = OrderHistoryScraper(on_progress=update_order_progress)
		st.session_state.order_items = scraper.fetch_orders()
		st.session_state.product = None
		st.session_state.draft = None
		st.session_state.selected_url = ""
		if not st.session_state.order_items:
			progress_container.warning("購入履歴が取得できませんでした。")
		else:
			progress_container.success(f"{len(st.session_state.order_items)}件の商品を取得しました")
	except Exception as e:
		progress_container.error(f"購入履歴取得エラー: {e}")
		st.session_state.order_items = None

# --- 購入履歴表示 ---
if st.session_state.order_items and not st.session_state.product:
	items = st.session_state.order_items

	# 選択中の商品を目立つように表示
	selected_item = None
	if st.session_state.selected_url:
		for item in items:
			if item.url == st.session_state.selected_url:
				selected_item = item
				break

	if selected_item:
		st.subheader("選択中の商品")
		sel_cols = st.columns([1, 3])
		with sel_cols[0]:
			if selected_item.image_url:
				st.image(selected_item.image_url, use_container_width=True)
		with sel_cols[1]:
			st.markdown(f"### {selected_item.title}")
			info_parts = []
			if selected_item.price:
				info_parts.append(f"**購入価格:** ¥{selected_item.price:,}")
			if selected_item.order_date:
				info_parts.append(f"**注文日:** {selected_item.order_date}")
			if info_parts:
				st.markdown(" / ".join(info_parts))
			btn_cols = st.columns([1, 1, 2])
			with btn_cols[0]:
				draft_btn = st.empty()
				if draft_btn.button("下書きを生成", type="primary", use_container_width=True):
					draft_btn.markdown(
						'<div style="background:#1a73e8;color:#fff;padding:10px 16px;'
						'border-radius:8px;text-align:center;font-weight:bold;'
						'animation:pulse 1.5s ease-in-out infinite">'
						'⏳ 下書き生成中...'
						'</div>'
						'<style>@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}</style>',
						unsafe_allow_html=True,
					)
					fetch_button = True
					amazon_url = st.session_state.selected_url
					st.session_state.last_fetched_url = ""  # 強制取得
			with btn_cols[1]:
				if st.button("選択を解除", use_container_width=True):
					st.session_state.selected_url = ""
					st.rerun()
		st.divider()

	# ページネーション
	items_per_page = 9
	if "order_page" not in st.session_state:
		st.session_state.order_page = 0
	total_pages = max(1, (len(items) + items_per_page - 1) // items_per_page)
	page = st.session_state.order_page
	page_start = page * items_per_page
	page_end = min(page_start + items_per_page, len(items))
	page_items = items[page_start:page_end]

	st.subheader(f"購入履歴（{len(items)}件 / {page + 1}/{total_pages}ページ）")

	# ページ送りボタン（一覧の上に配置）
	if total_pages > 1:
		nav_cols = st.columns([1, 2, 1])
		with nav_cols[0]:
			if page > 0:
				if st.button("← 前のページ", use_container_width=True):
					st.session_state.order_page = page - 1
					st.rerun()
		with nav_cols[2]:
			if page < total_pages - 1:
				if st.button("次のページ →", use_container_width=True):
					st.session_state.order_page = page + 1
					st.rerun()

	# 3列グリッドで表示（カード型・クリックで選択）
	cols_per_row = 3
	for row_start in range(0, len(page_items), cols_per_row):
		cols = st.columns(cols_per_row)
		for col_idx, item in enumerate(page_items[row_start:row_start + cols_per_row]):
			with cols[col_idx]:
				is_selected = (st.session_state.selected_url == item.url)
				with st.container(border=True):
					if item.image_url:
						st.image(item.image_url, use_container_width=True)
					st.markdown(f"**{item.title[:60]}{'...' if len(item.title) > 60 else ''}**")
					details = []
					if item.price:
						details.append(f"¥{item.price:,}")
					if item.order_date:
						details.append(item.order_date)
					if details:
						st.caption(" / ".join(details))
					if is_selected:
						if st.button("✓ 選択中", key=f"order_{item.asin}", type="primary", use_container_width=True):
							st.session_state.selected_url = ""
							st.rerun()
					else:
						if st.button("選択", key=f"order_{item.asin}", use_container_width=True):
							st.session_state.selected_url = item.url
							st.rerun()


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

	# LLMで出品テキスト生成
	if st.session_state.product and use_llm:
		with st.spinner("Claude APIで出品テキストを生成中..."):
			try:
				from generator.listing_generator import ListingGenerator
				generator = ListingGenerator()
				draft = generator.generate(
					st.session_state.product,
					condition=condition,
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
				st.warning(f"LLM生成エラー: {e}。基本テンプレートを使用します。")
				use_llm = False

	# LLMなしの場合は基本テンプレート
	if st.session_state.product and not use_llm:
		from main import create_basic_draft
		st.session_state.draft = create_basic_draft(
			st.session_state.product,
			condition, shipping_from, shipping_method, shipping_size, shipping_days,
		)

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
	# 一覧に戻るボタン
	if st.button("← 一覧に戻る"):
		st.session_state.product = None
		st.session_state.draft = None
		st.session_state.selected_url = ""
		st.rerun()

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

		# 編集可能フォーム
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
			# セッション状態で選択状態を初期化（全未選択）
			if "selected_images" not in st.session_state or len(st.session_state.selected_images) != len(draft.image_paths):
				st.session_state.selected_images = [False] * len(draft.image_paths)

			selected_count = sum(st.session_state.selected_images)
			st.markdown(f"**画像:** {selected_count}/{len(draft.image_paths)}枚 選択中")

			with st.expander("画像を選択", expanded=True):
				# 全選択/全解除ボタン
				sel_cols = st.columns(2)
				with sel_cols[0]:
					if st.button("すべて選択", use_container_width=True):
						st.session_state.selected_images = [True] * len(draft.image_paths)
						st.rerun()
				with sel_cols[1]:
					if st.button("すべて解除", use_container_width=True):
						st.session_state.selected_images = [False] * len(draft.image_paths)
						st.rerun()

				# 画像グリッド（チェックボックス付き）
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
		if st.button("🛒 メルカリに自動入力", use_container_width=True):
			# 選択された画像のみをドラフトに設定
			if draft.image_paths and "selected_images" in st.session_state:
				draft.image_paths = [
					p for p, sel in zip(draft.image_paths, st.session_state.selected_images) if sel
				]
			progress_container = st.empty()
			try:
				def update_progress(msg):
					progress_container.info(f"⏳ {msg}")

				from output.mercari_filler import MercariFiller
				filler = MercariFiller(on_progress=update_progress)
				filler.fill_listing(draft, wait_for_close=False)
				progress_container.success("メルカリ出品フォームに入力しました。内容を確認して出品してください。")
			except Exception as e:
				progress_container.error(f"自動入力エラー: {e}")

elif not st.session_state.product and not st.session_state.order_items:
	st.info("サイドバーからURL入力または購入履歴から商品を指定してください。")

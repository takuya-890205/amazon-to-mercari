"""アプリケーション設定"""

from pathlib import Path

# --- パス設定 ---
PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / "data"
DOWNLOAD_DIR = PROJECT_DIR / "downloads"

# --- Amazon設定 ---
AMAZON_BASE_URL = "https://www.amazon.co.jp"
ASIN_PATTERN = r"/dp/([A-Z0-9]{10})"
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL_MIN = 2.0
REQUEST_INTERVAL_MAX = 5.0

# --- Amazonセレクタ（優先度順） ---
SELECTORS = {
	"title": [
		"#productTitle",
		"#title span",
		"h1.a-size-large",
	],
	"price": [
		".a-price .a-offscreen",
		"#priceblock_ourprice",
		"#priceblock_dealprice",
		"#corePrice_feature_div .a-offscreen",
		".a-price-whole",
	],
	"images": [
		"#imgTagWrapperId img",
		"#imageBlock img",
		"#landingImage",
	],
	"bullet_points": [
		"#feature-bullets .a-list-item",
		"#featurebullets_feature_div .a-list-item",
	],
	"description": [
		"#productDescription p",
		"#productDescription span",
		"#productDescription",
	],
	"specifications": [
		"#productDetails_techSpec_section_1 tr",
		"#detailBullets_feature_div li",
		"table.a-keyvalue tr",
	],
	"category": [
		"#wayfinding-breadcrumbs_container a",
		".a-breadcrumb a",
	],
	"brand": [
		"#bylineInfo",
		"a#brand",
		".po-brand .a-span9 span",
	],
}

# --- メルカリ制約 ---
MERCARI_TITLE_MAX = 40
MERCARI_DESC_MAX = 1000
MERCARI_IMAGE_MAX = 10
MERCARI_PRICE_MIN = 300
MERCARI_PRICE_MAX = 9_999_999
MERCARI_FEE_RATE = 0.10

# --- 画像最適化設定 ---
IMAGE_MAX_SIZE = (1080, 1080)
IMAGE_QUALITY = 85
IMAGE_FORMAT = "JPEG"

# --- 商品状態 ---
CONDITION_CHOICES = [
	"新品、未使用",
	"未使用に近い",
	"目立った傷や汚れなし",
	"やや傷や汚れあり",
	"傷や汚れあり",
	"全体的に状態が悪い",
]

# --- 状態別価格倍率（Amazon価格に対する割合） ---
CONDITION_PRICE_RATIO = {
	"新品、未使用": 0.90,
	"未使用に近い": 0.80,
	"目立った傷や汚れなし": 0.65,
	"やや傷や汚れあり": 0.50,
	"傷や汚れあり": 0.35,
	"全体的に状態が悪い": 0.20,
}

# --- 配送方法と送料 ---
SHIPPING_METHODS = {
	"らくらくメルカリ便": {
		"ネコポス": 210,
		"宅急便コンパクト": 450,
		"60サイズ": 750,
		"80サイズ": 850,
		"100サイズ": 1050,
		"120サイズ": 1200,
		"140サイズ": 1450,
		"160サイズ": 1700,
	},
	"ゆうゆうメルカリ便": {
		"ゆうパケット": 230,
		"ゆうパケットポスト": 215,
		"ゆうパック60": 770,
		"ゆうパック80": 870,
		"ゆうパック100": 1070,
	},
}

# --- 発送までの日数 ---
SHIPPING_DAYS_CHOICES = [
	"1~2日で発送",
	"2~3日で発送",
	"4~7日で発送",
]

# --- 都道府県一覧 ---
PREFECTURES = [
	"北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
	"茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
	"新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
	"岐阜県", "静岡県", "愛知県", "三重県",
	"滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
	"鳥取県", "島根県", "岡山県", "広島県", "山口県",
	"徳島県", "香川県", "愛媛県", "高知県",
	"福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

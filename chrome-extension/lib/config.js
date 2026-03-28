/**
 * アプリケーション設定（config.py からの移植）
 */

// --- Amazonセレクタ（優先度順） ---
const SELECTORS = {
	title: [
		"#productTitle",
		"#title span",
		"h1.a-size-large",
	],
	price: [
		".a-price .a-offscreen",
		"#priceblock_ourprice",
		"#priceblock_dealprice",
		"#corePrice_feature_div .a-offscreen",
		".a-price-whole",
	],
	images: [
		"#imgTagWrapperId img",
		"#imageBlock img",
		"#landingImage",
	],
	bulletPoints: [
		"#feature-bullets .a-list-item",
		"#featurebullets_feature_div .a-list-item",
	],
	description: [
		"#productDescription p",
		"#productDescription span",
		"#productDescription",
	],
	specifications: [
		"#productDetails_techSpec_section_1 tr",
		"#detailBullets_feature_div li",
		"table.a-keyvalue tr",
	],
	category: [
		"#wayfinding-breadcrumbs_container a",
		".a-breadcrumb a",
	],
	brand: [
		"#bylineInfo",
		"a#brand",
		".po-brand .a-span9 span",
	],
};

// --- メルカリ制約 ---
const MERCARI_TITLE_MAX = 40;
const MERCARI_DESC_MAX = 1000;
const MERCARI_PRICE_MIN = 300;
const MERCARI_PRICE_MAX = 9_999_999;
const MERCARI_FEE_RATE = 0.10;

// --- ASIN抽出パターン ---
const ASIN_PATTERN = /\/dp\/([A-Z0-9]{10})/;

// --- 商品状態 ---
const CONDITION_CHOICES = [
	"新品、未使用",
	"未使用に近い",
	"目立った傷や汚れなし",
	"やや傷や汚れあり",
	"傷や汚れあり",
	"全体的に状態が悪い",
];

// --- 状態別価格倍率（Amazon価格に対する割合） ---
const CONDITION_PRICE_RATIO = {
	"新品、未使用": 0.90,
	"未使用に近い": 0.80,
	"目立った傷や汚れなし": 0.65,
	"やや傷や汚れあり": 0.50,
	"傷や汚れあり": 0.35,
	"全体的に状態が悪い": 0.20,
};

// --- 配送方法と送料 ---
const SHIPPING_METHODS = {
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
};

// --- デフォルト設定 ---
const DEFAULT_SETTINGS = {
	condition: "目立った傷や汚れなし",
	shippingMethod: "らくらくメルカリ便",
	shippingSize: "60サイズ",
	shippingFrom: "東京都",
	shippingDays: "2~3日で発送",
	descriptionHeader: "",
	descriptionFooter: "\nご質問はお気軽にコメントください。",
	priceRatios: {
		"新品、未使用": 90,
		"未使用に近い": 80,
		"目立った傷や汚れなし": 65,
		"やや傷や汚れあり": 50,
		"傷や汚れあり": 35,
		"全体的に状態が悪い": 20,
	},
};

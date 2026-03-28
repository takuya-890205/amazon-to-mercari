/**
 * Chrome拡張ロジックのユニットテスト
 */
const fs = require("fs");
const vm = require("vm");

// ライブラリを結合して1つのコンテキストで実行
const code = [
	fs.readFileSync("lib/config.js", "utf8"),
	fs.readFileSync("lib/price_calculator.js", "utf8"),
	fs.readFileSync("lib/category_mapper.js", "utf8"),
].join("\n");

const ctx = vm.createContext({
	console, JSON, Math, Object, Array, parseInt, isNaN, Set, String,
});
vm.runInContext(code, ctx);

// テスト用ヘルパー
let pass = 0, fail = 0;
function check(result, msg) {
	if (result) {
		console.log("PASS", msg);
		pass++;
	} else {
		console.log("FAIL", msg);
		fail++;
	}
}

// テスト実行用の関数を注入
vm.runInContext(`
	globalThis._calculatePrice = calculatePrice;
	globalThis._suggestPriceRange = suggestPriceRange;
	globalThis._mapCategory = mapCategory;
	globalThis._CONDITION_CHOICES = CONDITION_CHOICES;
	globalThis._MERCARI_TITLE_MAX = MERCARI_TITLE_MAX;
	globalThis._MERCARI_PRICE_MIN = MERCARI_PRICE_MIN;
	globalThis._MERCARI_FEE_RATE = MERCARI_FEE_RATE;
	globalThis._SHIPPING_METHODS = SHIPPING_METHODS;
`, ctx);

const calc = ctx._calculatePrice;
const range = ctx._suggestPriceRange;
const cat = ctx._mapCategory;

// === 価格計算テスト ===
console.log("=== 価格計算テスト ===");
check(calc(10000, "新品、未使用").suggestedPrice === 9000, "新品 10000円 => 9000円");
check(calc(10000, "目立った傷や汚れなし").suggestedPrice === 6500, "傷なし 10000円 => 6500円");
check(calc(10000, "やや傷や汚れあり").suggestedPrice === 5000, "やや傷 10000円 => 5000円");
check(calc(200, "全体的に状態が悪い").suggestedPrice === 300, "200円 => 最低価格300円");

// 利益計算
const r1 = calc(10000, "目立った傷や汚れなし");
check(r1.mercariFee === 650, "手数料 10% = 650");
check(r1.shippingCost === 750, "送料 60サイズ = 750");
check(r1.estimatedProfit === 6500 - 650 - 750, "利益 = 5100");

// カスタム割引率
const r2 = calc(10000, "新品、未使用", "らくらくメルカリ便", "60サイズ", {"新品、未使用": 70});
check(r2.suggestedPrice === 7000, "カスタム割引率 70% => 7000円");

// === 価格範囲テスト ===
console.log("\n=== 価格範囲テスト ===");
const rng = range(10000, "目立った傷や汚れなし");
check(rng.low === 5200, "low = 5200");
check(rng.recommended === 6500, "recommended = 6500");
check(rng.high === 7800, "high = 7800");

// === カテゴリマッピングテスト ===
console.log("\n=== カテゴリマッピングテスト ===");
check(cat({title:"SONY ワイヤレスイヤホン", brand:"SONY", categoryBreadcrumb:[]})[0] === "テレビ・オーディオ・カメラ", "イヤホン => テレビ・オーディオ");
check(cat({title:"Nintendo Switch", brand:"Nintendo", categoryBreadcrumb:[]})[0] === "ゲーム・おもちゃ・グッズ", "Switch => ゲーム");
check(cat({title:"UGREEN USB充電器", brand:"UGREEN", categoryBreadcrumb:[]})[0] === "スマホ・タブレット・パソコン", "充電器 => スマホ");
check(cat({title:"ダイソン 掃除機", brand:"Dyson", categoryBreadcrumb:[]})[0] === "生活家電・空調", "掃除機 => 生活家電");
check(cat({title:"不明な商品", brand:"", categoryBreadcrumb:["本","コミック"]})[0] === "本・雑誌・漫画", "コミックキーワードマッチ");
check(cat({title:"不明な商品xyz", brand:"", categoryBreadcrumb:["家電","テスト"]})[0] === "家電", "breadcrumbフォールバック");
check(cat({title:"不明な商品", brand:"", categoryBreadcrumb:[]})[0] === "その他", "デフォルト => その他");

// === 定数チェック ===
console.log("\n=== 定数チェック ===");
check(ctx._CONDITION_CHOICES.length === 6, "商品状態 6種類");
check(ctx._MERCARI_TITLE_MAX === 40, "タイトル上限 40文字");
check(ctx._MERCARI_PRICE_MIN === 300, "最低価格 300円");
check(ctx._MERCARI_FEE_RATE === 0.10, "手数料 10%");
check(Object.keys(ctx._SHIPPING_METHODS).length === 2, "配送方法 2種類");
check(Object.keys(ctx._SHIPPING_METHODS["らくらくメルカリ便"]).length === 8, "らくらく 8サイズ");

// === manifest.json 検証 ===
console.log("\n=== manifest.json 検証 ===");
const manifest = JSON.parse(fs.readFileSync("manifest.json", "utf8"));
check(manifest.manifest_version === 3, "Manifest V3");
check(!!manifest.background?.service_worker, "service_worker 設定あり");
check(Array.isArray(manifest.content_scripts) && manifest.content_scripts.length >= 2, "content_scripts 2つ以上");
check(!!manifest.action?.default_popup, "popup 設定あり");
check(manifest.permissions.includes("storage"), "storage 権限あり");
check(manifest.host_permissions.some(h => h.includes("amazon.co.jp")), "amazon.co.jp ホスト権限");
check(manifest.host_permissions.some(h => h.includes("mercari.com")), "mercari.com ホスト権限");
check(manifest.host_permissions.some(h => h.includes("generativelanguage.googleapis.com")), "Gemini API ホスト権限");

// === 結果 ===
console.log("\n" + "=".repeat(40));
console.log(`結果: ${pass} PASS / ${fail} FAIL`);
if (fail > 0) process.exit(1);

/**
 * Background Service Worker
 * Gemini API呼び出しと価格計算を担当
 */

// lib/ のスクリプトはcontent scriptとしてのみ読み込まれるため、
// service worker では直接定義を持つ必要がある
// → importScripts は Manifest V3 の module worker では使えないため、
//   必要な定数・関数をここに含める

// --- 定数 ---
const GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent";

const SW_MERCARI_FEE_RATE = 0.10;
const SW_MERCARI_PRICE_MIN = 300;
const SW_CONDITION_PRICE_RATIO = {
	"新品、未使用": 0.90,
	"未使用に近い": 0.80,
	"目立った傷や汚れなし": 0.65,
	"やや傷や汚れあり": 0.50,
	"傷や汚れあり": 0.35,
	"全体的に状態が悪い": 0.20,
};
const SW_SHIPPING_METHODS = {
	"らくらくメルカリ便": { "ネコポス": 210, "宅急便コンパクト": 450, "60サイズ": 750, "80サイズ": 850, "100サイズ": 1050, "120サイズ": 1200, "140サイズ": 1450, "160サイズ": 1700 },
	"ゆうゆうメルカリ便": { "ゆうパケット": 230, "ゆうパケットポスト": 215, "ゆうパック60": 770, "ゆうパック80": 870, "ゆうパック100": 1070 },
};

// --- SPA遷移検知: tabs.onUpdatedでURL変化を監視し、/sell/createへの遷移時にcontent scriptを再注入 ---
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
	if (changeInfo.url && changeInfo.url.includes("jp.mercari.com/sell/create")) {
		chrome.storage.local.get("pendingDraft", (result) => {
			if (result.pendingDraft) {
				// 重複実行防止フラグをリセットしてから再注入
				chrome.scripting.executeScript({
					target: { tabId },
					func: () => { window.__atm_initialized = false; },
				}).then(() => {
					return chrome.scripting.executeScript({
						target: { tabId },
						files: ["content/mercari.js"],
					});
				}).catch(() => {}); // 権限エラー等は無視
			}
		});
	}
});

// --- メッセージリスナー ---
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
	if (request.action === "generateListing") {
		handleGenerateListing(request.product)
			.then(draft => sendResponse({ success: true, draft }))
			.catch(err => sendResponse({ success: false, error: err.message }));
		return true; // 非同期レスポンスを示す
	}
});

/**
 * 出品テキスト生成のメイン処理
 */
async function handleGenerateListing(product) {
	// 設定を読み込む
	const settings = await getSettings();
	const apiKey = settings.apiKey;

	if (!apiKey) {
		throw new Error("APIキーが設定されていません。拡張機能のポップアップから設定してください。");
	}

	// Gemini APIで出品テキスト生成
	const aiResult = await callGeminiApi(apiKey, product, settings);

	// 価格計算
	let priceBreakdown = null;
	if (product.price) {
		const ratio = resolveRatioSW(settings.condition, settings.priceRatios);
		let suggestedPrice = Math.floor(product.price * ratio);
		const methodCosts = SW_SHIPPING_METHODS[settings.shippingMethod] || {};
		const shippingCost = methodCosts[settings.shippingSize] || 750;
		let mercariFee = Math.floor(suggestedPrice * SW_MERCARI_FEE_RATE);
		if (suggestedPrice < SW_MERCARI_PRICE_MIN) suggestedPrice = SW_MERCARI_PRICE_MIN;
		mercariFee = Math.floor(suggestedPrice * SW_MERCARI_FEE_RATE);
		const estimatedProfit = suggestedPrice - mercariFee - shippingCost;

		priceBreakdown = {
			amazonPrice: product.price,
			suggestedPrice,
			mercariFee,
			shippingCost,
			estimatedProfit,
		};
	}

	// 下書きオブジェクトを構築
	return {
		title: aiResult.title || product.title.substring(0, 40),
		description: aiResult.description || "",
		category: aiResult.category || [],
		brand: product.brand || "",
		condition: settings.condition,
		shippingPayer: "送料込み(出品者負担)",
		shippingMethod: settings.shippingMethod,
		shippingFrom: settings.shippingFrom,
		shippingDays: settings.shippingDays,
		price: priceBreakdown ? priceBreakdown.suggestedPrice : 0,
		priceBreakdown,
		hashtags: aiResult.hashtags || [],
		sourceUrl: product.url,
	};
}

function resolveRatioSW(condition, customRatios) {
	if (customRatios && condition in customRatios) {
		return customRatios[condition] / 100;
	}
	return SW_CONDITION_PRICE_RATIO[condition] || 0.65;
}

/**
 * Gemini API を呼び出して出品テキストを生成
 */
async function callGeminiApi(apiKey, product, settings) {
	// プロンプトを構築
	const bulletText = (product.bulletPoints || []).slice(0, 5).map(bp => `・${bp}`).join("\n") || "なし";
	const specText = Object.entries(product.specifications || {}).slice(0, 10).map(([k, v]) => `・${k}: ${v}`).join("\n") || "なし";
	const categoryText = (product.categoryBreadcrumb || []).join(" > ") || "不明";

	const tplParts = [];
	if (settings.descriptionHeader) tplParts.push(`説明文の冒頭に次の内容を含めてください: 「${settings.descriptionHeader.trim()}」`);
	if (settings.descriptionFooter) tplParts.push(`説明文の末尾に次の内容を含めてください: 「${settings.descriptionFooter.trim()}」`);

	const prompt = `あなたはメルカリ出品のプロです。以下のAmazon商品情報を基に、メルカリ出品用の情報を生成してください。

【Amazon商品情報】
タイトル: ${product.title}
ブランド: ${product.brand || "不明"}
価格: ${product.price || "不明"}円
カテゴリ: ${categoryText}
説明: ${product.description || "なし"}
特徴:
${bulletText}
仕様:
${specText}

【出品条件】
商品の状態: ${settings.condition}

【テンプレート指示】
${tplParts.length > 0 ? tplParts.join("\n") : "特になし"}

【生成ルール】
1. タイトル: 必ず40文字以内。ブランド名+商品の種類+最大の魅力。
2. 説明文: 最大1000文字。状態→付属品→概要→特徴の順。
3. カテゴリ: メルカリの3階層 [大, 中, 小]
4. ハッシュタグ: 5-8個

【出力形式】JSON形式のみ:
{"title":"...","description":"...","category":["大","中","小"],"hashtags":["tag1","tag2"]}`;

	const response = await fetch(`${GEMINI_API_URL}?key=${apiKey}`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			contents: [{ parts: [{ text: prompt }] }],
		}),
	});

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}));
		throw new Error(`Gemini API エラー (${response.status}): ${errorData.error?.message || response.statusText}`);
	}

	const data = await response.json();
	const text = data.candidates?.[0]?.content?.parts?.[0]?.text || "";

	return parseGeminiResponse(text);
}

/**
 * Gemini APIのレスポンスからJSONを抽出
 */
function parseGeminiResponse(text) {
	text = text.trim();

	// ```json ... ``` ブロックを抽出
	if (text.includes("```json")) {
		text = text.split("```json")[1].split("```")[0].trim();
	} else if (text.includes("```")) {
		text = text.split("```")[1].split("```")[0].trim();
	}

	try {
		return JSON.parse(text);
	} catch(e) {
		// { から } までを切り出してリトライ
		const start = text.indexOf("{");
		const end = text.lastIndexOf("}") + 1;
		if (start >= 0 && end > start) {
			try {
				return JSON.parse(text.substring(start, end));
			} catch(e2) { /* パース失敗 */ }
		}
	}

	console.warn("[ATM] JSONパースに失敗。デフォルト値を使用。");
	return {};
}

/**
 * 設定をストレージから読み込む
 */
async function getSettings() {
	return new Promise((resolve) => {
		chrome.storage.sync.get({
			apiKey: "",
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
		}, resolve);
	});
}

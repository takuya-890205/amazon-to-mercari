/**
 * ポップアップUI のロジック
 */

const $ = (sel) => document.querySelector(sel);

// --- 要素取得 ---
const apiKeyInput = $("#apiKey");
const toggleKeyBtn = $("#toggleKey");
const conditionSelect = $("#condition");
const shippingMethodSelect = $("#shippingMethod");
const shippingSizeSelect = $("#shippingSize");
const shippingFromSelect = $("#shippingFrom");
const descHeaderInput = $("#descHeader");
const descFooterInput = $("#descFooter");
const saveBtn = $("#saveBtn");
const statusEl = $("#status");

// --- 配送サイズ選択肢の更新 ---
const shippingSizes = {
	"らくらくメルカリ便": [
		{ value: "ネコポス", label: "ネコポス (210円)" },
		{ value: "宅急便コンパクト", label: "宅急便コンパクト (450円)" },
		{ value: "60サイズ", label: "60サイズ (750円)" },
		{ value: "80サイズ", label: "80サイズ (850円)" },
		{ value: "100サイズ", label: "100サイズ (1,050円)" },
		{ value: "120サイズ", label: "120サイズ (1,200円)" },
		{ value: "140サイズ", label: "140サイズ (1,450円)" },
		{ value: "160サイズ", label: "160サイズ (1,700円)" },
	],
	"ゆうゆうメルカリ便": [
		{ value: "ゆうパケット", label: "ゆうパケット (230円)" },
		{ value: "ゆうパケットポスト", label: "ゆうパケットポスト (215円)" },
		{ value: "ゆうパック60", label: "ゆうパック60 (770円)" },
		{ value: "ゆうパック80", label: "ゆうパック80 (870円)" },
		{ value: "ゆうパック100", label: "ゆうパック100 (1,070円)" },
	],
};

function updateShippingSizes(method, currentSize = "") {
	shippingSizeSelect.innerHTML = "";
	const sizes = shippingSizes[method] || [];
	sizes.forEach(({ value, label }) => {
		const opt = document.createElement("option");
		opt.value = value;
		opt.textContent = label;
		if (value === currentSize) opt.selected = true;
		shippingSizeSelect.appendChild(opt);
	});
}

shippingMethodSelect.addEventListener("change", () => {
	updateShippingSizes(shippingMethodSelect.value);
});

// --- APIキー表示切替 ---
toggleKeyBtn.addEventListener("click", () => {
	apiKeyInput.type = apiKeyInput.type === "password" ? "text" : "password";
});

// --- 設定の読み込み ---
chrome.storage.sync.get({
	apiKey: "",
	condition: "目立った傷や汚れなし",
	shippingMethod: "らくらくメルカリ便",
	shippingSize: "60サイズ",
	shippingFrom: "東京都",
	descriptionHeader: "",
	descriptionFooter: "\nご質問はお気軽にコメントください。",
}, (settings) => {
	apiKeyInput.value = settings.apiKey;
	conditionSelect.value = settings.condition;
	shippingMethodSelect.value = settings.shippingMethod;
	updateShippingSizes(settings.shippingMethod, settings.shippingSize);
	shippingFromSelect.value = settings.shippingFrom;
	descHeaderInput.value = settings.descriptionHeader;
	descFooterInput.value = settings.descriptionFooter;
});

// --- 設定の保存 ---
saveBtn.addEventListener("click", () => {
	const settings = {
		apiKey: apiKeyInput.value.trim(),
		condition: conditionSelect.value,
		shippingMethod: shippingMethodSelect.value,
		shippingSize: shippingSizeSelect.value,
		shippingFrom: shippingFromSelect.value,
		descriptionHeader: descHeaderInput.value,
		descriptionFooter: descFooterInput.value,
	};

	chrome.storage.sync.set(settings, () => {
		statusEl.textContent = "保存しました";
		statusEl.className = "status success";
		setTimeout(() => {
			statusEl.textContent = "";
			statusEl.className = "status";
		}, 2000);
	});
});

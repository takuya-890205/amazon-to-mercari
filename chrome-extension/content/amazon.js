/**
 * Amazon商品ページ用 Content Script
 * 商品情報をDOMから抽出し、「メルカリに出品」ボタンを注入する
 */

(function() {
	"use strict";

	// 商品ページかどうか判定（/dp/ を含むURLのみ対象）
	if (!ASIN_PATTERN.test(location.pathname)) return;

	/**
	 * セレクタリストから最初にマッチする要素のテキストを取得
	 */
	function queryText(selectorList) {
		for (const selector of selectorList) {
			const el = document.querySelector(selector);
			if (el) {
				const text = el.textContent.trim();
				if (text) return text;
			}
		}
		return "";
	}

	/**
	 * セレクタリストから全マッチ要素のテキスト配列を取得
	 */
	function queryAllTexts(selectorList) {
		for (const selector of selectorList) {
			const els = document.querySelectorAll(selector);
			if (els.length > 0) {
				return Array.from(els)
					.map(el => el.textContent.trim())
					.filter(t => t && !t.includes("ここに記載の内容"));
			}
		}
		return [];
	}

	/**
	 * Amazon商品ページからASINを抽出
	 */
	function extractAsin() {
		const match = location.pathname.match(ASIN_PATTERN);
		return match ? match[1] : "";
	}

	/**
	 * 価格文字列から数値を抽出（例: "￥3,980" → 3980）
	 */
	function parsePrice(priceText) {
		if (!priceText) return null;
		const cleaned = priceText.replace(/[^\d]/g, "");
		const num = parseInt(cleaned, 10);
		return isNaN(num) ? null : num;
	}

	/**
	 * 商品画像URLを取得（高解像度版を優先）
	 */
	function extractImageUrls() {
		const urls = new Set();
		for (const selector of SELECTORS.images) {
			const imgs = document.querySelectorAll(selector);
			for (const img of imgs) {
				let src = img.getAttribute("data-old-hires") || img.getAttribute("data-a-dynamic-image") || img.src;
				// data-a-dynamic-image はJSONオブジェクト形式の場合がある
				if (src && src.startsWith("{")) {
					try {
						const parsed = JSON.parse(src);
						const highRes = Object.keys(parsed).sort((a, b) => {
							const sizeA = parsed[a][0] * parsed[a][1];
							const sizeB = parsed[b][0] * parsed[b][1];
							return sizeB - sizeA;
						});
						if (highRes.length > 0) src = highRes[0];
					} catch(e) { /* JSONパース失敗時はsrcをそのまま使用 */ }
				}
				if (src && src.startsWith("http") && !src.includes("sprite") && !src.includes("grey-pixel")) {
					// 高解像度版に変換（_SX/SL を大きいサイズに）
					const hiRes = src.replace(/\._[A-Z]{2}\d+_\./, "._SL1500_.");
					urls.add(hiRes);
				}
			}
			if (urls.size > 0) break;
		}
		return Array.from(urls).slice(0, 10);
	}

	/**
	 * 仕様テーブルから key-value を抽出
	 */
	function extractSpecifications() {
		const specs = {};
		for (const selector of SELECTORS.specifications) {
			const rows = document.querySelectorAll(selector);
			if (rows.length > 0) {
				rows.forEach(row => {
					const th = row.querySelector("th, .a-text-bold");
					const td = row.querySelector("td, .a-list-item span:last-child");
					if (th && td) {
						const key = th.textContent.trim().replace(/[\s\u200f\u200e:：]/g, "");
						const val = td.textContent.trim();
						if (key && val) specs[key] = val;
					}
				});
				break;
			}
		}
		return specs;
	}

	/**
	 * Amazon商品情報を全て抽出
	 */
	function scrapeProduct() {
		return {
			asin: extractAsin(),
			url: location.href,
			title: queryText(SELECTORS.title),
			price: parsePrice(queryText(SELECTORS.price)),
			description: queryText(SELECTORS.description),
			bulletPoints: queryAllTexts(SELECTORS.bulletPoints),
			specifications: extractSpecifications(),
			imageUrls: extractImageUrls(),
			categoryBreadcrumb: queryAllTexts(SELECTORS.category),
			brand: queryText(SELECTORS.brand).replace(/ブランド:\s*/, "").replace(/Visit the .* Store/, "").trim(),
		};
	}

	/**
	 * 「メルカリに出品」ボタンを商品ページに注入
	 */
	function injectButton() {
		// 既にボタンがあれば何もしない
		if (document.getElementById("atm-mercari-host")) return;

		// Shadow DOMでAmazonのCSSから完全に隔離
		const host = document.createElement("div");
		host.id = "atm-mercari-host";
		host.style.cssText = "all: initial; display: block; margin: 12px 0; padding: 0 4px;";
		const shadow = host.attachShadow({ mode: "open" });

		shadow.innerHTML = `
			<style>
				button {
					all: initial;
					background: #FF0211;
					color: white;
					border: none;
					border-radius: 8px;
					padding: 12px 24px;
					font-size: 16px;
					font-weight: bold;
					font-family: "Hiragino Sans", "Yu Gothic", sans-serif;
					cursor: pointer;
					width: 100%;
					min-height: 44px;
					display: block;
					box-sizing: border-box;
					line-height: 1.2;
					text-align: center;
					letter-spacing: 0.5px;
					box-shadow: 0 2px 4px rgba(0,0,0,0.2);
					transition: opacity 0.2s;
				}
				button:hover { opacity: 0.85; }
				button:disabled { opacity: 0.6; cursor: wait; }
			</style>
			<button id="atm-btn">メルカリに出品</button>
		`;

		const btn = shadow.getElementById("atm-btn");

		btn.addEventListener("click", async () => {
			btn.disabled = true;
			btn.textContent = "生成中...";

			const product = scrapeProduct();

			// タイムアウト（90秒）: service workerが応答しない場合の保険
			const timeout = setTimeout(() => {
				btn.disabled = false;
				btn.textContent = "メルカリに出品";
				alert("生成がタイムアウトしました。もう一度お試しください。");
			}, 90000);

			// background script にメッセージを送信
			chrome.runtime.sendMessage(
				{ action: "generateListing", product },
				(response) => {
					clearTimeout(timeout);
					btn.disabled = false;
					btn.textContent = "メルカリに出品";

					// service workerとの通信エラー
					if (chrome.runtime.lastError) {
						alert(`通信エラー: ${chrome.runtime.lastError.message}\nページをリロードして再試行してください。`);
						return;
					}

					if (response && response.success) {
						// 生成結果をストレージに保存してメルカリページを開く
						chrome.storage.local.set({ pendingDraft: response.draft }, () => {
							window.open("https://jp.mercari.com/sell/create", "_blank");
						});
					} else {
						const errMsg = response?.error || "不明なエラー";
						alert(`生成エラー: ${errMsg}`);
					}
				}
			);
		});

		// ボタンの挿入先を探す（購入ボタン群の下に配置）
		const targets = [
			"#desktop_buybox",
			"#buybox",
			"#addToCart",
			"#rightCol",
		];
		for (const sel of targets) {
			const target = document.querySelector(sel);
			if (target) {
				// 要素の直後（兄弟として）に挿入
				if (target.nextSibling) {
					target.parentNode.insertBefore(host, target.nextSibling);
				} else {
					target.parentNode.appendChild(host);
				}
				return;
			}
		}
	}

	// ページ読み込み完了後にボタンを注入
	injectButton();
})();

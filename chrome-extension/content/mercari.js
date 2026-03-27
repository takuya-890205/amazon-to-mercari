/**
 * メルカリ出品ページ用 Content Script
 * シンプル設計: フォーム要素が見つかったら入力する。ログイン検知・自動遷移は行わない。
 */

(function() {
	"use strict";

	// 重複実行防止
	if (window.__atm_initialized) return;
	window.__atm_initialized = true;

	/**
	 * 指定セレクタの要素が現れるまでMutationObserverで待機
	 */
	function waitForElement(selector, timeout = 10000) {
		return new Promise((resolve, reject) => {
			const el = document.querySelector(selector);
			if (el) return resolve(el);

			const observer = new MutationObserver(() => {
				const el = document.querySelector(selector);
				if (el) {
					observer.disconnect();
					resolve(el);
				}
			});
			observer.observe(document.body, { childList: true, subtree: true });
			setTimeout(() => {
				observer.disconnect();
				reject(new Error(`要素が見つかりません: ${selector}`));
			}, timeout);
		});
	}

	/**
	 * input/textareaに値を設定し、Reactのイベントを発火させる
	 */
	function setInputValue(element, value) {
		const proto = element.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
		const nativeInputValueSetter = Object.getOwnPropertyDescriptor(proto, "value").set;
		nativeInputValueSetter.call(element, value);
		element.dispatchEvent(new Event("input", { bubbles: true }));
		element.dispatchEvent(new Event("change", { bubbles: true }));
	}

	/**
	 * select要素の値を設定し、Reactのイベントを発火させる
	 */
	function setSelectValue(selectElement, value) {
		const nativeSetter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set;
		nativeSetter.call(selectElement, value);
		selectElement.dispatchEvent(new Event("change", { bubbles: true }));
	}

	/**
	 * メルカリのカスタムドロップダウンから値を選択
	 * セレクタで特定したトリガー要素をクリックし、表示されたリストからテキスト一致するアイテムをクリック
	 */
	async function selectFromDropdown(triggerSelector, value, label) {
		// まずネイティブselect要素を試す
		try {
			const selects = document.querySelectorAll("select");
			for (const sel of selects) {
				for (const opt of sel.options) {
					if (opt.text === value || opt.value === value) {
						setSelectValue(sel, opt.value);
						console.log(`[ATM] ${label}: ネイティブselectで設定完了`);
						return true;
					}
				}
			}
		} catch(e) { /* ネイティブselectが無い場合は次へ */ }

		// カスタムUIドロップダウンを試す: ラベルテキストで対象セクションを特定
		try {
			const allLabels = document.querySelectorAll("label, dt, [class*='label'], [class*='Label'], span, div");
			let triggerEl = null;

			for (const el of allLabels) {
				const text = el.textContent.trim();
				if (triggerSelector.some(keyword => text === keyword)) {
					// ラベルの近くにあるボタン/選択要素を探す
					const parent = el.closest("div[class], section, li, [class*='row'], [class*='Row'], [class*='item'], [class*='Item']") || el.parentElement;
					if (parent) {
						triggerEl = parent.querySelector("button, [role='button'], [role='listbox'], [role='combobox'], select, [class*='select'], [class*='Select'], [class*='dropdown'], [class*='Dropdown']");
						if (!triggerEl) {
							// 親要素自体がクリッカブルな場合
							triggerEl = parent.querySelector("div[class*='value'], div[class*='Value'], span[class*='value'], span[class*='Value']");
						}
					}
					if (triggerEl) break;
				}
			}

			if (triggerEl) {
				triggerEl.click();
				await new Promise(r => setTimeout(r, 500));

				// 開いたリストから値を選択
				const listItems = document.querySelectorAll("[role='option'], [role='menuitem'], li, [class*='option'], [class*='Option'], [class*='menuItem'], [class*='MenuItem']");
				for (const item of listItems) {
					if (item.textContent.trim() === value) {
						item.click();
						console.log(`[ATM] ${label}: カスタムUIで設定完了`);
						return true;
					}
				}

				// 閉じる（選択できなかった場合）
				document.body.click();
			}
		} catch(e) {
			console.warn(`[ATM] ${label}: カスタムUI操作エラー:`, e);
		}

		console.warn(`[ATM] ${label}: 設定できませんでした（値: ${value}）`);
		return false;
	}

	/**
	 * 下書きデータをフォームに入力
	 */
	async function fillForm(draft) {
		console.log("[ATM] フォーム自動入力を開始", draft);
		// Next.jsのhydration完了を待つ
		await new Promise(r => setTimeout(r, 2000));

		// タイトル
		try {
			const titleInput = await waitForElement('input[name="name"], input[data-testid="text-input-name"]');
			setInputValue(titleInput, draft.title);
			console.log("[ATM] タイトル入力完了");
		} catch(e) {
			console.warn("[ATM] タイトル入力欄が見つかりません:", e);
		}

		// 説明文
		try {
			const descInput = await waitForElement('textarea[name="description"], textarea[data-testid="textarea-description"]');
			setInputValue(descInput, draft.description);
			console.log("[ATM] 説明文入力完了");
		} catch(e) {
			console.warn("[ATM] 説明文入力欄が見つかりません:", e);
		}

		// 商品の状態
		if (draft.condition) {
			await selectFromDropdown(["商品の状態"], draft.condition, "商品の状態");
			await new Promise(r => setTimeout(r, 300));
		}

		// 発送元の地域
		if (draft.shippingFrom) {
			await selectFromDropdown(["発送元の地域"], draft.shippingFrom, "発送元の地域");
			await new Promise(r => setTimeout(r, 300));
		}

		// 価格
		if (draft.price) {
			try {
				const priceInput = await waitForElement('input[name="price"], input[data-testid="text-input-price"]');
				setInputValue(priceInput, String(draft.price));
				console.log("[ATM] 価格入力完了");
			} catch(e) {
				console.warn("[ATM] 価格入力欄が見つかりません:", e);
			}
		}

		// pendingDraftを削除して完了通知
		chrome.storage.local.remove("pendingDraft");
		showCompletionNotification(draft);
	}

	/**
	 * 自動入力完了の通知バナー
	 */
	function showCompletionNotification(draft) {
		removeExistingBanners();

		const banner = document.createElement("div");
		banner.id = "atm-notification";
		banner.style.cssText = `
			position: fixed; top: 16px; right: 16px;
			background: #FF0211; color: white;
			padding: 16px 24px; border-radius: 12px;
			box-shadow: 0 4px 12px rgba(0,0,0,0.3);
			z-index: 99999; font-size: 14px;
			max-width: 360px; line-height: 1.5;
			font-family: "Hiragino Sans", "Yu Gothic", sans-serif;
		`;

		const profit = draft.priceBreakdown
			? `利益: ¥${draft.priceBreakdown.estimatedProfit.toLocaleString()}`
			: "";

		banner.innerHTML = `
			<div style="font-weight: bold; margin-bottom: 4px;">Amazon to メルカリ</div>
			<div>出品情報を自動入力しました</div>
			${profit ? `<div style="margin-top: 4px;">${profit}</div>` : ""}
			<div style="margin-top: 8px; font-size: 12px; opacity: 0.8;">
				※ 内容を確認してから出品してください<br>
				※ 写真は自分で撮影したものを使用してください
			</div>
		`;

		document.body.appendChild(banner);
		setTimeout(() => banner.remove(), 8000);
	}

	/**
	 * フローティング通知バナー: 下書きデータの存在を案内
	 */
	function showPendingDraftBanner() {
		removeExistingBanners();

		const banner = document.createElement("div");
		banner.id = "atm-notification";
		banner.style.cssText = `
			position: fixed; top: 16px; right: 16px;
			background: #FF0211; color: white;
			padding: 16px 24px; border-radius: 12px;
			box-shadow: 0 4px 12px rgba(0,0,0,0.3);
			z-index: 99999; font-size: 14px;
			max-width: 400px; line-height: 1.5;
			font-family: "Hiragino Sans", "Yu Gothic", sans-serif;
		`;

		banner.innerHTML = `
			<div style="font-weight: bold; margin-bottom: 8px;">Amazon to メルカリ</div>
			<div>Amazon商品の下書きデータがあります。<br>出品フォームを開くと自動入力されます。</div>
			<div style="margin-top: 12px; display: flex; gap: 8px;">
				<a id="atm-open-form" href="https://jp.mercari.com/sell/create" style="
					background: white; color: #FF0211; text-decoration: none;
					padding: 8px 16px; border-radius: 6px; font-weight: bold;
					font-size: 13px; cursor: pointer; display: inline-block;
				">出品フォームを開く</a>
				<button id="atm-dismiss" style="
					background: transparent; color: white; border: 1px solid rgba(255,255,255,0.5);
					padding: 8px 12px; border-radius: 6px; font-size: 13px; cursor: pointer;
				">閉じる</button>
			</div>
		`;

		document.body.appendChild(banner);

		banner.querySelector("#atm-dismiss").addEventListener("click", () => banner.remove());
	}

	/**
	 * 既存のバナーを削除
	 */
	function removeExistingBanners() {
		const existing = document.getElementById("atm-notification");
		if (existing) existing.remove();
	}

	/**
	 * 出品フォームが現在のページにあるかチェック
	 */
	function isOnListingForm() {
		return location.pathname.startsWith("/sell/create");
	}

	/**
	 * メイン処理
	 */
	function main() {
		chrome.storage.local.get("pendingDraft", (result) => {
			if (!result.pendingDraft) return;

			console.log("[ATM] 下書きデータ検出。現在のパス:", location.pathname);

			if (isOnListingForm()) {
				// 出品フォームにいる → 自動入力
				console.log("[ATM] 出品フォーム検出、自動入力開始");
				fillForm(result.pendingDraft);
			} else {
				// 出品フォーム以外 → 案内バナー表示
				console.log("[ATM] 出品フォーム外、通知バナー表示");
				showPendingDraftBanner();
			}
		});
	}

	// 実行
	main();
})();

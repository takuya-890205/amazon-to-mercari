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
	function selectOption(selectElement, value) {
		const nativeSetter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set;
		nativeSetter.call(selectElement, value);
		selectElement.dispatchEvent(new Event("change", { bubbles: true }));
	}

	/**
	 * 下書きデータをフォームに入力
	 */
	async function fillForm(draft) {
		console.log("[ATM] フォーム自動入力を開始");
		// Next.jsのhydration完了を待つ
		await new Promise(r => setTimeout(r, 2000));

		try {
			const titleInput = await waitForElement('input[name="name"], input[data-testid="text-input-name"]');
			setInputValue(titleInput, draft.title);
			console.log("[ATM] タイトル入力完了");
		} catch(e) {
			console.warn("[ATM] タイトル入力欄が見つかりません:", e);
		}

		try {
			const descInput = await waitForElement('textarea[name="description"], textarea[data-testid="textarea-description"]');
			setInputValue(descInput, draft.description);
			console.log("[ATM] 説明文入力完了");
		} catch(e) {
			console.warn("[ATM] 説明文入力欄が見つかりません:", e);
		}

		if (draft.price) {
			try {
				const priceInput = await waitForElement('input[name="price"], input[data-testid="text-input-price"]');
				setInputValue(priceInput, String(draft.price));
				console.log("[ATM] 価格入力完了");
			} catch(e) {
				console.warn("[ATM] 価格入力欄が見つかりません:", e);
			}
		}

		if (draft.shippingFrom) {
			try {
				const regionSelect = await waitForElement('select[name="shippingFromArea"], select[data-testid="select-shippingFromArea"]');
				selectOption(regionSelect, draft.shippingFrom);
				console.log("[ATM] 発送元の地域入力完了");
			} catch(e) {
				console.warn("[ATM] 発送元の地域選択が見つかりません:", e);
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

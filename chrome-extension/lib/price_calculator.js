/**
 * メルカリ出品価格の計算・提案（price_calculator.py からの移植）
 */

/**
 * カスタム割引率（%整数）またはデフォルト（0〜1小数）から倍率を返す
 */
function resolveRatio(condition, customRatios = null) {
	if (customRatios && condition in customRatios) {
		return customRatios[condition] / 100;
	}
	return CONDITION_PRICE_RATIO[condition] || 0.65;
}

/**
 * Amazon価格からメルカリ出品価格を計算
 */
function calculatePrice(amazonPrice, condition = "新品、未使用", shippingMethod = "らくらくメルカリ便", shippingSize = "60サイズ", customRatios = null) {
	// 商品状態に応じてAmazon価格を割引
	const ratio = resolveRatio(condition, customRatios);
	let suggestedPrice = Math.floor(amazonPrice * ratio);

	// 送料を取得
	const methodCosts = SHIPPING_METHODS[shippingMethod] || {};
	const shippingCost = methodCosts[shippingSize] || 750;

	// メルカリ手数料（出品価格の10%）
	let mercariFee = Math.floor(suggestedPrice * MERCARI_FEE_RATE);

	// 推定利益
	let estimatedProfit = suggestedPrice - mercariFee - shippingCost;

	// 最低価格以上を保証
	if (suggestedPrice < MERCARI_PRICE_MIN) {
		suggestedPrice = MERCARI_PRICE_MIN;
		mercariFee = Math.floor(suggestedPrice * MERCARI_FEE_RATE);
		estimatedProfit = suggestedPrice - mercariFee - shippingCost;
	}

	return {
		amazonPrice,
		suggestedPrice,
		mercariFee,
		shippingCost,
		estimatedProfit,
	};
}

/**
 * 最低価格、推奨価格、最高価格の3段階を提案
 */
function suggestPriceRange(amazonPrice, condition = "新品、未使用", customRatios = null) {
	const ratio = resolveRatio(condition, customRatios);
	const recommended = Math.floor(amazonPrice * ratio);
	const low = Math.max(Math.floor(recommended * 0.80), MERCARI_PRICE_MIN);
	const high = Math.floor(recommended * 1.20);

	return {
		low,
		recommended: Math.max(recommended, MERCARI_PRICE_MIN),
		high,
	};
}

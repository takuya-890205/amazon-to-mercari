"""メルカリ出品価格の計算・提案"""

from config import (
	CONDITION_PRICE_RATIO,
	MERCARI_FEE_RATE,
	MERCARI_PRICE_MIN,
	SHIPPING_METHODS,
)
from scraper.product_data import PriceBreakdown


def calculate_price(
	amazon_price: int,
	condition: str = "新品、未使用",
	shipping_method: str = "らくらくメルカリ便",
	shipping_size: str = "60サイズ",
) -> PriceBreakdown:
	"""Amazon価格からメルカリ出品価格を計算"""
	# Amazon販売価格をそのまま出品価格にする
	suggested = amazon_price

	# 送料を取得
	method_costs = SHIPPING_METHODS.get(shipping_method, {})
	shipping_cost = method_costs.get(shipping_size, 750)

	# メルカリ手数料（出品価格の10%）
	mercari_fee = int(suggested * MERCARI_FEE_RATE)

	# 推定利益
	estimated_profit = suggested - mercari_fee - shipping_cost

	# 最低価格以上を保証
	if suggested < MERCARI_PRICE_MIN:
		suggested = MERCARI_PRICE_MIN
		mercari_fee = int(suggested * MERCARI_FEE_RATE)
		estimated_profit = suggested - mercari_fee - shipping_cost

	return PriceBreakdown(
		amazon_price=amazon_price,
		suggested_price=suggested,
		mercari_fee=mercari_fee,
		shipping_cost=shipping_cost,
		estimated_profit=estimated_profit,
	)


def suggest_price_range(
	amazon_price: int,
	condition: str = "新品、未使用",
) -> tuple[int, int, int]:
	"""最低価格、推奨価格、最高価格の3段階を提案"""
	# Amazon販売価格を基準に、±20%の範囲を提案
	recommended = amazon_price
	low = max(int(recommended * 0.80), MERCARI_PRICE_MIN)
	high = int(recommended * 1.20)

	return low, max(recommended, MERCARI_PRICE_MIN), high

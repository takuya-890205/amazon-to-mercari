"""商品データモデル定義"""

from dataclasses import dataclass, field


@dataclass
class AmazonProduct:
	"""Amazon商品情報"""
	asin: str
	url: str
	title: str
	price: int | None
	description: str
	bullet_points: list[str] = field(default_factory=list)
	specifications: dict[str, str] = field(default_factory=dict)
	image_urls: list[str] = field(default_factory=list)
	category_breadcrumb: list[str] = field(default_factory=list)
	brand: str = ""
	rating: float | None = None
	review_count: int | None = None


@dataclass
class SearchResult:
	"""Amazon検索結果の1商品"""
	asin: str
	title: str
	price: int | None
	image_url: str
	url: str
	rating: float | None = None


@dataclass
class PriceBreakdown:
	"""価格内訳"""
	amazon_price: int
	suggested_price: int
	mercari_fee: int
	shipping_cost: int
	estimated_profit: int


@dataclass
class MercariDraft:
	"""メルカリ出品下書き"""
	title: str
	description: str
	category: list[str] = field(default_factory=list)
	brand: str = ""
	condition: str = "新品、未使用"
	shipping_payer: str = "送料込み(出品者負担)"
	shipping_method: str = "らくらくメルカリ便"
	shipping_from: str = "東京都"
	shipping_days: str = "2~3日で発送"
	price: int = 0
	price_breakdown: PriceBreakdown | None = None
	image_paths: list[str] = field(default_factory=list)
	hashtags: list[str] = field(default_factory=list)
	source_url: str = ""

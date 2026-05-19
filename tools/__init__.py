from services.cosmos_service import CosmosService
from services.search_service import AiSearch

cosmos = CosmosService()
ai_search = AiSearch()


def get_product_details_tool(upc):
	"""Fetch real-time price, stock, and info for a specific UPC."""
	return cosmos.get_enriched_product_info(upc)


def get_shelf_layout_tool(shelf_id):
	"""Fetch planogram layout for a specific shelf."""
	return cosmos.get_shelf_layout(shelf_id)


def search_products_tool(query):
	"""Search products for recommendations."""
	return ai_search.search_text(query, top_k=3)


__all__ = [
	"get_product_details_tool",
	"get_shelf_layout_tool",
	"search_products_tool",
]

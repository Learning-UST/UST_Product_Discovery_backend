from core.cloud_runtime import get_active_cloud_provider
from factory.resolver import Resolver


def _services():
	return Resolver.resolve(get_active_cloud_provider())


def get_product_details_tool(upc):
	"""Fetch real-time price, stock, and info for a specific UPC."""
	return _services()["database"].get_enriched_product_info(upc)


def get_shelf_layout_tool(shelf_id):
	"""Fetch planogram layout for a specific shelf."""
	return _services()["database"].get_shelf_layout(shelf_id)


def search_products_tool(query):
	"""Search products for recommendations."""
	return _services()["vectordb"].search_text(query, top_k=3)


__all__ = [
	"get_product_details_tool",
	"get_shelf_layout_tool",
	"search_products_tool",
]

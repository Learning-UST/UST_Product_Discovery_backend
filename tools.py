from core.cloud_runtime import get_active_cloud_provider
from factory.resolver import Resolver


def _services():
    return Resolver.resolve(get_active_cloud_provider())

def get_product_details_tool(upc):
    """Fetches real-time price, stock, and info for a specific UPC."""
    return _services()["database"].get_enriched_product_info(upc)

def get_shelf_layout_tool(shelf_id):
    """Fetches the physical layout/planogram for a specific shelf."""
    return _services()["database"].get_shelf_layout(shelf_id)

def search_products_tool(query):
    """Searches the vector database for product recommendations."""
    return _services()["vectordb"].search_text(query, top_k=3)
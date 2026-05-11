from cosmos_service import CosmosService
from search_service import AiSearch

cosmos = CosmosService()
ai_search = AiSearch()

def get_product_details_tool(upc):
    """Fetches real-time price, stock, and info for a specific UPC."""
    return cosmos.get_enriched_product_info(upc)

def get_shelf_layout_tool(shelf_id):
    """Fetches the physical layout/planogram for a specific shelf."""
    return cosmos.get_shelf_layout(shelf_id)

def search_products_tool(query):
    """Searches the vector database for product recommendations."""
    return ai_search.search_text(query, top_k=3)
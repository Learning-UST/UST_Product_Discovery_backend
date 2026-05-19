from services.cosmos_service import CosmosService
import json

cosmos = CosmosService()

TOOL_DESCRIPTIONS = {
    "get_product_by_name": "Use this when user provides product name. Returns full enriched product details.",
    "get_product_by_upc": "Use this when user provides UPC or wants exact product lookup."
}

def get_product_by_name_tool(product_name: str) -> str:
    """
    Tool: Fetch enriched product details using product name.
    
    Use this when user provides product name instead of UPC.
    Includes:
    - Product info
    - Inventory
    - Pricing
    - Promotions
    """

    try:
        results = cosmos.get_enriched_product_info_by_name(product_name)

        if not results:
            return "No products found with that name."

        return json.dumps(results, indent=2)

    except Exception as e:
        return f"Error fetching product by name: {str(e)}"


def get_product_by_upc_tool(upc: str) -> str:
    """
    Tool: Fetch enriched product details using UPC.

    Use this for exact product lookup.
    Includes:
    - Product info
    - Inventory
    - Pricing
    - Promotions
    """

    try:
        result = cosmos.get_enriched_product_info(upc)

        if not result:
            return "Product not found."

        return json.dumps(result, indent=2)

    except Exception as e:
        return f"Error fetching product by UPC: {str(e)}"
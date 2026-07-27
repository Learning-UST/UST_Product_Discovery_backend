from agents.tools import ProductSearchTools


def cosmos_query_tool(query: str, content: str) -> dict:
    """
    AutoGen Tool → Structured DB search
    """
    tools_service = ProductSearchTools()
    return tools_service.cosmos_query(query, content)


def ai_search_tool(query: str) -> dict:
    """
    AutoGen Tool → Semantic search
    """
    tools_service = ProductSearchTools()
    return tools_service.ai_search_query(query)


def price_enrichment_tool(ai_result: dict) -> dict:
    """
    Direct inventory price lookup by UPC.
    Mirrors Azure: extracts UPCs from AI search results, queries MongoDB inventory,
    and merges Price/US_Price back so the LLM always receives price-enriched data.
    No-op on Azure (Azure gets prices via its OpenAI query_builder→Cosmos path).
    """
    tools_service = ProductSearchTools()
    return tools_service.enrich_ai_results_with_prices(ai_result)


def promotion_enrichment_tool(ai_result: dict) -> dict:
    """
    Apply promotions and calculate discounted prices for products.
    For each product:
    1. Look up applicable promotions by Brand/Category/Product_Id
    2. Calculate discounted_price = base_price * (1 - discount_percentage / 100)
    3. Add promotion_name and us_discounted_price fields
    
    Mirrors Azure: Cosmos query includes promotion logic via resolve_effective_price.
    AWS does this explicitly here after price enrichment.
    """
    tools_service = ProductSearchTools()
    return tools_service.enrich_ai_results_with_promotions(ai_result)

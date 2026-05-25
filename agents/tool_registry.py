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

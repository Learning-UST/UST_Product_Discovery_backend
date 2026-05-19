from autogen import register_function
from tools.rag_tools import search_products


from typing import Annotated

def search_products_tool(query: Annotated[str, "Search query for products"]) -> str:
    """Search product catalog using Azure AI Search."""
    return search_products(query)


def register_tools(rag_agent):
    register_function(
        search_products_tool,
        caller=rag_agent,
        executor=rag_agent,
        name="search_products",
        description="Search product information from Azure AI Search"
    )

"""
Tool wrapper for AutoGen (must be plain function)
"""

from core.cloud_runtime import get_active_cloud_provider
from factory.resolver import Resolver
import json

def search_products(query: str) -> str:
    """
    Search products and return formatted context.
    """
    retriever = Resolver.resolve(get_active_cloud_provider())["vectordb"]
    docs = retriever.search_text(query, top_k=5)
    # print(f"Search query: {query}")
    # print(f"Search results: {docs}")
    if not docs:
        return "No relevant product informations found."

    return json.dumps(docs, indent=2)



def search_products_tool(query: str) -> str:
    return search_products(query)

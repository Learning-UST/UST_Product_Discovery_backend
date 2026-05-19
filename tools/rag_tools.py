"""
Tool wrapper for AutoGen (must be plain function)
"""

from services.search_service import AiSearch
import json

retriever = AiSearch()

def search_products(query: str) -> str:
    """
    Search products using Azure AI Search and return formatted context.
    """
    docs = retriever.search_text(query, top_k=5)
    # print(f"Search query: {query}")
    # print(f"Search results: {docs}")
    if not docs:
        return "No relevant product informations found."

    return json.dumps(docs, indent=2)



def search_products_tool(query: str) -> str:
    return search_products(query)

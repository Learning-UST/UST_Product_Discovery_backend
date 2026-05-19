import autogen
from config.autogen_config import get_llm_config
from tools.cosmos_query_tool import (
    get_product_by_name_tool,
    get_product_by_upc_tool
)

assistant = autogen.AssistantAgent(
    name="ShoppingAssistant",
    llm_config=get_llm_config(),
    system_message="""
You are a retail assistant.

Available tools:
1. get_product_by_name → use when user gives product name
2. get_product_by_upc → use when user provides UPC

Rules:
- ALWAYS use tools for product data
- DO NOT guess or hallucinate
"""
)

assistant.register_function(
    function_map={
        "get_product_by_name": get_product_by_name_tool,
        "get_product_by_upc": get_product_by_upc_tool
    }
)
from tools.cosmos_query_tool import (
    get_product_by_name_tool,
    get_product_by_upc_tool
)


TOOL_MAP = {
    "get_product_by_name": get_product_by_name_tool,
    "get_product_by_upc": get_product_by_upc_tool,
}


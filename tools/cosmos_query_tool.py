from services.cosmos_service import CosmosService
from services.openai_service import OpenAIService
from utils.logger import get_logger

logger = get_logger()


def search_products(message: str) -> dict:
    """
    End-to-end search:
    1. Convert natural language → Cosmos query
    2. Execute query
    3. Clean response
    """

    try:
        openai_service = OpenAIService()
        cosmos_service = CosmosService()

        # ✅ Step 1: Build Query
        query_response = openai_service.query_builder(message)

        if query_response["status"] != "success":
            logger.error("Query builder failed", extra={"response": query_response})
            return {
                "status": "error",
                "message": "Failed to generate query"
            }

        table = query_response["table"]

        query_data = {
            "query": query_response["query"],
            "parameters": query_response.get("parameters", [])
        }

        # ✅ Step 2: Execute Query
        db_result = cosmos_service.query_executor(query_data, table)

        if db_result["status"] != "success":
            logger.error("Query execution failed", extra={"response": db_result})
            return db_result


        return {
            "status": "success",
            "table": table,
            "count": db_result.get("count", 0),
            "results": db_result.get("results", [])
        }

    except Exception as e:
        logger.exception("search_products failed")
        return {
            "status": "error",
            "message": str(e)
        }


# ✅ Tool Wrapper (AutoGen / API use)
def cosmos_tool(query: str) -> dict:
    """
    Tool wrapper function
    """
    return search_products(query)
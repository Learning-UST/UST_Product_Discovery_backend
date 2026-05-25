from core.cloud_runtime import get_active_cloud_provider
from factory.resolver import Resolver
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
        services = Resolver.resolve(get_active_cloud_provider())
        llm_service = services["llm"]
        database_service = services["database"]

        # ✅ Step 1: Build Query
        query_response = llm_service.query_builder(message)

        if query_response["status"] != "success":
            logger.error("Query builder failed", extra={"response": query_response})
            return {
                "status": "error",
                "message": "Failed to generate query"
            }

        table = query_response["table"]

        # ✅ Step 2: Execute Query
        db_result = database_service.query_executor(query_response, table)

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
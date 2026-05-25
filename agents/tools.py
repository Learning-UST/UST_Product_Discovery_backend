import json
from core.cloud_runtime import get_active_cloud_provider
from factory.resolver import Resolver
from utils.logger import get_logger

logger = get_logger()


class ProductSearchTools:

    def __init__(self, cloud_provider=None):
        self.cloud_provider = cloud_provider or get_active_cloud_provider()
        services = Resolver.resolve(self.cloud_provider)
        self.database = services["database"]
        self.llm = services["llm"]
        self.search = services["vectordb"]

    # ✅ Tool 1: Cosmos (Structured Search)
    def cosmos_query(self, query: str, content: str) -> dict:
        """
        Uses GPT → Cosmos DB query → structured filtering
        """

        try:
            logger.info(f"Received Cosmos query: {query}")
            query_response = self.llm.query_builder(query, content)
            logger.info(f"Query builder response: {json.dumps(query_response)}")

            if query_response["status"] != "success":
                return {
                    "status": "error",
                    "message": "Query builder failed",
                    "details": query_response
                }

            table = query_response["table"]

            db_result = self.database.query_executor(query_response, table)
            logger.info(f"Cosmos query result: {json.dumps(db_result)}")
            return {
                "status": "success",
                "source": "database",
                "table": table,
                "count": db_result.get("count", 0),
                "results": db_result.get("results", [])
            }

        except Exception as e:
            logger.exception("Cosmos query failed")
            return {
                "status": "error",
                "source": "database",
                "message": str(e)
            }

    # ✅ Tool 2: AI Search (Semantic Search)
    def ai_search_query(self, query: str) -> dict:
        """
        Uses Azure AI Search → semantic retrieval
        """

        try:
            logger.info(f"Received AI Search query: {query}")
            docs = self.search.search_text(query, top_k=5)

            return {
                "status": "success",
                "source": "ai_search",
                "count": len(docs) if docs else 0,
                "results": docs if docs else []
            }

        except Exception as e:
            logger.exception("AI Search failed")
            return {
                "status": "error",
                "source": "search",
                "message": str(e)
            }
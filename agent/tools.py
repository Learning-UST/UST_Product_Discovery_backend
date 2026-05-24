import json
from utils.logger import get_logger
from core.vectordbs.ai_search import AISearch
from core.databases.cosmos import CosmosService
from core.llms.azure_openai import AzureOpenAIService


logger = get_logger()


class ProductSearchTools:

    def __init__(self,cloud_provider:str="azure"):
        services = self._initialize_services(cloud_provider)
        self.llm = services["llm"]
        self.vectordb = services["vectordb"]
        self.database = services["database"]

    def _initialize_services(self, cloud_provider: str):
        if cloud_provider.lower() == "azure":
            return self._initialize_azure_services()
        elif cloud_provider.lower() == "aws":
            return self._initialize_aws_services()
        else:
            raise ValueError(f"Unsupported cloud provider: {cloud_provider}")

    def _initialize_azure_services(self):
         # Initialize services (can be extended to use Resolver or Dependency Injection)
        return {
            "llm": AzureOpenAIService(),
            "vectordb": AISearch(),
            "database": CosmosService()
        }
    
    def _initialize_aws_services(self):
            from core.vectordbs.opensearch import OpenSearchVectorDB
            from core.llms.bedrock import BedrockLLMService
            from core.databases.mongodb import MongoDBService

            # Initialize services (can be extended to use Resolver or Dependency Injection)
            return {
                "llm": BedrockLLMService(),
                "vectordb": OpenSearchVectorDB(),
                "database": MongoDBService()
            }

    # ✅ Tool 1: Cosmos (Structured Search)
    def cosmos_query(self, query: str, content: str) -> dict:
        """
        Uses GPT → Cosmos DB query → structured filtering
        """

        try:
            logger.info(f"Received Cosmos query: {query}")
            query_response = self.llm.query_builder(query,content)
            logger.info(f"Query builder response: {json.dumps(query_response)}")

            if query_response["status"] != "success":
                return {
                    "status": "error",
                    "message": "Query builder failed",
                    "details": query_response
                }

            table = query_response["table"]

            query_data = {
                "query": query_response["query"],
                "parameters": query_response.get("parameters", [])
            }

            db_result = self.database.query_executor(query_data, table)
            logger.info(f"Cosmos query result: {json.dumps(db_result)}")
            return {
                "status": "success",
                "source": "cosmos",
                "table": table,
                "count": db_result.get("count", 0),
                "results": db_result.get("results", [])
            }

        except Exception as e:
            logger.exception("Cosmos query failed")
            return {
                "status": "error",
                "source": "cosmos",
                "message": str(e)
            }

    # ✅ Tool 2: AI Search (Semantic Search)
    def ai_search_query(self, query: str) -> dict:
        """
        Uses Azure AI Search → semantic retrieval
        """

        try:
            logger.info(f"Received AI Search query: {query}")
            docs = self.vectordb.search_text(query, top_k=5)

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
                "source": "ai_search",
                "message": str(e)
            }

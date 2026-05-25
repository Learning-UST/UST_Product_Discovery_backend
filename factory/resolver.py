from services.openai_service import OpenAIService
from services.search_service import AiSearch
from services.cosmos_service import CosmosService
from services.bedrock_service import BedrockLLMService
from services.opensearch_service import OpenSearchService
from services.mongo_service import MongoService
from core.cloud_runtime import normalize_cloud_provider


class Resolver:
    """Resolves concrete service implementations for the selected cloud provider."""

    @staticmethod
    def resolve(cloud_provider: str = "azure") -> dict:
        provider = normalize_cloud_provider(cloud_provider)

        if provider == "aws":
            return {
                "llm": BedrockLLMService(),
                "vectordb": OpenSearchService(),
                "database": MongoService(),
            }

        return {
            "llm": OpenAIService(),
            "vectordb": AiSearch(),
            "database": CosmosService(),
        }

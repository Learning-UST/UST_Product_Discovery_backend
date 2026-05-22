# ✅ LLMs
from core.llms.azure_openai import AzureOpenAIService
from core.llms.bedrock import BedrockLLMService

# ✅ Vector DBs
from core.vectordbs.ai_search import AISearch
from core.vectordbs.opensearch import OpenSearchVectorDB

# ✅ NoSQL DBs
from core.databases.cosmos import CosmosService
from core.databases.mongodb import MongoDBService


class Resolver:
    SERVICES = {
        "azure": {
            "llm": AzureOpenAIService,
            "vectordb": AISearch,
            "database": CosmosService
        },
        "aws": {
            "llm": BedrockLLMService,
            "vectordb": OpenSearchVectorDB,
            "database": MongoDBService
        }
    }

    @staticmethod
    def resolve(cloud_provider: str):
        if cloud_provider not in Resolver.SERVICES:
            raise ValueError(f"Unsupported cloud provider: {cloud_provider}")

        services = Resolver.SERVICES[cloud_provider]

        # Instantiate all services
        return {
            key: service() for key, service in services.items()
        }
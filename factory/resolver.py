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

    # ✅ ----------------------------
    # LLM
    # ✅ ----------------------------
    @staticmethod
    def get_llm(name: str):
        mapping = {
            "openai": AzureOpenAIService,
            "bedrock": BedrockLLMService
        }

        if name not in mapping:
            raise ValueError(f"Unsupported LLM: {name}")

        return mapping[name]()  # ✅ instance


    # ✅ ----------------------------
    # Vector DB
    # ✅ ----------------------------
    @staticmethod
    def get_vectordb(name: str):
        mapping = {
            "ai_search": AISearch,
            "opensearch": OpenSearchVectorDB
        }

        if name not in mapping:
            raise ValueError(f"Unsupported Vector DB: {name}")

        return mapping[name]()  # ✅ instance


    # ✅ ----------------------------
    # Database (NoSQL)
    # ✅ ----------------------------
    @staticmethod
    def get_database(name: str):
        mapping = {
            "cosmos": CosmosService,
            "mongodb": MongoDBService
        }

        if name not in mapping:
            raise ValueError(f"Unsupported Database: {name}")

        return mapping[name]()  # ✅ instance
    
    @staticmethod
    def get_azure_service():
       services = {
            "llm": AzureOpenAIService,
            "vectordb": AISearch,
            "database": CosmosService
       }
       return services
    
    @staticmethod
    def get_aws_service():
       services = {
            "llm": BedrockLLMService,
            "vectordb": OpenSearchVectorDB,
            "database": MongoDBService
       }
       return services
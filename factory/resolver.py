class Resolver:
    SERVICES = {
        "azure": {
            "llm": "core.llms.azure_openai:AzureOpenAIService",
            "vectordb": "core.vectordbs.ai_search:AISearch",
            "database": "core.databases.cosmos:CosmosService"
        },
        "aws": {
            "llm": "core.llms.bedrock:BedrockLLMService",
            "vectordb": "core.vectordbs.opensearch:OpenSearchVectorDB",
            "database": "core.databases.mongodb:MongoDBService"
        }
    }

    @staticmethod
    def _load_class(import_path: str):
        module_path, class_name = import_path.split(":", 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)

    @staticmethod
    def resolve(cloud_provider: str):
        if cloud_provider not in Resolver.SERVICES:
            raise ValueError(f"Unsupported cloud provider: {cloud_provider}")

        services = Resolver.SERVICES[cloud_provider]

        # Instantiate all services
        return {
            key: Resolver._load_class(service_path)() for key, service_path in services.items()
        }
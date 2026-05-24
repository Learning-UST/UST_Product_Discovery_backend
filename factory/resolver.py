from services.openai_service import OpenAIService
from services.search_service import AiSearch
from services.cosmos_service import CosmosService


class Resolver:
    """Resolves concrete service implementations for the selected cloud provider."""

    @staticmethod
    def resolve(cloud_provider: str = "azure") -> dict:
        provider = str(cloud_provider or "azure").strip().lower()

        if provider != "azure":
            raise ValueError(
                f"Unsupported cloud provider: {provider}. Supported providers: azure"
            )

        return {
            "llm": OpenAIService(),
            "vectordb": AiSearch(),
            "database": CosmosService(),
        }

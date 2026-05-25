# llm_service.py

from core.cloud_runtime import get_active_cloud_provider
from factory.resolver import Resolver

class LLMService:

    def __init__(self):
        services = Resolver.resolve(get_active_cloud_provider())
        self.impl = services["llm"]

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return self.impl.generate(system_prompt, user_prompt)

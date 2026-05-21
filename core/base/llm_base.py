from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseLLM(ABC):

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        pass

    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def query_builder(self, message: str, content: str = "") -> Dict[str, Any]:
        pass

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseVectorDB(ABC):

    @abstractmethod
    def search_text(self, query: str, top_k: int = 5) -> List[Dict]:
        pass

    @abstractmethod
    def vector_search(self, embedding: List[float], top_k: int = 5) -> List[Dict]:
        pass


    @abstractmethod
    def insert(self, docs: List[Dict]) -> Any:
        pass

    @abstractmethod
    def create_index(self):
        pass

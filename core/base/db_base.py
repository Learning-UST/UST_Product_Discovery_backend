from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseDatabase(ABC):

    # ✅ Core methods (MUST implement)
    @abstractmethod
    def get_item(self, key: str, table_name: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def query_executor(self, query: Dict, table_name: str) -> Dict:
        pass

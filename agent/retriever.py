# retriever.py

from services.search_service import AiSearch
from utils.logger import get_logger

logger = get_logger()


class Retriever:

    def __init__(self):
        self.search = AiSearch()

    def retrieve(self, query: str, top_k=3):
        docs = self.search.search_text(query, top_k=top_k)

        # ✅ Retry strategy if no results
        if not docs:
            logger.info("No results found. Retrying with relaxed query...")
            relaxed_query = self._relax_query(query)
            docs = self.search.search_text(relaxed_query, top_k=top_k)

        return docs

    def _relax_query(self, query: str) -> str:
        # Basic fallback strategy
        return query.lower().replace("best", "").strip()
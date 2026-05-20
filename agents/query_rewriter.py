from agent.llm_service import LLMService
from utils.logger import get_logger

logger = get_logger()


class QueryRewriter:

    def __init__(self):
        self.llm = LLMService()

    def rewrite(self, query: str, history: str) -> str:
        """
        Convert follow-up question into standalone query
        """

        rewrite_prompt = f"""
You are a helpful assistant that rewrites user queries into clear, standalone search queries.

Rules:
- Use conversation history to resolve references like "it", "that", "this"
- Keep it concise
- Do not add extra information
- Output ONLY the rewritten query

Conversation History:
{history}

User Query:
{query}

Rewritten Query:
"""

        try:
            rewritten = self.llm.generate(
                system_prompt="You rewrite queries for search clarity.",
                user_prompt=rewrite_prompt
            )
            # logger.info(f"Original query: {query}")
            # logger.info(f"Rewritten query: {rewritten}")
            return rewritten.strip()

        except Exception as e:
            logger.error(f"Rewrite failed: {e}")
            return query  # fallback

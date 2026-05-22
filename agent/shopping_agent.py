"""
Shopping Agent (Sequential Execution - Production Ready)
"""

import json
from agent.tool_registry import ai_search_tool, cosmos_query_tool
from utils.logger import get_logger
from core.prompts import REWRITE_SYSTEM_PROMPT,FINAL_ANSWER_SYSTEM_PROMPT
from core.utils import extract_product_names, normalize_result_payload
from agent.tools import ProductSearchTools

logger = get_logger()


class ShopilotAgent:

    def __init__(self,cloud_provider="azure"):
        self.tools = ProductSearchTools(cloud_provider)
        

    def rewrite(self, query: str, history: str) -> str:
        """
        Convert follow-up question into standalone query
        """

        rewrite_prompt = f"""


            Conversation History:
            {history}

            User Query:
            {query}

            Rewritten Query:
            """

        try:
            rewritten = self.tools.llm.generate(
                system_prompt=REWRITE_SYSTEM_PROMPT,
                user_prompt=rewrite_prompt
            )
            # logger.info(f"Original query: {query}")
            # logger.info(f"Rewritten query: {rewritten}")
            return rewritten.strip()

        except Exception as e:
            logger.error(f"Rewrite failed: {e}")
            return query  # fallback

    def final_answer(self, rewritten_query: str, ai_result: dict, cosmos_result: dict) -> str:

            user_prompt = f"""
                User Query:
                {rewritten_query}

                AI Search Results:
                {json.dumps(ai_result)}

                Cosmos DB Results:
                {json.dumps(cosmos_result)}

                """

            final_response = self.tools.llm.generate(
                system_prompt=FINAL_ANSWER_SYSTEM_PROMPT,
                user_prompt=user_prompt
            )


            return final_response


    def chat(self, message: str, history: list) -> tuple:
        logger.info(f"Received message: {message}")
        history = history or []
        logger.info(f"Conversation history length: {len(history)}")
        try:
            # ✅ STEP 1: Rewrite user query (context aware)
            rewritten_query = self.rewrite(message, history)
            logger.info(f"[STEP 1] Rewritten Query: {rewritten_query}")

            # ✅ STEP 2: AI SEARCH (Semantic)
            ai_result = self.tools.ai_search_query(rewritten_query)
            ai_result = normalize_result_payload(ai_result)
            logger.info(f"[STEP 2] AI Search Done")
            logger.info(f"AI Search Result: {json.dumps(ai_result)}")

            # ✅ STEP 3: Cosmos Query
            cosmos_result = self.tools.database(rewritten_query, json.dumps(ai_result))
            cosmos_result = normalize_result_payload(cosmos_result)
            logger.info(f"[STEP 4] Cosmos Query Done")
            logger.info(f"Cosmos DB Result: {json.dumps(cosmos_result)}")
            # ✅ STEP 5: Final Answer Generation

            logger.info(f"[STEP 5] Final Answer generated")
            final_response = self.final_answer(rewritten_query, ai_result, cosmos_result)

            # ✅ Extract only the product names shown in the answer for frontend highlighting
            product_names = extract_product_names(final_response)
            logger.info(f"Extracted product names from answer: {product_names}")

            return final_response, ai_result, product_names

        except Exception as e:
            logger.exception("ShoppingAgent failed")
            return "Something went wrong while processing your request.", [], []
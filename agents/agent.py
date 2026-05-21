"""
Shopping Agent (Sequential Execution - Production Ready)
"""

import json
from agents.query_rewriter import QueryRewriter
from agents.tool_registry import ai_search_tool, cosmos_query_tool
from services.openai_service import OpenAIService
from agent.llm_service import LLMService
from utils.logger import get_logger

logger = get_logger()


class ShopilotAgent:

    def __init__(self):
        self.rewriter = QueryRewriter()
        self.llm = LLMService()

    def chat(self, message: str, history: list) -> tuple:
        logger.info(f"Received message: {message}")
        logger.info(f"Conversation history length: {len(history)}")
        try:
            # ✅ STEP 1: Rewrite user query (context aware)
            rewritten_query = self.rewriter.rewrite(message, history)
            logger.info(f"[STEP 1] Rewritten Query: {rewritten_query}")

            # ✅ STEP 2: AI SEARCH (Semantic)
            ai_result = ai_search_tool(rewritten_query)
            logger.info(f"[STEP 2] AI Search Done")
            logger.info(f"AI Search Result: {json.dumps(ai_result)}")

            # ✅ STEP 3: Rewrite for structured query (Cosmos)
#             structured_prompt = f"""
# Convert this user request into a structured product filter query:
# User Query: {rewritten_query}
# Content : {ai_result}
# Consider product attributes like:
# - Brand
# - Category
# - Calories
# - Ingredients
# - Labels
# """

#             structured_query = self.llm.generate(
#                 system_prompt="You convert user queries into structured product search filters.",
#                 user_prompt=structured_prompt
#             )

#             logger.info(f"[STEP 3] Structured Query: {structured_query}")

            # ✅ STEP 4: Cosmos Query
            cosmos_result = cosmos_query_tool(rewritten_query, json.dumps(ai_result))
            logger.info(f"[STEP 4] Cosmos Query Done")
            logger.info(f"Cosmos DB Result: {json.dumps(cosmos_result)}")
            # ✅ STEP 5: Final Answer Generation
            final_prompt = f"""
You are a product assistant.

Use the below data to answer the user.

User Query:
{rewritten_query}

AI Search Results:
{json.dumps(ai_result)}

Cosmos DB Results:
{json.dumps(cosmos_result)}

Instructions:
- Combine insights from both sources
- Prioritize accurate product info
- Be clear and concise
- If no data → "No relevant product information found"
"""

            final_response = self.llm.generate(
                system_prompt="You are a helpful shopping assistant",
                user_prompt=final_prompt
            )


            logger.info(f"[STEP 5] Final Answer generated")

            return final_response , ai_result

        except Exception as e:
            logger.exception("ShoppingAgent failed")
            return "Something went wrong while processing your request.", []
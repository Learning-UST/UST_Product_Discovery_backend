"""
Shopping Agent (Sequential Execution - Production Ready)
"""

import json
from agents.query_rewriter import QueryRewriter
from agents.tool_registry import ai_search_tool, cosmos_query_tool
from services.openai_service import OpenAIService
from agent.llm_service import LLMService
from utils.logger import get_logger
from utils.config import get_config_value

logger = get_logger()


class ShopilotAgent:

    def __init__(self):
        self.rewriter = QueryRewriter()
        self.llm = LLMService()

    def _price_source(self) -> str:
        source = str(get_config_value("PRICE_SOURCE", "NORMAL")).strip().upper()
        return "US" if source == "US" else "NORMAL"

    def _currency_symbol(self) -> str:
        configured_symbol = get_config_value("PRICE_CURRENCY_SYMBOL")
        if configured_symbol is not None and str(configured_symbol).strip() != "":
            return str(configured_symbol).strip()
        return "$" if self._price_source() == "US" else "INR "

    def _normalize_price_fields(self, item: dict) -> dict:
        if not isinstance(item, dict):
            return item

        source = self._price_source()
        normalized = dict(item)

        if source == "US":
            price = normalized.get("us_price")
            discounted = normalized.get("us_discounted_price")
            if price is None:
                price = normalized.get("US_Price")
            if discounted is None:
                discounted = normalized.get("US_Discounted_Price")
        else:
            price = normalized.get("price")
            discounted = normalized.get("discounted_price")
            if price is None:
                price = normalized.get("Price")
            if discounted is None:
                discounted = normalized.get("Discounted_Price")

        if price is not None:
            normalized["display_price"] = price
        if discounted is not None:
            normalized["display_discounted_price"] = discounted

        normalized["currency_symbol"] = self._currency_symbol()
        return normalized

    def _normalize_result_payload(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)
        results = normalized.get("results")
        if isinstance(results, list):
            normalized["results"] = [self._normalize_price_fields(r) for r in results]
        return normalized

    def _extract_product_names(self, ai_result: dict, cosmos_result: dict) -> list:
        """Extract unique product names from both search results for frontend highlighting"""
        product_names = []
        seen = set()

        # Extract from AI Search results
        ai_results = ai_result.get("results", [])
        if isinstance(ai_results, list):
            for item in ai_results:
                name = item.get("name")
                if name and name not in seen:
                    product_names.append(name)
                    seen.add(name)

        # Extract from Cosmos results
        cosmos_results = cosmos_result.get("results", [])
        if isinstance(cosmos_results, list):
            for item in cosmos_results:
                name = item.get("name") or item.get("Name")
                if name and name not in seen:
                    product_names.append(name)
                    seen.add(name)

        logger.info(f"Extracted product names: {product_names}")
        return product_names

    def chat(self, message: str, history: list) -> tuple:
        logger.info(f"Received message: {message}")
        history = history or []
        logger.info(f"Conversation history length: {len(history)}")
        try:
            # ✅ STEP 1: Rewrite user query (context aware)
            rewritten_query = self.rewriter.rewrite(message, history)
            logger.info(f"[STEP 1] Rewritten Query: {rewritten_query}")

            # ✅ STEP 2: AI SEARCH (Semantic)
            ai_result = ai_search_tool(rewritten_query)
            ai_result = self._normalize_result_payload(ai_result)
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
            cosmos_result = self._normalize_result_payload(cosmos_result)
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
# - Include only the product name and description in the response.
- If the user asks for price, use display_price/display_discounted_price with currency_symbol.
- Prioritize accurate product info
- Be clear and concise
- If no data → "No relevant product information found"
"""

            final_response = self.llm.generate(
                system_prompt="You are a helpful shopping assistant",
                user_prompt=final_prompt
            )

            logger.info(f"[STEP 5] Final Answer generated")

            # ✅ Extract product names for frontend highlighting
            product_names = self._extract_product_names(ai_result, cosmos_result)

            return final_response, ai_result, product_names

        except Exception as e:
            logger.exception("ShoppingAgent failed")
            return "Something went wrong while processing your request.", [], []
"""
Shopping Agent (Sequential Execution - Production Ready)
"""

import json
import re
from agent.query_rewriter import QueryRewriter
from agent.tool_registry import ai_search_tool, cosmos_query_tool
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

    def _extract_product_names(self, answer_text: str) -> list:
        """Extract only the product names that are actually visible in the final answer."""
        if not answer_text:
            return []

        product_names = []
        seen = set()

        for raw_line in answer_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Remove leading numbering like "1." or "2)"
            line = re.sub(r"^\d+[\.)]\s*", "", line)

            # Skip intro/outro sentences
            if line.lower().startswith(("here are", "these options", "these are", "you can")):
                continue

            candidate = None

            # Handle formats like: "Product Name by Brand - Description"
            if " - " in line:
                candidate = line.split(" - ", 1)[0].strip()
            # Handle formats like: "Product Name: Description"
            elif ":" in line:
                candidate = line.split(":", 1)[0].strip()
            else:
                candidate = line.strip()

            # If we still have "Product Name by Brand", keep only the product name
            if " by " in candidate.lower():
                candidate = re.split(r"\s+by\s+", candidate, flags=re.IGNORECASE)[0].strip()

            # Final cleanup for short/obvious noise
            if candidate and len(candidate) > 2 and candidate not in seen:
                product_names.append(candidate)
                seen.add(candidate)

        logger.info(f"Extracted product names from answer: {product_names}")
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

            # ✅ STEP 3: Cosmos Query
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

            # ✅ Extract only the product names shown in the answer for frontend highlighting
            product_names = self._extract_product_names(final_response)

            return final_response, ai_result, product_names

        except Exception as e:
            logger.exception("ShoppingAgent failed")
            return "Something went wrong while processing your request.", [], []
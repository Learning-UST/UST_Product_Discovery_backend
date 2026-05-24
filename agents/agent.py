"""
Shopping Agent (Sequential Execution - Production Ready)
"""

import json
import os
import re
from difflib import SequenceMatcher
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

    def _extract_product_names(self, answer_text: str) -> list:
        """Extract only the product names that are actually visible in the final answer."""
        if not answer_text:
            return []

        products_param_names = self._extract_products_parameter_names(answer_text)
        product_names = []
        seen = set()

        for name in products_param_names:
            candidate = str(name).strip()
            if candidate and candidate not in seen:
                product_names.append(candidate)
                seen.add(candidate)

        for raw_line in answer_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Keep only numbered-list lines as product title candidates.
            if not re.match(r"^\d+[\.)]\s+", line):
                continue

            # Remove leading numbering like "1." or "2)"
            line = re.sub(r"^\d+[\.)]\s*", "", line)

            # Skip intro/outro sentences
            if line.lower().startswith(("here are", "these options", "these are", "you can")):
                continue

            candidate = None

            # Handle formats like: "Product Name - Description"
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

    def _extract_products_parameter_names(self, answer_text: str) -> list:
        """Extract product names from products(name1, name2, ...) blocks in the LLM response."""
        if not answer_text:
            return []

        names = []
        seen = set()
        lower_text = answer_text.lower()
        search_start = 0

        while True:
            idx = lower_text.find("products(", search_start)
            if idx == -1:
                break

            open_idx = idx + len("products")
            close_idx = self._find_matching_paren(answer_text, open_idx)
            if close_idx == -1:
                break

            inner = answer_text[open_idx + 1:close_idx]
            for token in self._split_comma_balanced(inner):
                candidate = token.strip().strip('"\'')
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    names.append(candidate)

            search_start = close_idx + 1

        return names

    def _find_matching_paren(self, text: str, open_idx: int) -> int:
        if open_idx < 0 or open_idx >= len(text) or text[open_idx] != "(":
            return -1

        depth = 0
        for i in range(open_idx, len(text)):
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i

        return -1

    def _split_comma_balanced(self, text: str) -> list:
        parts = []
        current = []
        depth = 0

        for ch in text:
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth = max(0, depth - 1)
                current.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(ch)

        if current:
            parts.append("".join(current).strip())

        return [p for p in parts if p]

    def _tokenize_for_match(self, value) -> set:
        text = str(value or "").lower()
        tokens = re.findall(r"[a-z0-9]+", text)
        return {token for token in tokens if token}

    def _is_name_match(self, mentioned_name: str, candidate_name: str) -> bool:
        mentioned_norm = self._normalize_text_for_match(mentioned_name)
        candidate_norm = self._normalize_text_for_match(candidate_name)
        if not mentioned_norm or not candidate_norm:
            return False

        # Fast exact/containment checks.
        if (
            mentioned_norm == candidate_norm
            or mentioned_norm in candidate_norm
            or candidate_norm in mentioned_norm
        ):
            return True

        # Fuzzy check for near-variants.
        similarity = SequenceMatcher(None, mentioned_norm, candidate_norm).ratio()
        if similarity >= 0.72:
            return True

        # Token overlap check handles variants like "Pepsi Can" vs "Pepsi Zero Sugar Can".
        mentioned_tokens = self._tokenize_for_match(mentioned_name)
        candidate_tokens = self._tokenize_for_match(candidate_name)
        if not mentioned_tokens or not candidate_tokens:
            return False

        overlap = len(mentioned_tokens.intersection(candidate_tokens))
        min_token_count = min(len(mentioned_tokens), len(candidate_tokens))
        if min_token_count == 0:
            return False

        return (overlap / float(min_token_count)) >= 0.6

    def _normalize_text_for_match(self, value) -> str:
        if value is None:
            return ""

        normalized = str(value).lower().strip()
        normalized = normalized.replace("&", " and ")
        normalized = re.sub(r"[^a-z0-9]+", "", normalized)
        return normalized

    def _get_result_name_candidates(self, item: dict) -> list:
        candidates = []

        for key in ["name", "product_name", "title"]:
            value = item.get(key)
            if value:
                candidates.append(str(value).strip())

        image_url = item.get("image_url")
        if image_url:
            image_name = os.path.splitext(os.path.basename(str(image_url)))[0]
            image_name = image_name.replace("_", " ").replace("-", " ").strip()
            if image_name:
                candidates.append(image_name)

        brand = item.get("brand")
        if brand and candidates:
            candidates.extend([f"{brand} {candidate}" for candidate in list(candidates)])

        unique_candidates = []
        seen = set()
        for candidate in candidates:
            normalized = self._normalize_text_for_match(candidate)
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_candidates.append(candidate)

        return unique_candidates

    def _get_record_identity(self, item: dict) -> str:
        raw_identity = (
            item.get("upc")
            or item.get("product_upc")
            or item.get("id")
            or item.get("sku")
            or item.get("product_id")
            or item.get("name")
            or item.get("description")
        )
        return self._normalize_text_for_match(raw_identity)

    def _get_primary_product_name(self, item: dict) -> str:
        for key in ["name", "product_name", "title"]:
            value = item.get(key)
            if value and str(value).strip():
                return str(value).strip()

        image_url = item.get("image_url")
        if image_url:
            image_name = os.path.splitext(os.path.basename(str(image_url)))[0]
            image_name = image_name.replace("_", " ").replace("-", " ").strip()
            if image_name:
                return image_name

        return ""

    def _name_similarity_score(self, source_name: str, candidate_name: str) -> float:
        source_norm = self._normalize_text_for_match(source_name)
        candidate_norm = self._normalize_text_for_match(candidate_name)
        if not source_norm or not candidate_norm:
            return 0.0

        if source_norm == candidate_norm:
            return 1.0

        if source_norm in candidate_norm or candidate_norm in source_norm:
            return 0.92

        return SequenceMatcher(None, source_norm, candidate_norm).ratio()

    def _canonicalize_answer_product_names(self, answer_text: str, *payloads: dict) -> str:
        if not answer_text:
            return answer_text

        mentioned_names = self._extract_product_names(answer_text)
        if not mentioned_names:
            return answer_text

        canonical_names = []
        seen = set()
        for payload in payloads:
            results = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(results, list):
                continue

            for item in results:
                if not isinstance(item, dict):
                    continue

                name = self._get_primary_product_name(item)
                normalized = self._normalize_text_for_match(name)
                if not normalized or normalized in seen:
                    continue

                seen.add(normalized)
                canonical_names.append(name)

        corrected_answer = answer_text
        for mentioned_name in mentioned_names:
            best_name = ""
            best_score = 0.0
            for canonical_name in canonical_names:
                score = self._name_similarity_score(canonical_name, mentioned_name)
                if score > best_score:
                    best_score = score
                    best_name = canonical_name

            # Replace only reasonably-close variants to avoid accidental substitutions.
            if best_name and best_score >= 0.78:
                if self._normalize_text_for_match(best_name) != self._normalize_text_for_match(mentioned_name):
                    corrected_answer = re.sub(
                        re.escape(mentioned_name),
                        best_name,
                        corrected_answer,
                        flags=re.IGNORECASE,
                    )

        return corrected_answer

    def _extract_mentioned_source_records(self, answer_text: str, *payloads: dict) -> list:
        mentioned_names = [
            name
            for name in self._extract_product_names(answer_text)
            if self._normalize_text_for_match(name)
        ]
        if not mentioned_names:
            return []

        matched_records = []
        seen_records = set()

        for payload in payloads:
            results = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(results, list):
                continue

            for item in results:
                if not isinstance(item, dict):
                    continue

                candidate_names = [
                    candidate
                    for candidate in self._get_result_name_candidates(item)
                    if self._normalize_text_for_match(candidate)
                ]
                if not candidate_names:
                    continue

                if not any(
                    self._is_name_match(mentioned_name, candidate_name)
                    for mentioned_name in mentioned_names
                    for candidate_name in candidate_names
                ):
                    continue

                record_identity = self._get_record_identity(item)
                if record_identity and record_identity in seen_records:
                    continue

                if record_identity:
                    seen_records.add(record_identity)
                matched_records.append(dict(item))

        logger.info(f"Matched source records from answer: {len(matched_records)}")
        return matched_records

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
- I also need a comma separated list of product names used in the answer. This will be used to identify source records for UPC extraction. Include complete product names exactly as present in source data. Name this list as products(parameter).
- Use product names exactly as present in source data. Do not paraphrase or rename product names. Include the full product name as present in the source, even if it's long. This is important for accurate product identification.
- Prioritize accurate product info
- Include the full proper product name and description in the response, no need to show the origin or shelf life in the response.
- Format the answer for readability using short bullet points.
- Highlight key details in markdown bold: product name, price, and the key attribute asked by the user.
- If the user asks for price, use display_price/display_discounted_price with currency_symbol.
- Be clear and concise
- If no data → "No relevant product information found"
"""

            final_response = self.llm.generate(
                system_prompt="You are a helpful shopping assistant",
                user_prompt=final_prompt
            )

            # Ground product names back to canonical source names to avoid renamed variants.
            final_response = self._canonicalize_answer_product_names(
                final_response,
                ai_result,
                cosmos_result,
            )

            logger.info(f"[STEP 5] Final Answer generated")

            # ✅ Return exact source records that correspond to products explicitly mentioned in the answer.
            mentioned_records = self._extract_mentioned_source_records(
                final_response,
                ai_result,
                cosmos_result,
            )

            return final_response, ai_result, mentioned_records

        except Exception as e:
            logger.exception("ShoppingAgent failed")
            return "Something went wrong while processing your request.", [], []
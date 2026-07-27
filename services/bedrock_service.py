import os
import json
import boto3
from typing import List

from utils.config import get_config_value
from utils.logger import get_logger
from services.openai_service import (
    QUERY_BUILDER_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
)

logger = get_logger()


class BedrockLLMService:
    def __init__(self):
        # ✅ Load config
        self.region = get_config_value("AWS_REGION")
        self.model_id = get_config_value("AWS_BEDROCK_CHAT_MODEL")
        self.embedding_model_id = get_config_value("AWS_BEDROCK_EMBEDDING_MODEL")

        self.access_key = get_config_value("AWS_ACCESS_KEY_ID")
        self.secret_key = get_config_value("AWS_SECRET_ACCESS_KEY")
        self.profile_arn = get_config_value("AWS_BEDROCK_INFERENCE_PROFILE_ARN")
        self._validate_config()

        # ✅ Bedrock runtime client (supports either explicit keys or ambient IAM role/profile)
        client_kwargs = {"region_name": self.region}
        if self.access_key and self.secret_key:
            client_kwargs["aws_access_key_id"] = self.access_key
            client_kwargs["aws_secret_access_key"] = self.secret_key
        self.runtime_client = boto3.client("bedrock-runtime", **client_kwargs)

        logger.info("✅ BedrockLLMService initialized")

    # ------------------------------------------------------------------
    # CONFIG VALIDATION
    # ------------------------------------------------------------------
    def _validate_config(self):
        missing = []

        if not self.region:
            missing.append("AWS_REGION")
        if not self.embedding_model_id:
            missing.append("AWS_BEDROCK_EMBEDDING_MODEL")
        if not self.model_id and not self.profile_arn:
            missing.append("AWS_BEDROCK_CHAT_MODEL or AWS_BEDROCK_INFERENCE_PROFILE_ARN")
        if missing:
            raise ValueError(f"Missing AWS Bedrock configuration: {', '.join(missing)}")

    # ------------------------------------------------------------------
    # GENERIC INVOKE
    # ------------------------------------------------------------------
    def invoke_model(self, payload: dict, model_id: str = None) -> dict:
        """
        Generic Bedrock invocation wrapper
        """
        try:
            target_model_id = model_id or self.profile_arn or self.model_id
            response = self.runtime_client.invoke_model(
                modelId=target_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload),
            )

            result = json.loads(response["body"].read())
            return result

        except Exception as e:
            logger.error(f"❌ Bedrock invocation failed: {e}")
            raise

    # ------------------------------------------------------------------
    # CHAT / GENERATION
    # ------------------------------------------------------------------
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Chat completion using Bedrock (Anthropic format)
        """
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "temperature": 0.5,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        }

        result = self.invoke_model(payload)

        try:
            return result["content"][0]["text"]
        except Exception:
            logger.error(f"Unexpected Bedrock response: {result}")
            raise

    # ------------------------------------------------------------------
    # QUERY BUILDER (FOR OPENSEARCH)
    # ------------------------------------------------------------------
    def build_search_query(self, user_input: str) -> str:
        """
        Converts user natural query into structured search query
        """
        return self.generate(
            system_prompt=QUERY_BUILDER_SYSTEM_PROMPT,
            user_prompt=user_input,
        )

    def query_builder(self, message: str, content: str = "") -> dict:
        """Provider-neutral query builder result compatible with existing tool chain."""
        text = str(message or "").strip()
        lower = text.lower()

        table = "products"
        if any(word in lower for word in ["promotion", "offer", "discount"]):
            table = "promotion"
        elif any(word in lower for word in ["stock", "inventory", "quantity"]):
            table = "inventory"
        elif any(word in lower for word in ["shelf", "layout", "row"]):
            table = "layout"

        # ------------------------------------------------------------------
        # Parse AI-search content to extract exact product names and UPCs.
        # Using these gives precise MongoDB filters instead of matching the
        # full query text (which never matches a product Name field).
        # ------------------------------------------------------------------
        names_from_content: list = []
        upcs_from_content: list = []

        if content:
            try:
                parsed = json.loads(content)
                ai_results = parsed.get("results") if isinstance(parsed, dict) else None
                if isinstance(ai_results, list):
                    for r in ai_results[:10]:
                        if not isinstance(r, dict):
                            continue
                        name = r.get("name") or r.get("Name")
                        upc = r.get("upc") or r.get("UPC")
                        if name and str(name).strip():
                            names_from_content.append(str(name).strip())
                        if upc and str(upc).strip():
                            upcs_from_content.append(str(upc).strip())
            except Exception:
                pass

        # Build a targeted filter when AI-search content provides product identifiers.
        if names_from_content or upcs_from_content:
            import re as _re
            or_conditions: list = []
            for name in names_from_content:
                pattern = _re.escape(name)
                or_conditions.extend([
                    {"Name": {"$regex": pattern, "$options": "i"}},
                    {"name": {"$regex": pattern, "$options": "i"}},
                ])
            for upc_str in upcs_from_content:
                or_conditions.extend([{"upc": upc_str}, {"UPC": upc_str}])
                try:
                    upc_int = int(upc_str)
                    or_conditions.extend([{"upc": upc_int}, {"UPC": upc_int}])
                except (ValueError, TypeError):
                    pass

            if table == "inventory":
                # For inventory queries, filter by UPC directly.
                inv_conditions: list = []
                for upc_str in upcs_from_content:
                    inv_conditions.extend([{"upc": upc_str}, {"UPC": upc_str}])
                    try:
                        upc_int = int(upc_str)
                        inv_conditions.extend([{"upc": upc_int}, {"UPC": upc_int}])
                    except (ValueError, TypeError):
                        pass
                mongo_filter = {"$or": inv_conditions} if inv_conditions else {"$or": or_conditions}
            else:
                mongo_filter = {"$or": or_conditions} if or_conditions else {}
        else:
            # Fallback: use individual words from the query as regex patterns so
            # that the full query text doesn't kill match accuracy.
            words = [w for w in text.split() if len(w) > 3]
            if words:
                # Prefer matching by product name keywords (last 5 meaningful words)
                keyword_pattern = " ".join(words[-5:])
                import re as _re
                regex_filter = {"$regex": _re.escape(keyword_pattern), "$options": "i"}
            else:
                regex_filter = {"$regex": text, "$options": "i"} if text else {"$exists": True}

            table_filters = {
                "products": {
                    "$or": [
                        {"Name": regex_filter},
                        {"name": regex_filter},
                        {"Brand": regex_filter},
                        {"brand": regex_filter},
                        {"Category": regex_filter},
                        {"category": regex_filter},
                        {"Description": regex_filter},
                        {"description": regex_filter},
                    ]
                },
                "inventory": {
                    "$or": [
                        {"upc": regex_filter},
                        {"UPC": regex_filter},
                        {"store_id": regex_filter},
                    ]
                },
                "promotion": {
                    "$or": [
                        {"Promotion_Name": regex_filter},
                        {"Scope_Value": regex_filter},
                    ]
                },
                "layout": {
                    "$or": [
                        {"id": regex_filter},
                        {"shelf_id": regex_filter},
                        {"shelf_name": regex_filter},
                    ]
                },
            }
            mongo_filter = table_filters.get(table, table_filters["products"])

        return {
            "status": "success",
            "table": table,
            "query": "SELECT * FROM c",
            "parameters": [],
            "mongo_filter": mongo_filter,
        }

    # ------------------------------------------------------------------
    # EMBEDDINGS
    # ------------------------------------------------------------------
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using Bedrock embedding model
        """
        try:
            embeddings = []

            for text in texts:
                payload = {
                    "inputText": text
                }

                response = self.runtime_client.invoke_model(
                    modelId=self.embedding_model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(payload),
                )

                result = json.loads(response["body"].read())

                embeddings.append(result.get("embedding"))

            return embeddings

        except Exception as e:
            logger.error(f"❌ Embedding generation failed: {e}")
            raise

    def get_embedding(self, text: str) -> List[float]:
        embeddings = self.get_embeddings([text])
        return embeddings[0] if embeddings else []
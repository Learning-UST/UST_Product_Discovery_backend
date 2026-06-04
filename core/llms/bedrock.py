import json
import boto3
from core.base.llm_base import BaseLLM
from utils.config import get_config_value
from utils.logger import get_logger
from core.prompts import QUERY_BUILDER_SYSTEM_PROMPT
from typing import List


logger = get_logger()


class BedrockLLMService(BaseLLM):

    def __init__(self):
        # ✅ Load config
        self.region = get_config_value("AWS_REGION")
        self.model_id = get_config_value("AWS_BEDROCK_CHAT_MODEL")
        self.embedding_model_id = get_config_value("AWS_BEDROCK_EMBEDDING_MODEL")

        self.access_key = get_config_value("AWS_ACCESS_KEY_ID")
        self.secret_key = get_config_value("AWS_SECRET_ACCESS_KEY")
        self.profile_arn = get_config_value("AWS_BEDROCK_INFERENCE_PROFILE_ARN")
        self._validate_config()

        # ✅ Bedrock runtime client
        self.runtime_client = boto3.client(
            "bedrock-runtime",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
        )

        logger.info("✅ BedrockLLMService initialized")

    # ------------------------------------------------------------------
    # CONFIG VALIDATION
    # ------------------------------------------------------------------
    def _validate_config(self):
        missing = []

        if not self.region:
            missing.append("AWS_REGION")
        if not self.model_id:
            missing.append("AWS_BEDROCK_CHAT_MODEL")
        if not self.embedding_model_id:
            missing.append("AWS_BEDROCK_EMBEDDING_MODEL")
        if not self.access_key:
            missing.append("AWS_ACCESS_KEY_ID")
        if not self.secret_key:
            missing.append("AWS_SECRET_ACCESS_KEY")
        if not self.profile_arn:
            missing.append("AWS_BEDROCK_INFERENCE_PROFILE_ARN")
        if missing:
            raise ValueError(f"Missing AWS Bedrock configuration: {', '.join(missing)}")

    # ------------------------------------------------------------------
    # GENERIC INVOKE
    # ------------------------------------------------------------------
    def invoke_model(self, payload: dict) -> dict:
        """
        Generic Bedrock invocation wrapper
        """
        try:
            response = self.runtime_client.invoke_model(
                modelId=self.profile_arn,
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
            "temperature": 0.2,
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
    # EMBEDDINGS
    # ------------------------------------------------------------------
    def get_embedding(self, texts: List[str]) -> List[List[float]]:
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

    def query_builder(self, message: str, content: str = ""):

        try:

            payload  = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "temperature": 0,
            "system": QUERY_BUILDER_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": f"message: {message}\n\ncontent: {content}"
                }
            ],
        }

         

            result = self.invoke_model(payload)
            try:
                query_data = json.loads(result["content"][0]["text"].strip())
            except Exception:
                logger.error("Invalid JSON from Bedrock", content=content)
                return {"status": "error", "message": "Failed to parse query", "raw": content}

            if not query_data.get("query") or not query_data.get("table"):
                return {"status": "error", "message": "Missing query/table", "data": query_data}

            if "SELECT" not in query_data["query"].upper():
                return {"status": "error", "message": "Invalid query", "data": query_data}

            query_data["parameters"] = query_data.get("parameters", [])

            return {
                "status": "success",
                "table": query_data["table"],
                "query": query_data["query"],
                "parameters": query_data["parameters"]
            }

        except Exception as e:
            logger.exception("Bedrock query builder failed")
            return {"status": "error", "message": str(e)}
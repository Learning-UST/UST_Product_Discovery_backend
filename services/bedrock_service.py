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
    def invoke_model(self, payload: dict, model_id: str = None) -> dict:
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
    def generate(self, user_prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
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
            user_prompt=user_input,
            system_prompt=QUERY_BUILDER_SYSTEM_PROMPT,
        )

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
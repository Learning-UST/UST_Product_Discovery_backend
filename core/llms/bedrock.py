import json
import boto3
from core.base.llm_base import BaseLLM
from utils.config import get_config_value
from utils.logger import get_logger
from core.prompts import QUERY_BUILDER_SYSTEM_PROMPT


logger = get_logger()


class BedrockLLMService(BaseLLM):

    def __init__(self):
        self.region = get_config_value("AWS_REGION")
        self.model_id = get_config_value("BEDROCK_MODEL_ID")  # e.g. anthropic.claude-3-sonnet

        self.client = boto3.client("bedrock-runtime", region_name=self.region)

        logger.info("AWS Bedrock initialized...")

    def generate(self, system_prompt: str, user_prompt: str) -> str:

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.2
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(payload)
        )

        body = json.loads(response["body"].read())

        # ⚠️ depends on model (Claude, Titan etc.)
        return body.get("content", [{}])[0].get("text", "")

    def get_embedding(self, text: str):

        payload = {
            "inputText": text
        }

        response = self.client.invoke_model(
            modelId="amazon.titan-embed-text-v1",
            body=json.dumps(payload)
        )

        body = json.loads(response["body"].read())

        return body.get("embedding", [])

    def query_builder(self, message: str, content: str = ""):

        try:

            payload = {
                "messages": [
                    {"role": "system", "content": QUERY_BUILDER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"message: {message}\n\ncontent: {content}"}
                ],
                "temperature": 0
            }

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(payload)
            )

            body = json.loads(response["body"].read())
            content = body.get("content", [{}])[0].get("text", "").strip()

            try:
                query_data = json.loads(content)
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
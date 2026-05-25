import json

import boto3
from utils.config import get_config_value
from utils.logger import get_logger
from services.openai_service import QUERY_BUILDER_SYSTEM_PROMPT, SYSTEM_PROMPT

logger = get_logger()


class BedrockLLMService:
    def __init__(self):
        self.region = get_config_value("AWS_REGION") or get_config_value("AWS_BEDROCK_REGION")
        self.model_id = get_config_value("AWS_BEDROCK_CHAT_MODEL")
        self.embedding_model_id = get_config_value("AWS_BEDROCK_EMBEDDING_MODEL")

        missing = []
        if not self.region:
            missing.append("AWS_REGION or AWS_BEDROCK_REGION")
        if not self.model_id:
            missing.append("AWS_BEDROCK_CHAT_MODEL")
        if not self.embedding_model_id:
            missing.append("AWS_BEDROCK_EMBEDDING_MODEL")
        if missing:
            raise ValueError(f"Missing AWS Bedrock configuration: {', '.join(missing)}")

        self.client = boto3.client("bedrock-runtime", region_name=self.region)
        logger.info("BedrockLLMService initialized")

    def _invoke_json(self, model_id: str, payload: dict) -> dict:
        response = self.client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload),
        )
        body = response.get("body")
        raw = body.read() if hasattr(body, "read") else body
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def _extract_text(self, response_json: dict) -> str:
        content = response_json.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")
        if "outputText" in response_json:
            return response_json.get("outputText", "")
        return ""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "system": system_prompt,
            "messages": [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
            "temperature": 0.2,
            "max_tokens": 1024,
        }
        response = self._invoke_json(self.model_id, payload)
        return self._extract_text(response)

    def build_context(self, documents: list) -> str:
        context_lines = []
        for d in documents:
            line = (
                f"Product ID: {d.get('id')}\n"
                f"Name: {d.get('name')}\n"
                f"Brand: {d.get('brand')}\n"
                f"Category: {d.get('category')}\n"
                f"Description: {d.get('description')}\n"
                f"Price: {d.get('price')}\n"
                f"Discounted Price: {d.get('discounted_price')}\n"
            )
            context_lines.append(line.strip())
        return "\n\n".join(context_lines)

    def build_prompt(self, query: str, history: str, context: str) -> str:
        return (
            "Conversation History (chronological list):\n"
            f"{history}\n\n"
            "Context:\n"
            f"{context}\n\n"
            "User Question:\n"
            f"{query}\n\n"
            "Answer:"
        )

    def generate_answer(self, query: str, history: str, context_docs: list) -> str:
        context_text = self.build_context(context_docs)
        prompt = self.build_prompt(query, history, context_text)
        return self.generate(SYSTEM_PROMPT, prompt)

    def get_embedding(self, text: str):
        payload = {"inputText": text}
        response = self._invoke_json(self.embedding_model_id, payload)
        return response.get("embedding", [])

    def query_builder(self, message: str, content: str = "") -> dict:
        prompt = f" message: {message}\n\n content: {content}"
        raw = self.generate(QUERY_BUILDER_SYSTEM_PROMPT, prompt).strip()

        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()

        try:
            query_data = json.loads(raw)
        except Exception:
            logger.error("Invalid JSON from Bedrock query builder")
            return {"status": "error", "message": "Failed to parse query", "raw": raw}

        table = query_data.get("table")
        mongo_filter = query_data.get("mongo_filter") or query_data.get("filter") or {}
        if not table:
            return {"status": "error", "message": "Missing table", "data": query_data}

        return {
            "status": "success",
            "table": table,
            "query": query_data.get("query", "SELECT * FROM c"),
            "parameters": query_data.get("parameters", []),
            "mongo_filter": mongo_filter if isinstance(mongo_filter, dict) else {},
        }

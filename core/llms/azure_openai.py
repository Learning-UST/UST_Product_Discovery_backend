from openai import OpenAI
from core.base.llm_base import BaseLLM
from utils.config import get_config_value
from utils.logger import get_logger
import httpx
import json
from core.prompts import QUERY_BUILDER_SYSTEM_PROMPT


logger = get_logger()


class AzureOpenAIService(BaseLLM):

    def __init__(self):
        self.endpoint = get_config_value("AZURE_OPENAI_ENDPOINT")
        self.api_key = get_config_value("AZURE_OPENAI_API_KEY")
        self.deployment = get_config_value("AZURE_OPENAI_DEPLOYMENT")

        self.client = OpenAI(
            base_url=f"{self.endpoint}/openai/v1",
            api_key=self.api_key,
            http_client=httpx.Client()
        )

        logger.info("Azure OpenAI initialized...")

    def generate(self, system_prompt: str, user_prompt: str) -> str:

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )

        return response.choices[0].message.content

    def get_embedding(self, text: str):

        response = self.client.embeddings.create(
            model=get_config_value("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            input=text
        )

        return response.data[0].embedding

    def query_builder(self, message: str, content: str = ""):

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": QUERY_BUILDER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"message: {message}\n\ncontent: {content}"}
                ],
                temperature=0
            )

            content = response.choices[0].message.content.strip()

            try:
                query_data = json.loads(content)
            except Exception:
                logger.error("Invalid JSON from GPT", content=content)
                return {"status": "error", "message": "Failed to parse query", "raw": content}

            if not query_data.get("query") or not query_data.get("table"):
                return {"status": "error", "message": "Missing query/table", "data": query_data}

            if "SELECT" not in query_data["query"].upper():
                return {"status": "error", "message": "Invalid query generated", "data": query_data}

            query_data["parameters"] = query_data.get("parameters", [])

            return {
                "status": "success",
                "table": query_data["table"],
                "query": query_data["query"],
                "parameters": query_data["parameters"]
            }

        except Exception as e:
            logger.exception("Query builder failed")
            return {"status": "error", "message": str(e)}
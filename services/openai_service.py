from openai import OpenAI
from utils.config import get_config_value
import json
import httpx
from core.prompts import SYSTEM_PROMPT, QUERY_BUILDER_SYSTEM_PROMPT
from utils.logger import get_logger


logger = get_logger()




class OpenAIService:

    def __init__(self):
        self.endpoint = get_config_value("AZURE_OPENAI_ENDPOINT")
        self.api_key = get_config_value("AZURE_OPENAI_API_KEY")
        self.deployment = get_config_value("AZURE_OPENAI_DEPLOYMENT")

        self.client = OpenAI(
            base_url=f"{self.endpoint}/openai/v1",
            api_key=self.api_key,
            http_client=httpx.Client()
        )

        logger.info("OpenAI initialized...")

    def build_context(self, documents: list) -> str:
        context_lines = []

        for d in documents:
            line = f"""
                    Product ID: {d.get('id')}
                    Name: {d.get('name')}
                    Brand: {d.get('brand')}
                    Category: {d.get('category')}
                    Description: {d.get('description')}
                    Price: ₹{d.get('price')}
                    Discounted Price: ₹{d.get('discounted_price')}
                    Veg: {"Yes" if d.get('veg') else "No"}
                    Nutrition: {d.get('nutrition')}
                    """
            context_lines.append(line.strip())

        return "\n\n".join(context_lines)

    # ✅ Generate prompt

    def build_prompt(self, query: str, history: str, context: str) -> str:
        return f"""
            Conversation History (chronological list):
            {history}

            Context:
            {context}

            User Question:
            {query}

            Answer:
            """

    # ✅ Main RAG method
    def generate_answer(self, query: str,history: str, context_docs: list) -> str:
        context_text = self.build_context(context_docs)
        prompt = self.build_prompt(query, history, context_text)
        logger.info(f"Final Prompt: {prompt}")
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2  # ✅ stable production response
        )
        asssitant_response = response.choices[0].message.content
        logger.info(f"Assitant Response: {asssitant_response}")
        return asssitant_response


    def get_embedding(self,text: str):
        response = self.client.embeddings.create(
            model=get_config_value("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            input=text
        )
        return response.data[0].embedding


    def query_builder(self, message: str, content: str = "") -> dict:
        """
        Generates:
        - Cosmos DB SQL query
        - Target table name
        """

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": QUERY_BUILDER_SYSTEM_PROMPT},
                    {"role": "user", "content": f" message: {message}\n\n content: {content}"}
                ],
                temperature=0
            )

            content = response.choices[0].message.content.strip()

            # ✅ Parse JSON safely
            try:
                query_data = json.loads(content)
            except Exception:
                logger.error("Invalid JSON from GPT", content=content)
                return {
                    "status": "error",
                    "message": "Failed to parse query",
                    "raw": content
                }

            # ✅ Validation
            if not query_data.get("query") or not query_data.get("table"):
                return {
                    "status": "error",
                    "message": "Missing query/table",
                    "data": query_data
                }

            if "SELECT" not in query_data["query"].upper():
                return {
                    "status": "error",
                    "message": "Invalid query generated",
                    "data": query_data
                }

            # ✅ Ensure parameters exist
            query_data["parameters"] = query_data.get("parameters", [])

            return {
                "status": "success",
                "table": query_data["table"],
                "query": query_data["query"],
                "parameters": query_data["parameters"]
            }

        except Exception as e:
            logger.exception("Query builder failed")
            return {
                "status": "error",
                "message": str(e)
            }
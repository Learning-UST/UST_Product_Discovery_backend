from openai import OpenAI
from config import get_config_value


class OpenAIService:

    def __init__(self):
        self.endpoint = get_config_value("AZURE_OPENAI_ENDPOINT")
        self.api_key = get_config_value("AZURE_OPENAI_API_KEY")
        self.deployment = get_config_value("AZURE_OPENAI_DEPLOYMENT")

        self.client = OpenAI(
            base_url=f"{self.endpoint}/openai/v1",
            api_key=self.api_key
        )

    # ✅ Build structured context
    def build_context(self, documents: list) -> str:
        context_lines = []

        for d in documents:
            planogram = d.get("planogram_info", {})

            context_lines.append(
                f"{d.get('product_name', 'N/A')} - "
                f"{d.get('description', 'N/A')} - "
                f"Aisle:{planogram.get('aisle', 'N/A')} "
                f"Shelf:{planogram.get('shelf', 'N/A')}"
            )

        return "\n".join(context_lines)

    # ✅ Generate prompt
    def build_prompt(self, query: str, context: str) -> str:
        return f"""
You are a retail assistant helping with planogram navigation.

Context:
{context}

User Query:
{query}

Instructions:
- Answer ONLY from the context
- If not found, say "Product not found in store"
- Be concise and clear
"""

    # ✅ Main RAG method
    def generate_answer(self, query: str, context_docs: list) -> str:
        context_text = self.build_context(context_docs)
        prompt = self.build_prompt(query, context_text)

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": "You are a helpful retail assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2  # ✅ stable production response
        )

        return response.choices[0].message.content
        
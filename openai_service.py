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
    def build_prompt(self, query: str, context: str) -> str:
        prompt = f"""
            You are a retail shopping assistant helping customers with product details such as price, offers, availability, and nutritional information. 
            You will receive product information from a vector database.

            Context:
            {context}

            User Query:
            {query}

            Instructions:
            - Answer ONLY using the provided context
            - Do not make up any information
            - If the product is not found, respond with: "Product not found in store"
            - Provide clear, concise, and helpful answers
            - Include relevant details such as price, discounts, veg/non-veg status, and nutrition when available
            """


        return prompt

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
        
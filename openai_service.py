from openai import OpenAI
from config import get_config_value
import json

from logger import get_logger
from tools import get_product_details_tool, search_products_tool

logger = get_logger()


SYSTEM_PROMPT = """
You are a retail shopping assistant that provides accurate product information based ONLY on the given context.

Rules:
- Use strictly the provided context to answer the question.
- Do NOT invent or assume any information not present in the context.
- If the requested product is present but the information of that product is missing :
  Try to give teh relevent or related information or give I don't have the specific information.
- If the requested product are missing in the store respond exactly with:
  "Product not found in store"
- If the requested product is not in a shelf but it is present in the store then :
  "[product name] is not present on the shelf but is available in the store. it is available in [shelf name]".
- Be concise, clear, and helpful.
"""


class OpenAIService:

    def __init__(self):
        self.endpoint = get_config_value("AZURE_OPENAI_ENDPOINT")
        self.api_key = get_config_value("AZURE_OPENAI_API_KEY")
        self.deployment = get_config_value("AZURE_OPENAI_DEPLOYMENT")

        self.client = OpenAI(
            base_url=f"{self.endpoint}/openai/v1",
            api_key=self.api_key
        )

        logger.info("OpenAI initialized...")

    def get_master_prompt(self):
        return """
        You are the 'SmartRetail Assistant', a highly capable AI agent for a modern retail store.
        Your goal is to provide a seamless shopping experience by acting as an intermediary between the customer and the store's digital twin.

        COMMANDS & TOOLS:
        - If a user wants to find a product category (e.g., 'snacks'): Use search_products_tool.
        - If a user asks about a specific item's price/stock: Use get_product_details_tool.
        - If a user asks for their location or shelf layout: Use get_shelf_layout_tool.

        STRICT RULES:
        1. INVENTORY: Always verify 'stock_status' from the tool before telling a user they can buy an item.
        2. PRICING: Only report the 'final_price'. If a promotion is applied, mention the 'Promotion Name' as a bonus.
        3. VOICE: Keep responses concise (under 3 sentences) because the user is likely listening via speech-to-text.
        4. MISSING DATA: If the tool returns 'Out of Stock', still provide nutritional info but suggest they check back later.
        """

    def run_orchestrator(self, user_query):
        # This is where the Agentic decision happens
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_product_details",
                    "description": "Get real-time price and stock for a specific UPC",
                    "parameters": {
                        "type": "object",
                        "properties": {"upc": {"type": "string"}},
                        "required": ["upc"]
                    }
                }
            },
            # Add more tools (search_products, get_shelf_layout) here...
        ]

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": self.get_master_prompt()},
                {"role": "user", "content": user_query}
            ],
            tools=tools,
            tool_choice="auto"
        )
        return response.choices[0].message


    def get_agent_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_product_details_tool",
                    "description": "Use this to check stock, price, and ingredients for a specific item.",
                    "parameters": {
                        "type": "object",
                        "properties": {"upc": {"type": "string"}},
                        "required": ["upc"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_products_tool",
                    "description": "Use this for general questions like 'find me snacks' or 'healthy food'.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"]
                    }
                }
            }
        ]

    def generate_agentic_answer(self, query):
        messages = [
            {"role": "system", "content": "You are a retail agent. Use tools to provide real-time data. Always report stock status and final price."},
            {"role": "user", "content": query}
        ]

        # 1. First call to see if a tool is needed
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            tools=self.get_agent_tools(),
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # 2. If the Agent decided to use a tool
        if tool_calls:
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                # Execute the tool
                if function_name == "get_product_details_tool":
                    result = get_product_details_tool(args.get("upc"))
                else:
                    result = search_products_tool(args.get("query"))

                messages.append(response_message)
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(result)
                })

            # 3. Get final natural language response
            final_response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages
            )
            return final_response.choices[0].message.content
        
        return response_message.content

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
        return f"""
            Context:
            {context}

            User Question:
            {query}

            Answer:
            """

    # ✅ Main RAG method
    def generate_answer(self, query: str, context_docs: list) -> str:
        context_text = self.build_context(context_docs)
        prompt = self.build_prompt(query, context_text)
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


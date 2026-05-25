from openai import OpenAI
from utils.config import get_config_value
import json
import httpx


from utils.logger import get_logger
# from tools import get_product_details_tool, search_products_tool

logger = get_logger()


SYSTEM_PROMPT = """
You are a retail shopping assistant that provides accurate product information based ONLY on the given context.

Rules:
- Use strictly the provided context to answer the question.
- Do NOT invent or assume any information not present in the context.
- If the requested product is present but its information is missing:
  - Provide relevant or related information if available.
  - Otherwise respond: "I don't have the specific information."
- If the requested product is not present in the store, respond exactly with:
  "Product not found in store"
- If the requested product is not on the shelf but exists in the store, respond exactly with:
  "[product name] is not present on the shelf but is available in the store. It is available in [shelf name]."
- Be concise, clear, and helpful.
"""


QUERY_BUILDER_SYSTEM_PROMPT = """
You are an expert Cosmos DB query builder.

Your task:
1. Understand user request
2. Identify correct table: products, inventory, promotion
3. Generate SAFE parameterized Cosmos SQL query
4. you will get some content which is the output of AI search tool, you can use that to build better query

Rules:
- Always use SELECT * FROM c
- NEVER inline values → use parameters @p1, @p2...
- Use:
  - CONTAINS(c.field, @p) → for text search
  - ARRAY_CONTAINS(c.field, @p) → for arrays
  - Direct comparisons for numbers

Tables:

products:
Fields: Name, Brand, Category, Description, Nutritional_Facts.Calories, Ingredients, Allergens, Health_Labels, Veg

inventory:
Fields: UPC, Price, US_Price, Quantity, store_id

promotion:
Fields: Promotion_Name, Scope_Type, Scope_Value, Discount_Percentage, Start_Date, End_Date, isPromotion

Output STRICT JSON:
{
  "table": "products|inventory|promotion",
  "query": "SELECT ...",
  "parameters": [
    {"name": "@p1", "value": "..."}
  ]
}
"""

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

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Unified LLM interface used by provider-agnostic wrappers."""
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content

    # def get_master_prompt(self):
    #     return """
    #     You are the 'SmartRetail Assistant', a highly capable AI agent for a modern retail store.
    #     Your goal is to provide a seamless shopping experience by acting as an intermediary between the customer and the store's digital twin.

    #     COMMANDS & TOOLS:
    #     - If a user wants to find a product category (e.g., 'snacks'): Use search_products_tool.
    #     - If a user asks about a specific item's price/stock: Use get_product_details_tool.
    #     - If a user asks for their location or shelf layout: Use get_shelf_layout_tool.

    #     STRICT RULES:
    #     1. INVENTORY: Always verify 'stock_status' from the tool before telling a user they can buy an item.
    #     2. PRICING: Only report the 'final_price'. If a promotion is applied, mention the 'Promotion Name' as a bonus.
    #     3. VOICE: Keep responses concise (under 3 sentences) because the user is likely listening via speech-to-text.
    #     4. MISSING DATA: If the tool returns 'Out of Stock', still provide nutritional info but suggest they check back later.
    #     """

    # def run_orchestrator(self, user_query):
    #     # This is where the Agentic decision happens
    #     tools = [
    #         {
    #             "type": "function",
    #             "function": {
    #                 "name": "get_product_details",
    #                 "description": "Get real-time price and stock for a specific UPC",
    #                 "parameters": {
    #                     "type": "object",
    #                     "properties": {"upc": {"type": "string"}},
    #                     "required": ["upc"]
    #                 }
    #             }
    #         },
    #         # Add more tools (search_products, get_shelf_layout) here...
    #     ]

    #     response = self.client.chat.completions.create(
    #         model=self.deployment,
    #         messages=[
    #             {"role": "system", "content": self.get_master_prompt()},
    #             {"role": "user", "content": user_query}
    #         ],
    #         tools=tools,
    #         tool_choice="auto"
    #     )
    #     return response.choices[0].message


    # def get_agent_tools(self):
    #     return [
    #         {
    #             "type": "function",
    #             "function": {
    #                 "name": "get_product_details_tool",
    #                 "description": "Use this to check stock, price, and ingredients for a specific item.",
    #                 "parameters": {
    #                     "type": "object",
    #                     "properties": {"upc": {"type": "string"}},
    #                     "required": ["upc"]
    #                 }
    #             }
    #         },
    #         {
    #             "type": "function",
    #             "function": {
    #                 "name": "search_products_tool",
    #                 "description": "Use this for general questions like 'find me snacks' or 'healthy food'.",
    #                 "parameters": {
    #                     "type": "object",
    #                     "properties": {"query": {"type": "string"}},
    #                     "required": ["query"]
    #                 }
    #             }
    #         }
    #     ]

    # def generate_agentic_answer(self, query):
    #     messages = [
    #         {"role": "system", "content": "You are a retail agent. Use tools to provide real-time data. Always report stock status and final price."},
    #         {"role": "user", "content": query}
    #     ]

    #     # 1. First call to see if a tool is needed
    #     response = self.client.chat.completions.create(
    #         model=self.deployment,
    #         messages=messages,
    #         tools=self.get_agent_tools(),
    #         tool_choice="auto"
    #     )

    #     response_message = response.choices[0].message
    #     tool_calls = response_message.tool_calls

    #     # 2. If the Agent decided to use a tool
    #     if tool_calls:
    #         for tool_call in tool_calls:
    #             function_name = tool_call.function.name
    #             args = json.loads(tool_call.function.arguments)
                
    #             # Execute the tool
    #             if function_name == "get_product_details_tool":
    #                 result = get_product_details_tool(args.get("upc"))
    #             else:
    #                 result = search_products_tool(args.get("query"))

    #             messages.append(response_message)
    #             messages.append({
    #                 "tool_call_id": tool_call.id,
    #                 "role": "tool",
    #                 "name": function_name,
    #                 "content": json.dumps(result)
    #             })

    #         # 3. Get final natural language response
    #         final_response = self.client.chat.completions.create(
    #             model=self.deployment,
    #             messages=messages
    #         )
    #         return final_response.choices[0].message.content
        
    #     return response_message.content

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
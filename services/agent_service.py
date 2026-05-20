import json
from agent.retriever import Retriever
from agent.prompt import build_context, build_prompt, format_history, SYSTEM_PROMPT
from agent.llm_service import LLMService
from agent.query_rewriter import QueryRewriter
from utils.logger import get_logger

logger = get_logger()

class ShoppingAgent:

    def __init__(self):
        self.retriever = Retriever()
        self.llm = LLMService()  # Your existing service that handles Azure connections
        self.rewriter = QueryRewriter()

    def ask(self, query: str, history: list):
        # Step 1: Rewrite query using conversation history
        rewritten_query = self.rewriter.rewrite(query, history)

        logger.info(f"Original Query: {query}")
        logger.info(f"Rewritten Query: {rewritten_query}")

        # Step 2: Define tools/functions for the LLM Router
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "retrieve_products",
                    "description": "Call this to search the product inventory database for specific items, tags, nutritional values (like gluten-free, low calorie), categories, or pricing.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search_term": {
                                "type": "string",
                                "description": "The optimized search keyword extracted from the user's intent."
                            }
                        },
                        "required": ["search_term"]
                    }
                }
            }
        ]

        # Step 3: Format conversation message history for the router
        messages = [
            {"role": "system", "content": "You are a smart retail assistant. You can handle generalized conversations directly. If the user is asking about product data, inventory, dietary preferences (like gluten-free), or specific properties (like calories), you MUST use the 'retrieve_products' tool first. Mention price only when the user asks for price/cost/value/discount. When you mention any price, never return a bare number: always include the currency symbol from 'currency_symbol' and prefer 'display_price'/'display_discounted_price' fields when available."}
        ]
        
        for msg in history:
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", "user")
            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
            messages.append({"role": role, "content": content})
            
        messages.append({"role": "user", "content": rewritten_query})

        # Step 4: Use your existing LLMService to generate the tool routing decision safely
        # We pass the tools structural arguments directly to your existing completion generator wrapper
        try:
            # Check if your LLMService supports passing raw tools natively
            # If your llm.generate method doesn't take tools, we call its internal client object safely:
            if hasattr(self.llm, 'client') and self.llm.client:
                response = self.llm.client.chat.completions.create(
                    model=self.llm.model_name if hasattr(self.llm, 'model_name') else "gpt-4o-mini",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
            else:
                # If your service initializes via the AzureOpenAI sdk client class directly:
                from openai import AzureOpenAI
                import os
                
                # Instantiating locally using standard environment configurations mapped by your deployment scripts
                azure_client = AzureOpenAI(
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                    api_version="2024-02-01"
                )
                response = azure_client.chat.completions.create(
                    model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
        except Exception as e:
            logger.error(f"Failed router execution sequence: {str(e)}")
            # Robust fallback: If tool orchestration fails completely under pressure, default gracefully to standard sequential retrieval
            docs = self.retriever.retrieve(rewritten_query)
            prompt = build_prompt(query, history, docs)
            fallback_res = self.llm.generate(SYSTEM_PROMPT, prompt)
            return fallback_res, docs

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        docs = []

        # Step 5: Process Agent Router Decision Tree
        if tool_calls:
            logger.info("Agent router triggered inventory retrieval path.")
            messages.append(response_message)

            for tool_call in tool_calls:
                function_args = json.loads(tool_call.function.arguments)
                search_term = function_args.get("search_term", rewritten_query)
                
                # Execute original retrieval logic 
                docs = self.retriever.retrieve(search_term)
                logger.info(f"Retrieved docs for agent: {docs}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": "retrieve_products",
                    "content": json.dumps(docs)
                })

            # Fetch the final summary execution response from Azure OpenAI
            if 'azure_client' in locals():
                second_response = azure_client.chat.completions.create(
                    model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
                    messages=messages
                )
            else:
                second_response = self.llm.client.chat.completions.create(
                    model=self.llm.model_name if hasattr(self.llm, 'model_name') else "gpt-4o-mini",
                    messages=messages
                )
                
            return second_response.choices[0].message.content, docs

        else:
            # Generalized query route (No database search needed!)
            logger.info("Agent handled query as a generalized question directly.")
            return response_message.content, []
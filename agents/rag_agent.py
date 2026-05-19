"""
RAG Agent
"""

from autogen import AssistantAgent, register_function

from config.autogen_config import get_agent_config
from tools.rag_tools import search_products_tool
import json

class ProductRAGAgent:
    def __init__(self):
        self.agent = self._create_agent()
        self._register_tools()

    # ✅ Create LLM agent
    def _create_agent(self) -> AssistantAgent:
        system_prompt = """You are a product assistant.

STRICT RULES:
- ALWAYS call `search_products` tool before answering
- NEVER answer from memory
- ONLY use retrieved product data
- If no data is found, say: "No relevant product information found"
"""

        agent_config = get_agent_config(
            agent_name="ProductRAGAgent",
            system_message=system_prompt
        )

        return AssistantAgent(
            name=agent_config["name"],
            system_message=agent_config["system_message"],
            llm_config=agent_config["llm_config"],
            human_input_mode=agent_config["human_input_mode"],
            max_consecutive_auto_reply=agent_config["max_consecutive_auto_reply"],
            code_execution_config=agent_config["code_execution_config"],
        )

    # ✅ Register tools properly
    def _register_tools(self):
        register_function(
            search_products_tool,   # ✅ plain function (FIXED)
            caller=self.agent,
            executor=self.agent,
            name="search_products",
            description="Search product data using Azure AI Search"
        )

    # ✅ Chat method
    def chat(self, message: str) -> str:
        messages = [{"role": "user", "content": message}]

        while True:
            response = self.agent.generate_reply(messages=messages)

            print(f"✅ RAW RESPONSE: {response}")

            # ✅ CASE 1: Final response is STRING → STOP
            if isinstance(response, str):
                return response

            # ✅ CASE 2: Final response inside dict → STOP
            if isinstance(response, dict) and response.get("content"):
                return response["content"]

            # ✅ CASE 3: Tool call
            if isinstance(response, dict) and response.get("tool_calls"):

                # ✅ IMPORTANT: append assistant message ONLY once
                messages.append(response)

                for tool_call in response["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])

                    if function_name == "search_products":
                        tool_result = search_products_tool(arguments["query"])

                    # ✅ ensure string
                    assert isinstance(tool_result, str)

                    messages.append({
                        "role": "tool",
                        "content": tool_result,
                        "tool_call_id": tool_call["id"]
                    })

            else:
                return "No response generated."
            
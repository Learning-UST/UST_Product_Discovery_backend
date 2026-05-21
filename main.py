"""
Main Script to test ShoppingAgent
"""

import json
from services.agent_service import ShopilotAgent


def main():
    agent = ShopilotAgent()

    # ✅ Store conversation history
    history = []

    print("🛒 Shopping Assistant Started (type 'exit' to quit)\n")

    while True:
        try:
            # ✅ User input
            user_input = input("👤 You: ").strip()

            if user_input.lower() in ["exit", "quit"]:
                print("👋 Exiting Shopping Assistant")
                break

            if not user_input:
                continue

            # ✅ Add user message to history
            history.append({
                "role": "user",
                "content": user_input
            })

            # ✅ Get agent response
            response = agent.chat(user_input, history)

            print(f"🤖 Assistant: {response}\n")

            # ✅ Add assistant message to history
            history.append({
                "role": "assistant",
                "content": response
            })

        except KeyboardInterrupt:
            print("\n👋 Interrupted. Exiting...")
            break

        except Exception as e:
            print(f"❌ Error: {str(e)}")

    # ✅ Save history to file
    # with open("chat_history.json", "w") as f:
    #     json.dump(history, f, indent=2)

    # print("💾 Chat history saved to chat_history.json")


if __name__ == "__main__":
    main()
# prompt.py

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


def build_context(documents: list) -> str:
    lines = []

    for d in documents:
        lines.append(f"""
Product ID: {d.get('id')}
Name: {d.get('name')}
Brand: {d.get('brand')}
Category: {d.get('category')}
Description: {d.get('description')}
Price: ₹{d.get('price')}
Discounted Price: ₹{d.get('discounted_price')}
Veg: {"Yes" if d.get('veg') else "No"}
Nutrition: {d.get('nutrition')}
""".strip())

    return "\n\n".join(lines)


def build_prompt(query: str, history: str, context: str) -> str:
    return f"""
Conversation History (chronological list):
{history}

Context:
{context}

User Question:
{query}

Answer:
"""

def format_history(history:list) ->str:
    return "\n".join(history)
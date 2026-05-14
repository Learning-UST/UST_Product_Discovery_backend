# prompt.py

SYSTEM_PROMPT = """
You are a retail shopping assistant that provides accurate product information based ONLY on the given context.

Rules:
- Use strictly the provided context to answer the question.
- Do NOT invent any information.
- If product not found → "Product not found in store"
- If product exists but missing info → "I don't have the specific information."
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
Conversation History:
{history}

Context:
{context}

User Question:
{query}

Answer:
"""

def format_history(history:list) ->str:
    return "\n".join(history)
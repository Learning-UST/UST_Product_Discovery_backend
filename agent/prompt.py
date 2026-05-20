# prompt.py

from utils.config import get_config_value

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
  "[product name] is not present on the shelf but is available in the store. It is available on [shelf name]."
- Be concise, clear, and helpful.
"""


def _select_chat_prices(doc: dict):
    source = str(get_config_value("PRICE_SOURCE", "NORMAL")).strip().upper()
    source = source if source in {"NORMAL", "US"} else "NORMAL"

    normal_price = doc.get("price")
    us_price = doc.get("us_price", doc.get("US_Price"))
    normal_discounted_price = doc.get("discounted_price")
    us_discounted_price = doc.get("us_discounted_price")

    if source == "US":
        selected_price = us_price if us_price is not None else normal_price
        selected_discounted_price = (
            us_discounted_price
            if us_discounted_price is not None
            else normal_discounted_price
        )
    else:
        selected_price = normal_price if normal_price is not None else us_price
        selected_discounted_price = (
            normal_discounted_price
            if normal_discounted_price is not None
            else us_discounted_price
        )

    return source, normal_price, us_price, selected_price, selected_discounted_price


def build_context(documents: list) -> str:
    lines = []

    for d in documents:
        source, normal_price, us_price, selected_price, selected_discounted_price = _select_chat_prices(d)
        lines.append(f"""
Product ID: {d.get('id')}
Name: {d.get('name')}
Brand: {d.get('brand')}
Category: {d.get('category')}
Description: {d.get('description')}
Configured Price Source: {source}
Normal Price: ₹{normal_price}
US Price: ₹{us_price}
Price: ₹{selected_price}
Discounted Price: ₹{selected_discounted_price}
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
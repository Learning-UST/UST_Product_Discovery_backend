

from typing import Any, List, Dict
from utils.config import get_config_value
import re


def read_json(file_path="combined_output.json") -> List[Dict[str, Any]]:
    import json

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    formatted_data = []

    for item in data:
        metadata = item.get("metadata", {})
        promotion = item.get("promotion", {})

        formatted_data.append({
            "id": item.get("id"),
            "product_id": item.get("product_id"),

            # ✅ Product fields
            "name": item.get("name"),
            "brand": item.get("brand"),
            "category": item.get("category"),
            "description": item.get("description"),

            # ✅ Pricing
            "price": item.get("price"),
            "us_price": item.get("us_price"),
            "discounted_price": item.get("discounted_price"),
            "us_discounted_price": item.get("us_discounted_price"),

            # ✅ Inventory
            "stock": item.get("stock"),
            "store_id": item.get("store_id"),

            # ✅ Additional fields
            "image_url": item.get("image_url"),
            "country_of_origin": item.get("country_of_origin"),
            "shelf_life": item.get("shelf_life"),

            # ✅ Promotion (flattened)
            "promotion_name": promotion.get("name") if promotion else None,
            "discount_percentage": promotion.get("discount_percentage") if promotion else None,

            # ✅ Metadata (flattened)
            "veg": metadata.get("veg", False),
            "age_restricted": metadata.get("age_restricted", False),
            "color": metadata.get("color"),

            "nutrition": json.dumps(metadata.get("nutrition", {})),

            "ingredients": metadata.get("ingredients", []),
            "allergens": metadata.get("allergens", []),
            "health_labels": metadata.get("health_labels", []),

            "serving_size": metadata.get("serving_size")
        })

    return formatted_data

# ✅ Result Formatter (Updated)
def format_result(r: dict) -> dict:
    return {
        "id": r.get("id"),
        "product_id": r.get("product_id"),
        "name": r.get("name"),
        "brand": r.get("brand"),
        "category": r.get("category"),
        "description": r.get("description"),

        # Pricing
        "price": r.get("price"),
        "us_price": r.get("us_price"),
        "discounted_price": r.get("discounted_price"),
        "us_discounted_price": r.get("us_discounted_price"),

        # Inventory
        "stock": r.get("stock"),
        "store_id": r.get("store_id"),

        # Product info
        "image_url": r.get("image_url"),
        "country_of_origin": r.get("country_of_origin"),
        "shelf_life": r.get("shelf_life"),

        # Promotion
        "promotion": {
            "name": r.get("promotion_name"),
            "discount_percentage": r.get("discount_percentage")
        } if r.get("promotion_name") else None,

        # Metadata
        "metadata": {
            "veg": r.get("veg"),
            "age_restricted": r.get("age_restricted"),
            "color": r.get("color"),
            "nutrition": r.get("nutrition"),
            "ingredients": r.get("ingredients"),
            "allergens": r.get("allergens"),
            "health_labels": r.get("health_labels"),
            "serving_size": r.get("serving_size")
        }
    }


#utils for db

def price_source() -> str:
    source = str(get_config_value("PRICE_SOURCE", "NORMAL")).strip().upper()
    return "US" if source == "US" else "NORMAL"

def currency_symbol() -> str:
    configured_symbol = get_config_value("PRICE_CURRENCY_SYMBOL")
    if configured_symbol is not None and str(configured_symbol).strip() != "":
        return str(configured_symbol).strip()
    return "$" if price_source() == "US" else "INR "

def pick_price_value(product: dict, inventory: dict):
    source = price_source()

    if source == "US":
        return (
            product.get("US_Price")
            or product.get("us_price")
            or inventory.get("US_Price")
            or inventory.get("us_price")
            or inventory.get("Price")
            or inventory.get("price")
        )

    return (
        inventory.get("Price")
        or inventory.get("price")
        or product.get("Price")
        or product.get("price")
    )

def format_product_info(data,promo):
    product = data['product']
    inventory = data['inventory']

    base_price = pick_price_value(product, inventory)

    return {
        "name": product["Name"],
        "brand": product["Brand"],
        "description": product["Description"],
        "ingredients": product.get("Ingredients"),
        "nutrition": product.get("Nutritional_Facts"),
        "stock_status": "In Stock" if inventory["Quantity"] > 0 else "Out of Stock",
        "quantity": inventory["Quantity"],
        "base_price": base_price,
        "final_price": promo['effective_price'],
        "currency_symbol": currency_symbol(),
        "applied_promotion": promo['promotion_name'],
        "image_url": product["image_url"]
    }


def normalize_price_fields(item: dict) -> dict:
    if not isinstance(item, dict):
        return item

    source = price_source()
    normalized = dict(item)

    if source == "US":
        price = normalized.get("us_price")
        discounted = normalized.get("us_discounted_price")
        if price is None:
            price = normalized.get("US_Price")
        if discounted is None:
            discounted = normalized.get("US_Discounted_Price")
    else:
        price = normalized.get("price")
        discounted = normalized.get("discounted_price")
        if price is None:
            price = normalized.get("Price")
        if discounted is None:
            discounted = normalized.get("Discounted_Price")

    if price is not None:
        normalized["display_price"] = price
    if discounted is not None:
        normalized["display_discounted_price"] = discounted

    normalized["currency_symbol"] = currency_symbol()
    return normalized

def normalize_result_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload

    normalized = dict(payload)
    results = normalized.get("results")
    if isinstance(results, list):
        normalized["results"] = [normalize_price_fields(r) for r in results]
    return normalized

def extract_product_names(answer_text: str) -> list:
    """Extract only the product names that are actually visible in the final answer."""
    if not answer_text:
        return []

    product_names = []
    seen = set()

    for raw_line in answer_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Remove leading numbering like "1." or "2)"
        line = re.sub(r"^\d+[\.)]\s*", "", line)

        # Skip intro/outro sentences
        if line.lower().startswith(("here are", "these options", "these are", "you can")):
            continue

        candidate = None

        # Handle formats like: "Product Name by Brand - Description"
        if " - " in line:
            candidate = line.split(" - ", 1)[0].strip()
        # Handle formats like: "Product Name: Description"
        elif ":" in line:
            candidate = line.split(":", 1)[0].strip()
        else:
            candidate = line.strip()

        # If we still have "Product Name by Brand", keep only the product name
        if " by " in candidate.lower():
            candidate = re.split(r"\s+by\s+", candidate, flags=re.IGNORECASE)[0].strip()

        # Final cleanup for short/obvious noise
        if candidate and len(candidate) > 2 and candidate not in seen:
            product_names.append(candidate)
            seen.add(candidate)

    return product_names
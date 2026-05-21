

from typing import Any, List, Dict
from utils.config import get_config_value


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

def price_source(self) -> str:
    source = str(get_config_value("PRICE_SOURCE", "NORMAL")).strip().upper()
    return "US" if source == "US" else "NORMAL"

def currency_symbol(self) -> str:
    configured_symbol = get_config_value("PRICE_CURRENCY_SYMBOL")
    if configured_symbol is not None and str(configured_symbol).strip() != "":
        return str(configured_symbol).strip()
    return "$" if self._price_source() == "US" else "INR "

def pick_price_value(self, product: dict, inventory: dict):
    source = self._price_source()

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
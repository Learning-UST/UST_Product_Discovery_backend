import json
from datetime import datetime,timezone
from utils.config import get_config_value

# ---------- Load JSON files ----------
def load_json(file_path):
    with open(file_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

promotions = load_json("promotion.json")
products = load_json("products.json")
inventory = load_json("inventory_new.json")

# ---------- Helper: check promotion validity ----------
def is_active(promo):
    today = datetime.now(timezone.utc).date()
    start = datetime.strptime(promo["Start_Date"], "%Y-%m-%d").date()
    end = datetime.strptime(promo["End_Date"], "%Y-%m-%d").date()
    return start <= today <= end

# ---------- Index inventory by UPC ----------
inventory_map = {item["UPC"]: item for item in inventory}

# ---------- Apply promotions ----------
def get_best_promo(product):
    applicable = []

    for promo in promotions:
        if not promo.get("isPromotion", False):
            continue
        if not is_active(promo):
            continue

        scope_type = promo["Scope_Type"]
        scope_value = promo["Scope_Value"]

        if scope_type == "Brand" and product.get("Brand") == scope_value:
            applicable.append(promo)
        elif scope_type == "Category" and product.get("Category") == scope_value:
            applicable.append(promo)
        elif scope_type == "Product" and str(product.get("Product_Id")) == str(scope_value):
            applicable.append(promo)

    if not applicable:
        return None

    applicable.sort(key=lambda x: x.get("Priority", 999))
    return applicable[0]

# ---------- Combine data ----------
price_source = str(get_config_value("PRICE_SOURCE", "NORMAL")).strip().upper()
if price_source not in {"NORMAL", "US"}:
    price_source = "US"

combined_data = []

for product in products:
    upc = product.get("UPC")
    inv = inventory_map.get(upc)

    if not inv:
        continue

    promo = get_best_promo(product)

    price = inv["Price"]
    us_price = inv.get("US_Price", inv.get("US_price"))

    price = inv.get("Price", 0)
    discounted_price = price
    us_discounted_price = us_price

    if promo:
        discount = promo.get("Discount_Percentage", 0)
        discounted_price = round(price * (1 - discount / 100), 2)
        if us_price is not None:
            us_discounted_price = round(us_price * (1 - discount / 100), 2)

    selected_price = us_price if price_source == "US" and us_price is not None else price
    selected_discounted_price = (
        us_discounted_price
        if price_source == "US" and us_discounted_price is not None
        else discounted_price
    )

    combined_item = {
        "id": product.get("id"),
        "product_id": product.get("Product_Id"),
        "name": product.get("Name"),
        "brand": product.get("Brand"),
        "category": product.get("Category"),
        "description": product.get("Description"),

        "price": price,
        "us_price": us_price,
        "discounted_price": discounted_price,
        "us_discounted_price": us_discounted_price,
        "selected_price": selected_price,
        "selected_discounted_price": selected_discounted_price,
        "price_source": price_source,
        "stock": inv.get("Quantity", 0),
        "store_id": inv.get("store_id"),

        "image_url": product.get("image_url"),
        "country_of_origin": product.get("Country_Of_Origin"),
        "shelf_life": product.get("Shelf_Life"),

        "promotion": {
            "name": promo.get("Promotion_Name"),
            "discount_percentage": promo.get("Discount_Percentage")
        } if promo else None,

        "metadata": {
            "veg": product.get("Veg"),
            "age_restricted": product.get("age_restricted"),
            "color": product.get("Colour"),

            "nutrition": product.get("Nutritional_Facts", {}),
            "ingredients": product.get("Ingredients", []),
            "allergens": product.get("Allergens", []),
            "preservatives": product.get("Preservatives", []),
            "health_labels": product.get("Health_Labels", []),

            "dimensions": {
                "height_cm": product.get("Height(cm)"),
                "width_cm": product.get("Width(cm)"),
                "depth_cm": product.get("Depth(cm)")
            },

            "serving_size": product.get("Serving_Size")
        }
    }

    combined_data.append(combined_item)

# ---------- Save output ----------
with open("combined_output_new.json", "w", encoding="utf-8") as f:
    json.dump(combined_data, f, indent=2, ensure_ascii=False)

print(f"✅ Combined {len(combined_data)} records into combined_output_new.json")
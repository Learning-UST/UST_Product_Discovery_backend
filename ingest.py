import json
from datetime import datetime,timezone

# ---------- Load JSON files ----------
def load_json(file_path):
    with open(file_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

promotions = load_json("promotion.json")
products = load_json("products.json")
inventory = load_json("inventory.json")

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

        if scope_type == "Brand" and product["Brand"] == scope_value:
            applicable.append(promo)
        elif scope_type == "Category" and product["Category"] == scope_value:
            applicable.append(promo)
        elif scope_type == "Product" and str(product["Product_Id"]) == str(scope_value):
            applicable.append(promo)

    if not applicable:
        return None

    # select by highest priority (lowest number = higher priority)
    applicable.sort(key=lambda x: x.get("Priority", 999))
    return applicable[0]

# ---------- Combine data ----------
combined_data = []

for product in products:
    upc = product["UPC"]
    inv = inventory_map.get(upc)

    if not inv:
        continue  # skip if no inventory

    promo = get_best_promo(product)

    price = inv["Price"]
    discounted_price = price

    if promo:
        discount = promo["Discount_Percentage"]
        discounted_price = round(price * (1 - discount / 100), 2)

    combined_item = {
        "id": product["id"],
        "name": product["Name"],
        "brand": product["Brand"],
        "category": product["Category"],
        "description": product["Description"],
        "price": price,
        "discounted_price": discounted_price,
        "stock": inv["Quantity"],
        "store_id": inv["store_id"],
        "promotion": {
            "name": promo["Promotion_Name"],
            "discount_percentage": promo["Discount_Percentage"]
        } if promo else None,
        "metadata": {
            "veg": product["Veg"],
            "nutrition": product["Nutritional_Facts"],
            "dimensions": {
                "height": product["Height(cm)"],
                "width": product["Width(cm)"],
                "depth": product["Depth(cm)"]
            }
        }
    }

    combined_data.append(combined_item)

# ---------- Save output ----------
with open("combined_output.json", "w") as f:
    json.dump(combined_data, f, indent=2)

print(f"✅ Combined {len(combined_data)} records into combined_output.json")
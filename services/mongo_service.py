import re
from pymongo import MongoClient
from utils.config import get_config_value


class MongoService:
    def __init__(self):
        self.mongo_uri = get_config_value("AWS_MONGODB_URI")
        self.db_name = get_config_value("AWS_MONGODB_DB_NAME")

        self.products_collection = get_config_value("AWS_MONGODB_PRODUCTS_COLLECTION", "products")
        self.inventory_collection = get_config_value("AWS_MONGODB_INVENTORY_COLLECTION", "inventory")
        self.promotion_collection = get_config_value("AWS_MONGODB_PROMOTION_COLLECTION", "promotion")
        self.layout_collection = get_config_value("AWS_MONGODB_LAYOUT_COLLECTION", "layout")

        missing = []
        if not self.mongo_uri:
            missing.append("AWS_MONGODB_URI")
        if not self.db_name:
            missing.append("AWS_MONGODB_DB_NAME")
        if missing:
            raise ValueError(f"Missing MongoDB configuration: {', '.join(missing)}")

        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        self.prod_ctr = self.db[self.products_collection]
        self.inv_ctr = self.db[self.inventory_collection]
        self.promo_ctr = self.db[self.promotion_collection]
        self.lay_ctr = self.db[self.layout_collection]

    def _price_source(self) -> str:
        source = str(get_config_value("PRICE_SOURCE", "NORMAL")).strip().upper()
        return "US" if source == "US" else "NORMAL"

    def _currency_symbol(self) -> str:
        configured_symbol = get_config_value("PRICE_CURRENCY_SYMBOL")
        if configured_symbol is not None and str(configured_symbol).strip() != "":
            return str(configured_symbol).strip()
        return "$" if self._price_source() == "US" else "INR "

    def _pick_price_value(self, product: dict, inventory: dict):
        source = self._price_source()
        product = product or {}
        inventory = inventory or {}

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

    def _normalize_upc(self, upc) -> str:
        if upc is None:
            return ""
        raw = str(upc).strip()
        if raw.upper().startswith("SKU_") or raw.upper().startswith("INV_"):
            raw = raw.split("_", 1)[1]
        return raw

    def _format_product_info(self, data):
        product = data.get("product") or {}
        inventory = data.get("inventory") or {}

        base_price = self._pick_price_value(product, inventory)
        effective_price, promo_name = self.resolve_effective_price(product, base_price)

        quantity = inventory.get("Quantity", inventory.get("quantity", 0))

        return {
            "name": product.get("Name") or product.get("name"),
            "brand": product.get("Brand") or product.get("brand"),
            "description": product.get("Description") or product.get("description"),
            "ingredients": product.get("Ingredients") or product.get("ingredients"),
            "nutrition": product.get("Nutritional_Facts") or product.get("nutrition"),
            "stock_status": "In Stock" if (quantity or 0) > 0 else "Out of Stock",
            "quantity": quantity,
            "base_price": base_price,
            "final_price": effective_price,
            "currency_symbol": self._currency_symbol(),
            "applied_promotion": promo_name,
            "image_url": product.get("image_url"),
            "upc": product.get("upc") or product.get("UPC") or inventory.get("upc") or inventory.get("UPC"),
        }

    def get_all_products(self):
        return self.clean_product_results(list(self.prod_ctr.find({}, {"_id": 0})))

    def get_shelf_layout(self, shelf_id):
        shelf_key = str(shelf_id)
        doc = self.lay_ctr.find_one(
            {"$or": [{"id": shelf_key}, {"shelf_id": shelf_key}, {"shelf_id": int(shelf_id) if str(shelf_id).isdigit() else shelf_key}]},
            {"_id": 0},
        )
        if not doc:
            raise ValueError("Shelf not found")
        return doc

    def get_product_and_inventory(self, upc):
        upc_str = self._normalize_upc(upc)
        product = self.prod_ctr.find_one(
            {"$or": [{"upc": upc_str}, {"UPC": upc_str}, {"id": f"SKU_{upc_str}"}]},
            {"_id": 0},
        )
        inventory = self.inv_ctr.find_one(
            {"$or": [{"upc": upc_str}, {"UPC": upc_str}, {"id": f"INV_{upc_str}"}]},
            {"_id": 0},
        )
        return {"product": product, "inventory": inventory}

    def resolve_effective_price(self, product_data, base_price):
        if base_price is None:
            return None, None

        product_data = product_data or {}
        brand = product_data.get("Brand") or product_data.get("brand")
        category = product_data.get("Category") or product_data.get("category")
        product_id = str(product_data.get("Product_Id") or product_data.get("product_id") or "")

        query = {
            "isPromotion": True,
            "$or": [
                {"Scope_Value": brand},
                {"Scope_Value": category},
                {"Scope_Value": product_id},
            ],
        }

        promos = list(self.promo_ctr.find(query, {"_id": 0}))
        if not promos:
            return base_price, None

        promos.sort(key=lambda x: x.get("Priority", 999))
        best_promo = promos[0]
        discount = best_promo.get("Discount_Percentage", 0) or 0

        try:
            effective_price = round(float(base_price) * (1 - float(discount) / 100.0), 2)
        except Exception:
            effective_price = base_price

        return effective_price, best_promo.get("Promotion_Name")

    def get_enriched_product_info(self, upc):
        data = self.get_product_and_inventory(upc)
        if not data.get("product"):
            raise ValueError("Product not found")
        return self._format_product_info(data)

    def get_product_by_name(self, product_name: str):
        regex = {"$regex": re.escape(product_name), "$options": "i"}
        products = list(self.prod_ctr.find({"$or": [{"Name": regex}, {"name": regex}]}, {"_id": 0}))
        if not products:
            return []

        results = []
        for product in products:
            upc = self._normalize_upc(product.get("upc") or product.get("UPC"))
            inventory = None
            if upc:
                inventory = self.inv_ctr.find_one(
                    {"$or": [{"upc": upc}, {"UPC": upc}, {"id": f"INV_{upc}"}]},
                    {"_id": 0},
                )
            results.append({"product": product, "inventory": inventory})
        return results

    def get_enriched_product_info_by_name(self, product_name):
        data = self.get_product_by_name(product_name)
        if not data:
            return None
        return self._format_product_info(data[0])

    def clean_product_results(self, data: list):
        fields_to_remove = {
            "_id",
            "_rid",
            "_self",
            "_etag",
            "_attachments",
            "_ts",
        }

        cleaned_results = []
        for item in data:
            cleaned_item = {key: value for key, value in item.items() if key not in fields_to_remove}
            cleaned_results.append(cleaned_item)

        return cleaned_results

    def query_executor(self, query_payload: dict, table_name: str = "products"):
        try:
            collection_map = {
                "products": self.prod_ctr,
                "inventory": self.inv_ctr,
                "promotion": self.promo_ctr,
                "layout": self.lay_ctr,
            }
            collection = collection_map.get(str(table_name).lower())
            if collection is None:
                raise ValueError(f"Invalid table_name: {table_name}")

            mongo_filter = query_payload.get("mongo_filter")
            if mongo_filter is None:
                mongo_filter = {}

            items = list(collection.find(mongo_filter, {"_id": 0}).limit(20))
            return {
                "status": "success",
                "table": table_name,
                "query": query_payload.get("query", "SELECT * FROM c"),
                "parameters": query_payload.get("parameters", []),
                "count": len(items),
                "results": self.clean_product_results(items),
            }
        except Exception as e:
            return {"status": "error", "table": table_name, "message": str(e)}

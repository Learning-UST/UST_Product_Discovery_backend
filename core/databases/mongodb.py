from pymongo import MongoClient
from core.base.db_base import BaseDatabase
from utils.config import get_config_value
from utils.logger import get_logger
from core.utils import format_product_info, pick_price_value


logger = get_logger()


class MongoDBService(BaseDatabase):

    def __init__(self):

        self.uri = get_config_value("MONGO_URI")
        self.db_name = get_config_value("MONGO_DB_NAME")

        if not self.uri or not self.db_name:
            raise ValueError("Missing MongoDB configuration")

        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]

        self.collections = {
            "products": self.db["products"],
            "inventory": self.db["inventory"],
            "promotion": self.db["promotion"],
            "layout": self.db["layout"]
        }

        logger.info("✅ MongoDB initialized")

    # ✅ ----------------------------
    # Internal Helpers
    # ✅ ----------------------------

    def _get_collection(self, name: str):
        collection = self.collections.get(name.lower())
        if not collection:
            raise ValueError(f"Invalid collection: {name}")
        return collection

    # ✅ ----------------------------
    # Base Methods
    # ✅ ----------------------------

    def get_item(self, key: str, table_name: str):
        try:
            collection = self._get_collection(table_name)
            return collection.find_one({"_id": key})
        except Exception as e:
            logger.error(f"Mongo get_item failed: {e}")
            return None

    def query_executor(self, query: dict, table_name: str = "products"):

        """
        MongoDB Query Executor
        Expected query format:
        {
            "filter": {...},
            "projection": {...},   # optional
            "limit": 20            # optional
        }
        """

        try:
            collection = self._get_collection(table_name)

            mongo_filter = query.get("filter", {})
            projection = query.get("projection")
            limit = query.get("limit", 20)

            cursor = collection.find(mongo_filter, projection).limit(limit)

            items = list(cursor)

            return {
                "status": "success",
                "table": table_name,
                "count": len(items),
                "results": self.clean_results(items)
            }

        except Exception as e:
            logger.exception("Mongo query failed")

            return {
                "status": "error",
                "table": table_name,
                "message": str(e)
            }

    # ✅ ----------------------------
    # Agent Tools (Same Pattern ✅)
    # ✅ ----------------------------

    def get_all_products(self):

        return self.query_executor(
            {"filter": {}},
            table_name="products"
        )

    def get_shelf_layout(self, shelf_id):

        try:
            collection = self._get_collection("layout")
            return collection.find_one({"_id": str(shelf_id)})
        except Exception as e:
            logger.error("Shelf layout fetch failed")
            return None

    def get_product_and_inventory(self, upc):

        upc_str = str(upc)

        product = self._get_collection("products").find_one({
            "$or": [
                {"upc": upc_str},
                {"id": f"SKU_{upc_str}"}
            ]
        })

        inventory = self._get_collection("inventory").find_one({
            "$or": [
                {"upc": upc_str},
                {"id": f"INV_{upc_str}"}
            ]
        })

        return {
            "product": product,
            "inventory": inventory
        }

    def resolve_effective_price(self, product_data, base_price):

        collection = self._get_collection("promotion")

        promos = list(collection.find({
            "isPromotion": True,
            "$or": [
                {"Scope_Value": product_data.get("Brand")},
                {"Scope_Value": product_data.get("Category")},
                {"Scope_Value": str(product_data.get("Product_Id"))}
            ]
        }))

        if not promos:
            return {"effective_price": base_price, "promotion_name": None}

        promos.sort(key=lambda x: x.get("Priority", 999))
        best = promos[0]

        discount = best.get("Discount_Percentage", 0)
        price = round(base_price * (1 - discount / 100), 2)

        return {
            "effective_price": price,
            "promotion_name": best.get("Promotion_Name")
        }

    def get_enriched_product_info(self, upc):

        data = self.get_product_and_inventory(upc)

        if not data["product"]:
            return None

        base_price = pick_price_value(data["product"], data["inventory"])
        promo = self.resolve_effective_price(data["product"], base_price)

        return format_product_info(data=data, promo=promo)

    def get_product_by_name(self, product_name):

        collection = self._get_collection("products")

        products = list(collection.find({
            "Name": {"$regex": product_name, "$options": "i"}
        }))

        results = []

        for product in products:

            upc = str(product.get("upc", ""))

            data = self.get_product_and_inventory(upc)
            results.append(data)

        return results

    def get_enriched_product_info_by_name(self, product_name):

        data = self.get_product_by_name(product_name)

        if not data:
            return None

        item = data[0]

        base_price = pick_price_value(item["product"], item["inventory"])
        promo = self.resolve_effective_price(item["product"], base_price)

        return format_product_info(item, promo)
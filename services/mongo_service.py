import re
import time
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
        self._layout_shelf_index_cache = None
        self._layout_shelf_index_ts = 0
        self._layout_shelf_index_ttl_seconds = 300

    def _normalize_product_name(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", "", str(value or "").lower())).strip()

    def _extract_shelf_id(self, shelf_obj: dict) -> str:
        if not isinstance(shelf_obj, dict):
            return ""

        direct = shelf_obj.get("shelf_id") or shelf_obj.get("shelfId") or shelf_obj.get("id")
        if direct is not None and str(direct).strip() != "":
            return str(direct).strip()

        shelf_name = str(shelf_obj.get("shelf_name") or shelf_obj.get("name") or "").strip()
        if shelf_name:
            match = re.search(r"\d+", shelf_name)
            if match:
                return match.group(0)

        return ""

    def _build_layout_shelf_index(self):
        now = time.time()
        if (
            isinstance(self._layout_shelf_index_cache, dict)
            and (now - self._layout_shelf_index_ts) <= self._layout_shelf_index_ttl_seconds
        ):
            return self._layout_shelf_index_cache

        index = {}
        cursor = self.lay_ctr.find({}, {"_id": 0, "layout_plan": 1, "product_catalog": 1})

        for doc in cursor:
            layout_plan = doc.get("layout_plan") if isinstance(doc, dict) else None
            if not isinstance(layout_plan, list):
                continue

            catalog = doc.get("product_catalog") if isinstance(doc, dict) else None
            product_id_to_name = {}
            if isinstance(catalog, list):
                for item in catalog:
                    if not isinstance(item, dict):
                        continue
                    product_id = str(item.get("id") or "").strip()
                    product_name = str(item.get("name") or item.get("product_name") or "").strip()
                    if product_id and product_name:
                        product_id_to_name[product_id] = product_name

            for shelf in layout_plan:
                if not isinstance(shelf, dict):
                    continue

                shelf_id = self._extract_shelf_id(shelf)
                if not shelf_id:
                    continue

                rows = shelf.get("rows") if isinstance(shelf.get("rows"), list) else []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    products = row.get("products") if isinstance(row.get("products"), list) else []
                    for placement in products:
                        if not isinstance(placement, dict):
                            continue

                        product_name = str(placement.get("product_name") or placement.get("name") or "").strip()
                        if not product_name:
                            product_id = str(placement.get("product_id") or "").strip()
                            product_name = product_id_to_name.get(product_id, "")
                        if not product_name:
                            continue

                        normalized = self._normalize_product_name(product_name)
                        if not normalized:
                            continue

                        if normalized not in index:
                            index[normalized] = set()
                        index[normalized].add(shelf_id)

        normalized_index = {name: sorted(list(shelf_ids), key=lambda x: (len(str(x)), str(x))) for name, shelf_ids in index.items()}
        self._layout_shelf_index_cache = normalized_index
        self._layout_shelf_index_ts = now
        return normalized_index

    def get_shelf_ids_for_product_names(self, product_names):
        if not isinstance(product_names, list):
            return []

        index = self._build_layout_shelf_index()
        results = []
        seen = set()

        for raw_name in product_names:
            name = str(raw_name or "").strip()
            normalized = self._normalize_product_name(name)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            shelf_ids = index.get(normalized, [])
            results.append({
                "name": name,
                "normalized_name": normalized,
                "shelf_ids": shelf_ids,
                "shelf_id": shelf_ids[0] if shelf_ids else "",
            })

        return results

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

    def get_inventory_by_upcs(self, upcs: list) -> list:
        """
        Fetch inventory records for a list of UPCs (string or integer).
        Used for direct price lookup from AI search results.
        """
        if not upcs:
            return []

        or_conditions = []
        for upc in upcs:
            upc_str = self._normalize_upc(upc)
            if not upc_str:
                continue
            or_conditions.extend([{"upc": upc_str}, {"UPC": upc_str}])
            try:
                upc_int = int(upc_str)
                or_conditions.extend([{"upc": upc_int}, {"UPC": upc_int}])
            except (ValueError, TypeError):
                pass

        if not or_conditions:
            return []

        items = list(self.inv_ctr.find({"$or": or_conditions}, {"_id": 0}))
        return self.clean_product_results(items)

    def get_promotions_for_products(self, products: list) -> dict:
        """
        For a list of product dicts (with Brand, Category, Product_Id),
        look up applicable promotions and return a map:
        {
          "product_id|brand|category": {
            "promotion_name": "...",
            "discount_percentage": 10,
            "priority": 1
          }
        }
        Used to enrich AI search results with promotion and discounted price info.
        """
        if not products:
            return {}

        try:
            all_promos = list(self.promo_ctr.find({"isPromotion": True}, {"_id": 0}))
            if not all_promos:
                return {}

            promo_map = {}

            for product in products:
                if not isinstance(product, dict):
                    continue

                brand = product.get("Brand") or product.get("brand")
                category = product.get("Category") or product.get("category")
                product_id = str(product.get("Product_Id") or product.get("product_id") or "")

                # Find matching promotions for this product (by brand, category, or product_id)
                applicable = []
                for promo in all_promos:
                    if not isinstance(promo, dict):
                        continue
                    scope_value = promo.get("Scope_Value")
                    if scope_value in (brand, category, product_id):
                        applicable.append(promo)

                if applicable:
                    # Sort by Priority (lowest = highest priority)
                    applicable.sort(key=lambda x: x.get("Priority", 999))
                    best_promo = applicable[0]

                    # Use product_id as key, fallback to brand or category
                    key = product_id or brand or category or ""
                    if key:
                        promo_map[key] = {
                            "promotion_name": best_promo.get("Promotion_Name"),
                            "discount_percentage": float(best_promo.get("Discount_Percentage") or 0),
                            "priority": best_promo.get("Priority", 999),
                        }

            return promo_map

        except Exception as e:
            logger.error(f"Error fetching promotions: {e}")
            return {}


    def _enrich_products_with_inventory(self, products: list) -> list:
        """Join inventory price/stock data onto product records by UPC."""
        enriched = []
        for product in products:
            if not isinstance(product, dict):
                enriched.append(product)
                continue

            upc = self._normalize_upc(
                product.get("upc") or product.get("UPC")
            )
            inventory = None
            if upc:
                # Build query that matches both string and integer UPC values,
                # since MongoDB is type-strict and UPC may be stored as either.
                query_conditions = [
                    {"upc": upc},
                    {"UPC": upc},
                    {"id": f"INV_{upc}"},
                ]
                try:
                    upc_int = int(upc)
                    query_conditions.extend([{"upc": upc_int}, {"UPC": upc_int}])
                except (ValueError, TypeError):
                    pass
                inventory = self.inv_ctr.find_one(
                    {"$or": query_conditions},
                    {"_id": 0},
                )

            merged = dict(product)
            if isinstance(inventory, dict):
                # Merge inventory fields only when not already present on product
                for key, value in inventory.items():
                    if key not in merged or merged[key] is None:
                        merged[key] = value

                # Normalise to the lowercase field names the agent expects
                if merged.get("price") is None:
                    merged["price"] = inventory.get("Price") or inventory.get("price")
                if merged.get("us_price") is None:
                    merged["us_price"] = inventory.get("US_Price") or inventory.get("us_price")
                if merged.get("discounted_price") is None:
                    merged["discounted_price"] = (
                        inventory.get("Discounted_Price") or inventory.get("discounted_price")
                    )
                if merged.get("us_discounted_price") is None:
                    merged["us_discounted_price"] = (
                        inventory.get("US_Discounted_Price") or inventory.get("us_discounted_price")
                    )
                if merged.get("quantity") is None:
                    merged["quantity"] = inventory.get("Quantity") or inventory.get("quantity")

            enriched.append(merged)
        return enriched

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

            # Enrich product results with inventory price/stock data so the LLM
            # can answer pricing questions even when querying the products table.
            if str(table_name).lower() == "products":
                items = self._enrich_products_with_inventory(items)

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

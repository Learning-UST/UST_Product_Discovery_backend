from azure.cosmos import CosmosClient
from core.base.db_base import BaseDatabase
from utils.config import get_config_value
from utils.logger import get_logger
from core.utils import format_product_info, pick_price_value


logger = get_logger()


class CosmosService(BaseDatabase):

    def __init__(self):

        self.endpoint = get_config_value("COSMOS_ENDPOINT") or get_config_value("AZURE_COSMOS_ENDPOINT")
        self.key = get_config_value("COSMOS_KEY") or get_config_value("AZURE_COSMOS_KEY")
        self.db_name = get_config_value("COSMOS_DB_NAME") or get_config_value("AZURE_COSMOS_DB_NAME")

        self._validate_config()

        self.client = CosmosClient(self.endpoint, self.key)
        self.db = self.client.get_database_client(self.db_name)

        self.containers = {
            "products": self.db.get_container_client("products"),
            "inventory": self.db.get_container_client("inventory"),
            "promotion": self.db.get_container_client("promotion"),
            "layout": self.db.get_container_client("layout")
        }

        logger.info("✅ Cosmos DB initialized")

    # ✅ ----------------------------
    # Internal helpers
    # ✅ ----------------------------

    def _validate_config(self):
        missing = []

        if not self.endpoint:
            missing.append("COSMOS_ENDPOINT")
        if not self.key:
            missing.append("COSMOS_KEY")
        if not self.db_name:
            missing.append("COSMOS_DB_NAME")

        if missing:
            raise ValueError(f"Missing Cosmos config: {', '.join(missing)}")

    def _get_container(self, table_name: str):
        container = self.containers.get(table_name.lower())
        if not container:
            raise ValueError(f"Invalid table: {table_name}")
        return container
    
    # ✅ ----------------------------
    # Data cleaning
    # ✅ ----------------------------
    @staticmethod
    def clean_product_results(data: list):
        """
        Cleans Cosmos DB results by removing unwanted fields
        """


        fields_to_remove = {
            "model_url",
            "Height(cm)",
            "Width(cm)",
            "Depth(cm)",
            "_rid",
            "_self",
            "_etag",
            "_attachments",
            "_ts"
        }

        cleaned_results = []

        for item in data:
            cleaned_item = {
                key: value
                for key, value in item.items()
                if key not in fields_to_remove
            }
            cleaned_results.append(cleaned_item)

        return cleaned_results

    # ✅ ----------------------------
    # Base methods
    # ✅ ----------------------------

    def get_item(self, key: str, table_name: str):
        try:
            container = self._get_container(table_name)
            return container.read_item(item=key, partition_key=key)
        except Exception as e:
            logger.error(f"get_item failed: {str(e)}")
            return None

    def query_executor(self, sql_query: dict, table_name: str = "products"):

        try:
            container = self._get_container(table_name)

            query = sql_query.get("query")
            parameters = sql_query.get("parameters", [])
            partition_key = sql_query.get("partition_key")

            if not query or "SELECT" not in query.upper():
                raise ValueError("Invalid query")

            items = list(
                container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=(partition_key is None),
                    partition_key=partition_key if partition_key else None
                )
            )

            return {
                "status": "success",
                "table": table_name,
                "count": len(items),
                "results": self.clean_product_results(items[:20])
            }

        except Exception as e:
            logger.exception("Query execution failed")

            return {
                "status": "error",
                "table": table_name,
                "message": str(e)
            }

    # ✅ ----------------------------
    # Agent Tools (Domain Methods)
    # ✅ ----------------------------

    def get_all_products(self):

        query = "SELECT * FROM c"

        return self.query_executor(
            {"query": query},
            table_name="products"
        )

    def get_shelf_layout(self, shelf_id):

        try:
            container = self._get_container("layout")

            return container.read_item(
                item=str(shelf_id),
                partition_key=int(shelf_id)
            )

        except Exception as e:
            logger.error("Shelf layout fetch failed")
            return None

    def get_product_and_inventory(self, upc):

        upc_str = str(upc)

        product_query = {
            "query": """
            SELECT * FROM c 
            WHERE c.upc = @upc OR c.id = @prod_id
            """,
            "parameters": [
                {"name": "@upc", "value": upc_str},
                {"name": "@prod_id", "value": f"SKU_{upc_str}"}
            ]
        }

        inventory_query = {
            "query": """
            SELECT * FROM c 
            WHERE c.upc = @upc OR c.id = @inv_id
            """,
            "parameters": [
                {"name": "@upc", "value": upc_str},
                {"name": "@inv_id", "value": f"INV_{upc_str}"}
            ]
        }

        product_res = self.query_executor(product_query, "products")
        inv_res = self.query_executor(inventory_query, "inventory")

        return {
            "product": (product_res["results"][0] if product_res["results"] else None),
            "inventory": (inv_res["results"][0] if inv_res["results"] else None)
        }

    def resolve_effective_price(self, product_data, base_price):

        query = {
            "query": """
            SELECT * FROM c 
            WHERE c.isPromotion = true 
            AND (c.Scope_Value = @brand OR c.Scope_Value = @cat OR c.Scope_Value = @pid)
            """,
            "parameters": [
                {"name": "@brand", "value": product_data.get("Brand")},
                {"name": "@cat", "value": product_data.get("Category")},
                {"name": "@pid", "value": str(product_data.get("Product_Id"))}
            ]
        }

        result = self.query_executor(query, "promotion")
        promos = result.get("results", [])

        if not promos:
            logger.info(f"No applicable promotions found for product: {product_data.get('Name')}")
            return {"effective_price": base_price, "promotion_name": None}

        promos.sort(key=lambda x: x.get("Priority", 999))
        best = promos[0]

        discount = best.get("Discount_Percentage", 0)
        price = round(base_price * (1 - discount / 100), 2)

        logger.info(f"Base Price: {base_price}, Discount: {discount}%, Effective Price: {price}")
        logger.info(f"Applied Promotion: {best.get('Promotion_Name')})")
        return {
            "effective_price": price,
            "promotion_name": best.get("Promotion_Name")
        }

    def get_enriched_product_info(self, upc):

        data = self.get_product_and_inventory(upc)

        if not data["product"] and not data["inventory"]:
            return None

        base_price = pick_price_value(data["product"], data["inventory"])
        promo = self.resolve_effective_price(data["product"], base_price)

        return format_product_info(data=data, promo=promo)

    def get_product_by_name(self, product_name: str):
        """
        Query products by name (case-insensitive partial match)
        and fetch corresponding inventory for each product.
        
        Returns:
            list of {
                "product": {...},
                "inventory": {...}
            }
        """

        # ✅ 1. Query matching products
        product_query = """
        SELECT * FROM c
        WHERE CONTAINS(LOWER(c.Name), LOWER(@name))
        """

        product_params = [
            {"name": "@name", "value": product_name}
        ]

        product_res = self.query_executor(
            {"query": product_query, "parameters": product_params},
            table_name="products"
        )

        products = product_res.get("results", [])

        if not products:
            return []

        results = []

        # ✅ 2. Fetch inventory for each product
        for product in products:
            upc = str(product.get("upc") or product.get("UPC") or "")

            if not upc:
                # fallback if UPC missing
                results.append({
                    "product": product,
                    "inventory": None
                })
                continue

            inventory_query = """
            SELECT * FROM c 
            WHERE c.upc = @upc OR c.id = @inv_id
            """

            inventory_params = [
                {"name": "@upc", "value": upc},
                {"name": "@inv_id", "value": f"INV_{upc}"}
            ]

            inventory_res = self.query_executor(
                {"query": inventory_query, "parameters": inventory_params},
                table_name="inventory"
            )


            results.append({
                "product": product,
                "inventory": inventory_res.get("results", [None])[0]
            })

        return results


    def get_enriched_product_info_by_name(self, product_name):

        data = self.get_product_by_name(product_name)
        logger.info(f"Products found for name '{product_name}': {len(data)}")
        if not data:
            return None

        item = data[0]
        logger.info(f"Using product with UPC: {item['product'].get('upc') or item['product'].get('UPC')}")
        base_price = pick_price_value(item["product"], item["inventory"])
        promo = self.resolve_effective_price(item["product"], base_price)

        return format_product_info(item, promo)
from azure.cosmos import CosmosClient
from utils.config import get_config_value

class CosmosService:
    def __init__(self):
        endpoint = get_config_value("COSMOS_ENDPOINT") or get_config_value("AZURE_COSMOS_ENDPOINT")
        key = get_config_value("COSMOS_KEY") or get_config_value("AZURE_COSMOS_KEY")
        db_name = get_config_value("COSMOS_DB_NAME") or get_config_value("AZURE_COSMOS_DB_NAME")

        missing = []
        if not endpoint:
            missing.append("COSMOS_ENDPOINT or AZURE_COSMOS_ENDPOINT")
        if not key:
            missing.append("COSMOS_KEY or AZURE_COSMOS_KEY")
        if not db_name:
            missing.append("COSMOS_DB_NAME or AZURE_COSMOS_DB_NAME")
        if missing:
            raise ValueError(f"Missing Cosmos configuration: {', '.join(missing)}")

        self.client = CosmosClient(endpoint, key)
        self.db = self.client.get_database_client(db_name)
        self.prod_ctr = self.db.get_container_client("products")
        self.inv_ctr = self.db.get_container_client("inventory")
        self.promo_ctr = self.db.get_container_client("promotion")
        self.lay_ctr = self.db.get_container_client("layout")

    def _format_product_info(self, data):
        product = data['product']
        inventory = data['inventory']
        
        effective_price, promo_name = self.resolve_effective_price(
            product, inventory['Price']
        )
        
        return {
            "name": product["Name"],
            "brand": product["Brand"],
            "description": product["Description"],
            "ingredients": product.get("Ingredients"),
            "nutrition": product.get("Nutritional_Facts"),
            "stock_status": "In Stock" if inventory["Quantity"] > 0 else "Out of Stock",
            "quantity": inventory["Quantity"],
            "base_price": inventory["Price"],
            "final_price": effective_price,
            "applied_promotion": promo_name,
            "image_url": product["image_url"]
        }

    def get_all_products(self):
        """Fetch all product documents from the products container."""
        query = "SELECT * FROM c"
        return list(self.prod_ctr.query_items(
            query=query,
            enable_cross_partition_query=True
        ))


    def get_shelf_layout(self, shelf_id):
        """Tool for Agent: Digital Twin lookup"""
        return self.lay_ctr.read_item(item=str(shelf_id), partition_key=int(shelf_id))



    def get_product_and_inventory(self, upc):
        """Tool for Agent: Instant detail lookup (safe query-based version)"""

        upc_str = str(upc)

        # Query product
        product_query = """
        SELECT * FROM c 
        WHERE c.upc = @upc OR c.id = @prod_id
        """

        product_params = [
            {"name": "@upc", "value": upc_str},
            {"name": "@prod_id", "value": f"SKU_{upc_str}"}
        ]

        products = list(self.prod_ctr.query_items(
            query=product_query,
            parameters=product_params,
            enable_cross_partition_query=True
        ))

        # Query inventory
        inventory_query = """
        SELECT * FROM c 
        WHERE c.upc = @upc OR c.id = @inv_id
        """

        inventory_params = [
            {"name": "@upc", "value": upc_str},
            {"name": "@inv_id", "value": f"INV_{upc_str}"}
        ]

        inventory = list(self.inv_ctr.query_items(
            query=inventory_query,
            parameters=inventory_params,
            enable_cross_partition_query=True
        ))

        return {
            "product": products[0] if products else None,
            "inventory": inventory[0] if inventory else None
        }
    

    def resolve_effective_price(self, product_data, base_price):
        """Logic to find the best applicable promotion"""
        brand = product_data.get("Brand")
        category = product_data.get("Category")
        product_id = product_data.get("Product_Id")

        # Query promotions for Brand, Category, or Specific Product
        query = "SELECT * FROM c WHERE c.isPromotion = true AND (c.Scope_Value = @brand OR c.Scope_Value = @cat OR c.Scope_Value = @pid)"
        parameters = [
            {"name": "@brand", "value": brand},
            {"name": "@cat", "value": category},
            {"name": "@pid", "value": str(product_id)}
        ]
        
        promos = list(self.promo_ctr.query_items(
            query=query, parameters=parameters, enable_cross_partition_query=True
        ))

        if not promos:
            return base_price, None

        # Sort by Priority (lowest number = highest priority)
        promos.sort(key=lambda x: x.get("Priority", 999))
        best_promo = promos[0]
        discount = best_promo.get("Discount_Percentage", 0)
        
        effective_price = round(base_price * (1 - discount / 100), 2)
        return effective_price, best_promo.get("Promotion_Name")

    def get_enriched_product_info(self, upc):
        """Unified tool for the Instant-Retrieval requirement"""
        data = self.get_product_and_inventory(upc)
        return self._format_product_info(data=data)

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

        products = list(self.prod_ctr.query_items(
            query=product_query,
            parameters=product_params,
            enable_cross_partition_query=True
        ))

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

            inventory_items = list(self.inv_ctr.query_items(
                query=inventory_query,
                parameters=inventory_params,
                enable_cross_partition_query=True
            ))

            results.append({
                "product": product,
                "inventory": inventory_items[0] if inventory_items else None
            })

        return results

    def get_enriched_product_info_by_name(self, product_name):
        """
        Combined tool to search by product name and return enriched info.
        Uses get_product_by_name and then resolves price and promotion for the first match.
        """
        data = self.get_product_by_name(product_name)
        if not data:
            return None
        return self._format_product_info(data[0])
from azure.cosmos import CosmosClient
from utils.config import get_config_value


class FoodCosmosService:
    def __init__(self):
        # ✅ Read config
        endpoint = get_config_value("COSMOS_ENDPOINT") or get_config_value("AZURE_COSMOS_ENDPOINT")
        key = get_config_value("COSMOS_KEY") or get_config_value("AZURE_COSMOS_KEY")
        db_name = get_config_value("FOOD_COSMOS_DB_NAME")
        container_name = get_config_value("FOOD_COSMOS_CONTAINER_NAME")

        # ✅ Initialize client
        self.client = CosmosClient(endpoint, key)

        # ✅ Create/Get DB
        self.database = self.client.create_database_if_not_exists(id=db_name)

        # ✅ Create/Get Container
        self.container = self.database.create_container_if_not_exists(
            id=container_name,
            partition_key={"paths": ["/station"], "kind": "Hash"}
        )

    def clean_product_results(self, items):
        cleaned_results = []

        for item in items:
            cleaned_results.append({
                "id": item.get("id"),
                "recipe_number": item.get("recipe_number"),
                "recipe_name": item.get("recipe_name"),
                "short_name": item.get("short_name"),
                "station": item.get("station"),
                "portion": item.get("menu_portion_size"),
                "weight_g": item.get("menu_portion_weight_g"),
                "price": item.get("sell_price"),
                "kcal": item.get("kcal"),
                "protein_g": item.get("protein_g"),
                "fat_g": item.get("fat_g"),
                "carbs_g": item.get("carbohydrates_g"),
                "sugars_g": item.get("total_sugars_g"),
                "color": item.get("color")
            })

        return cleaned_results


    # ✅ Query Executor
    def query_executor(self, sql_query: dict):
        """
        Generic Cosmos DB Query Executor

        Args:
            sql_query: {
                "query": "SELECT * FROM c WHERE ...",
                "parameters": [],
                "partition_key": "Main Dish- Side"
            }

        Returns:
            dict: query result
        """
        try:
            # ✅ Extract query data
            query = sql_query.get("query")
            parameters = sql_query.get("parameters", [])
            partition_key = sql_query.get("partition_key", None)

            # ✅ Validation
            if not query or "SELECT" not in query.upper():
                raise ValueError("Invalid or missing query")

            # ✅ Execute query (IMPORTANT: use self.container ✅)
            items = list(
                self.container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=(partition_key is None),
                    partition_key=partition_key if partition_key else None
                )
            )

            return {
                "status": "success",
                "query": query,
                "parameters": parameters,
                "count": len(items),
                "results": self.clean_product_results(items[:5])  # ✅ limit results
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
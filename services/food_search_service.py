from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from utils.config import get_config_value

class FoodSearchService:
    def __init__(self):
        endpoint = get_config_value("FOOD_AZURE_SEARCH_ENDPOINT") or get_config_value("AZURE_SEARCH_ENDPOINT")
        api_key = get_config_value("FOOD_AZURE_SEARCH_API_KEY") or get_config_value("AZURE_SEARCH_API_KEY")
        index_name = get_config_value("FOOD_AZURE_SEARCH_INDEX") or "shopilot_food_recipes"
        self.client = SearchClient(endpoint=endpoint, index_name=index_name, credential=AzureKeyCredential(api_key))

    def search(self, query, top_k=5):
        # Hybrid search: keyword + vector (if embedding available)
        results = self.client.search(search_text=query, top=top_k)
        return [self._format_result(r) for r in results]

    def _format_result(self, r):
        return {
            "id": r.get("id"),
            "recipe_number": r.get("recipe_number"),
            "recipe_name": r.get("recipe_name"),
            "short_name": r.get("short_name"),
            "station": r.get("station"),
            "menu_portion_size": r.get("menu_portion_size"),
            "menu_portion_weight_g": r.get("menu_portion_weight_g"),
            "gtin": r.get("gtin"),
            "sell_price": r.get("sell_price"),
            "kcal_per_100g": r.get("kcal_per_100g"),
            "color": r.get("color"),
            "kcal": r.get("kcal"),
            "fat_g": r.get("fat_g"),
            "carbohydrates_g": r.get("carbohydrates_g"),
            "total_sugars_g": r.get("total_sugars_g"),
            "protein_g": r.get("protein_g"),
            "nutrition_summary": r.get("nutrition_summary"),
        }

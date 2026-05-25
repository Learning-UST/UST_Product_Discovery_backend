from opensearchpy import OpenSearch, RequestsHttpConnection
from utils.config import get_config_value


class OpenSearchService:
    def __init__(self):
        self.host = get_config_value("AWS_OPENSEARCH_HOST")
        self.index_name = get_config_value("AWS_OPENSEARCH_INDEX")
        self.username = get_config_value("AWS_OPENSEARCH_USERNAME")
        self.password = get_config_value("AWS_OPENSEARCH_PASSWORD")

        missing = []
        if not self.host:
            missing.append("AWS_OPENSEARCH_HOST")
        if not self.index_name:
            missing.append("AWS_OPENSEARCH_INDEX")
        if missing:
            raise ValueError(f"Missing OpenSearch configuration: {', '.join(missing)}")

        auth = (self.username, self.password) if self.username and self.password else None

        self.client = OpenSearch(
            hosts=[{"host": self.host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30,
        )

    def search_text(self, query, top_k=5):
        body = {
            "size": top_k,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "brand^2", "category^2", "description", "ingredients", "nutrition"],
                }
            },
        }
        response = self.client.search(index=self.index_name, body=body)
        hits = response.get("hits", {}).get("hits", [])
        return [self._format_result(hit.get("_source", {}), hit.get("_id")) for hit in hits]

    def _format_result(self, r, record_id=None):
        return {
            "id": r.get("id") or record_id,
            "product_id": r.get("product_id"),
            "name": r.get("name") or r.get("Name"),
            "brand": r.get("brand") or r.get("Brand"),
            "category": r.get("category") or r.get("Category"),
            "description": r.get("description") or r.get("Description"),
            "price": r.get("price") or r.get("Price"),
            "us_price": r.get("us_price") or r.get("US_Price"),
            "discounted_price": r.get("discounted_price"),
            "us_discounted_price": r.get("us_discounted_price"),
            "stock": r.get("stock") or r.get("Quantity"),
            "store_id": r.get("store_id"),
            "image_url": r.get("image_url"),
            "country_of_origin": r.get("country_of_origin"),
            "shelf_life": r.get("shelf_life"),
            "promotion": {
                "name": r.get("promotion_name"),
                "discount_percentage": r.get("discount_percentage"),
            }
            if r.get("promotion_name")
            else None,
            "metadata": {
                "veg": r.get("veg") or r.get("Veg"),
                "age_restricted": r.get("age_restricted"),
                "color": r.get("color"),
                "nutrition": r.get("nutrition") or r.get("Nutritional_Facts"),
                "ingredients": r.get("ingredients") or r.get("Ingredients"),
                "allergens": r.get("allergens") or r.get("Allergens"),
                "health_labels": r.get("health_labels") or r.get("Health_Labels"),
                "serving_size": r.get("serving_size"),
            },
            "upc": r.get("upc") or r.get("UPC"),
        }

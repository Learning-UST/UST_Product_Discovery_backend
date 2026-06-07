
from typing import List, Dict

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth, helpers

from utils.config import get_config_value
from utils.logger import get_logger

logger = get_logger()   

class OpenSearchService:
    def __init__(self):
        # ✅ Load config
        self.host = (
            get_config_value("AWS_OPENSEARCH_HOST")
            or get_config_value("AWS_OPENSEARCH_ENDPOINT")
            or get_config_value("OPENSEARCH_ENDPOINT")
        )
        self.host = str(self.host or "").replace("https://", "").replace("http://", "").rstrip("/")
        self.region = get_config_value("AWS_REGION") or "ap-northeast-1"
        self.index_name = get_config_value("AWS_OPENSEARCH_INDEX")

        self.access_key = get_config_value("AWS_ACCESS_KEY_ID")
        self.secret_key = get_config_value("AWS_SECRET_ACCESS_KEY")
        self.username = get_config_value("AWS_OPENSEARCH_USERNAME")
        self.password = get_config_value("AWS_OPENSEARCH_PASSWORD")

        self._validate_config()

        # ✅ Auth: prefer basic auth if provided, otherwise use SigV4
        auth = None
        if self.username and self.password:
            auth = (self.username, self.password)
        else:
            session_kwargs = {"region_name": self.region}
            if self.access_key and self.secret_key:
                session_kwargs["aws_access_key_id"] = self.access_key
                session_kwargs["aws_secret_access_key"] = self.secret_key
            session = boto3.Session(**session_kwargs)
            credentials = session.get_credentials()
            if not credentials:
                raise ValueError("Missing AWS credentials for OpenSearch SigV4 authentication")
            auth = AWSV4SignerAuth(credentials, self.region, "es")

        # ✅ OpenSearch client
        self.client = OpenSearch(
            hosts=[{"host": self.host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True,
        )

        logger.info("✅ OpenSearch client initialized")

    # ------------------------------------------------------------------
    # CONFIG VALIDATION
    # ------------------------------------------------------------------
    def _validate_config(self):
        missing = []

        if not self.host:
            missing.append("AWS_OPENSEARCH_HOST or AWS_OPENSEARCH_ENDPOINT")
        if not self.index_name:
            missing.append("AWS_OPENSEARCH_INDEX")

        if missing:
            raise ValueError(f"Missing configuration: {', '.join(missing)}")

    # ------------------------------------------------------------------
    # INDEX MANAGEMENT
    # ------------------------------------------------------------------
    def create_index(self, index_body: Dict):
        try:
            if not self.client.indices.exists(index=self.index_name):
                self.client.indices.create(index=self.index_name, body=index_body)
                logger.info(f"✅ Index '{self.index_name}' created")
            else:
                logger.info(f"ℹ️ Index '{self.index_name}' already exists")
        except Exception as e:
            logger.error(f"❌ Error creating index: {e}")
            raise

    def delete_index(self):
        try:
            if self.client.indices.exists(index=self.index_name):
                self.client.indices.delete(index=self.index_name)
                logger.info(f"✅ Index '{self.index_name}' deleted")
            else:
                logger.warning(f"⚠️ Index '{self.index_name}' not found")
        except Exception as e:
            logger.error(f"❌ Error deleting index: {e}")
            raise

    def get_indices(self) -> List[str]:
        try:
            indices = self.client.indices.get_alias(index="*")
            return list(indices.keys())
        except Exception as e:
            logger.error(f"❌ Error fetching indices: {e}")
            return []

    # ------------------------------------------------------------------
    # DATA OPERATIONS
    # ------------------------------------------------------------------
    def insert_document(self, doc_id: str, document: Dict):
        try:
            response = self.client.index(
                index=self.index_name,
                id=doc_id,
                body=document,
            )
            logger.info(f"✅ Inserted doc ID: {response['_id']}")
        except Exception as e:
            logger.error(f"❌ Insert failed: {e}")
            raise

    def bulk_insert(self, documents: List[Dict]):
        """
        ✅ Use this for production instead of single inserts
        """
        try:
            actions = [
                {
                    "_index": self.index_name,
                    "_id": doc.get("id"),
                    "_source": doc,
                }
                for doc in documents
            ]

            helpers.bulk(self.client, actions)
            logger.info(f"✅ Bulk inserted {len(documents)} documents")

        except Exception as e:
            logger.error(f"❌ Bulk insert failed: {e}")
            raise

    # ------------------------------------------------------------------
    # SEARCH
    # ------------------------------------------------------------------
    def search_text(self, query: str, top_k: int = 5):
        try:
            body = {
                "size": top_k,
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "name^3",
                            "brand^2",
                            "category^2",
                            "description",
                            "ingredients",
                            "nutrition",
                        ],
                    }
                },
            }

            response = self.client.search(index=self.index_name, body=body)
            hits = response.get("hits", {}).get("hits", [])
            return [self._format_result(hit.get("_source", {}), hit.get("_id")) for hit in hits]

        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []

    # ------------------------------------------------------------------
    # VECTOR SEARCH (KNN)
    # ------------------------------------------------------------------
    def search_vector(self, vector: List[float], top_k: int = 5):
        try:
            body = {
                "size": top_k,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": vector,
                            "k": top_k,
                        }
                    }
                },
            }

            response = self.client.search(index=self.index_name, body=body)
            hits = response.get("hits", {}).get("hits", [])
            return [self._format_result(hit.get("_source", {}), hit.get("_id")) for hit in hits]

        except Exception as e:
            logger.error(f"❌ Vector search failed: {e}")
            return []

    def _format_result(self, r, record_id=None):
        return {
            "id": r.get("id") or record_id,
            "product_id": r.get("product_id") or r.get("Product_Id"),
            "name": r.get("name") or r.get("Name"),
            "brand": r.get("brand") or r.get("Brand"),
            "category": r.get("category") or r.get("Category"),
            "description": r.get("description") or r.get("Description"),
            "price": r.get("price") or r.get("Price"),
            "us_price": r.get("us_price") or r.get("US_Price"),
            "discounted_price": r.get("discounted_price") or r.get("Discounted_Price"),
            "us_discounted_price": r.get("us_discounted_price") or r.get("US_Discounted_Price"),
            "stock": r.get("stock") or r.get("Quantity"),
            "store_id": r.get("store_id"),
            "image_url": r.get("image_url"),
            "country_of_origin": r.get("country_of_origin") or r.get("Country_Of_Origin"),
            "shelf_life": r.get("shelf_life") or r.get("Shelf_Life"),
            "promotion": {
                "name": r.get("promotion_name") or r.get("Promotion_Name"),
                "discount_percentage": r.get("discount_percentage") or r.get("Discount_Percentage"),
            }
            if (r.get("promotion_name") or r.get("Promotion_Name"))
            else None,
            "metadata": {
                "veg": r.get("veg") or r.get("Veg"),
                "age_restricted": r.get("age_restricted"),
                "color": r.get("color") or r.get("Colour"),
                "nutrition": r.get("nutrition") or r.get("Nutritional_Facts"),
                "ingredients": r.get("ingredients") or r.get("Ingredients"),
                "allergens": r.get("allergens") or r.get("Allergens"),
                "health_labels": r.get("health_labels") or r.get("Health_Labels"),
                "serving_size": r.get("serving_size") or r.get("Serving_Size"),
            },
            "upc": r.get("upc") or r.get("UPC"),
        }

    # ------------------------------------------------------------------
    # INDEX SCHEMA (FOOD / PRODUCT)
    # ------------------------------------------------------------------
    @staticmethod
    def get_index_schema():
        return {
            "settings": {
                "index": {
                    "knn": True
                }
            },
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "product_id": {"type": "keyword"},
                    "name": {"type": "text"},
                    "brand": {"type": "keyword"},
                    "category": {"type": "keyword"},
                    "description": {"type": "text"},

                    "price": {"type": "float"},
                    "discounted_price": {"type": "float"},

                    "stock": {"type": "integer"},
                    "store_id": {"type": "keyword"},

                    "image_url": {"type": "keyword"},
                    "country_of_origin": {"type": "keyword"},

                    "veg": {"type": "boolean"},
                    "age_restricted": {"type": "boolean"},

                    "ingredients": {"type": "text"},
                    "nutrition": {"type": "text"},

                    "embedding": {
                        "type": "knn_vector",
                        "dimension": 1024,
                    },
                }
            },
        }

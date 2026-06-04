
from typing import List, Dict

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth, helpers

from utils.config import get_config_value
from utils.logger import get_logger

logger = get_logger()   

class OpenSearchService:
    def __init__(self):
        # ✅ Load config
        self.host = get_config_value("AWS_OPENSEARCH_ENDPOINT")
        self.region = get_config_value("AWS_REGION") or "ap-northeast-1"
        self.index_name = get_config_value("AWS_OPENSEARCH_INDEX")

        self.access_key = get_config_value("AWS_ACCESS_KEY_ID")
        self.secret_key = get_config_value("AWS_SECRET_ACCESS_KEY")

        self._validate_config()

        # ✅ Create AWS session
        session = boto3.Session(
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
        )

        credentials = session.get_credentials()
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
            missing.append("AWS_OPENSEARCH_ENDPOINT")
        if not self.index_name:
            missing.append("AWS_OPENSEARCH_INDEX")
        if not self.access_key:
            missing.append("AWS_ACCESS_KEY_ID")
        if not self.secret_key:
            missing.append("AWS_SECRET_ACCESS_KEY")

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
            return response["hits"]["hits"]

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
            return response["hits"]["hits"]

        except Exception as e:
            logger.error(f"❌ Vector search failed: {e}")
            return []

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

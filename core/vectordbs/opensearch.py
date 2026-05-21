from core.base.vectordb_base import BaseVectorDB
from utils.config import get_config_value
from utils.logger import get_logger
from opensearchpy import OpenSearch
from core.utils import format_result
import uuid


logger = get_logger()


class OpenSearchVectorDB(BaseVectorDB):

    def __init__(self):

        self.host = get_config_value("OPENSEARCH_HOST")
        self.index_name = get_config_value("OPENSEARCH_INDEX")

        self.client = OpenSearch(
            hosts=[self.host],
            http_compress=True,
            use_ssl=True,
            verify_certs=True
        )

        logger.info("OpenSearch initialized...")

    # ✅ Create index
    def create_index(self):

        index_body = {
            "settings": {
                "index": {
                    "knn": True
                }
            },
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {"type": "text"},
                    "category": {"type": "text"},
                    "description": {"type": "text"},
                    "vector": {
                        "type": "knn_vector",
                        "dimension": 1536
                    }
                }
            }
        }

        self.client.indices.create(
            index=self.index_name,
            body=index_body,
            ignore=400
        )

        logger.info("✅ OpenSearch index created")

    # ✅ Text search
    def search_text(self, query, top_k=5):

        query_body = {
            "size": top_k,
            "query": {
                "match": {
                    "description": query
                }
            }
        }

        res = self.client.search(index=self.index_name, body=query_body)

        return [self._format(hit) for hit in res["hits"]["hits"]]

    # ✅ Vector search
    def vector_search(self, embedding, top_k=5):

        body = {
            "size": top_k,
            "query": {
                "knn": {
                    "vector": {
                        "vector": embedding,
                        "k": top_k
                    }
                }
            }
        }

        res = self.client.search(index=self.index_name, body=body)

        return [format_result(hit["_source"]) for hit in res["hits"]["hits"]]

    # ✅ Hybrid search
    def hybrid_search(self, query, embedding, top_k=5):

        body = {
            "size": top_k,
            "query": {
                "bool": {
                    "must": [
                        {"match": {"description": query}}
                    ],
                    "should": [
                        {
                            "knn": {
                                "vector": {
                                    "vector": embedding,
                                    "k": top_k
                                }
                            }
                        }
                    ]
                }
            }
        }

        res = self.client.search(index=self.index_name, body=body)

        return [format_result(hit["_source"]) for hit in res["hits"]["hits"]]

    # ✅ Insert docs
    def insert(self, docs):
        for doc in docs:
            if "id" not in doc:
                doc["id"] = str(uuid.uuid4())

            self.client.index(
                index=self.index_name,
                id=doc["id"],
                body=doc
            )

        logger.info(f"✅ Inserted {len(docs)} documents")

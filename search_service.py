from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import *
from azure.core.credentials import AzureKeyCredential
from azure.core.pipeline.transport import RequestsTransport

import json

from config import get_config_value


class AiSearch:

    def __init__(self):
        self.endpoint = get_config_value("AZURE_SEARCH_ENDPOINT")
        self.api_key = get_config_value("AZURE_SEARCH_API_KEY")
        self.index_name = get_config_value("AZURE_SEARCH_INDEX")

        self.credential = AzureKeyCredential(self.api_key)
        _transport = RequestsTransport(connection_verify=False)

        # Clients
        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=self.credential,
            transport=_transport
        )

        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=self.credential,
            transport=_transport
        )

    # ✅ Create Index
    def create_index(self):

        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),

            # Product info
            SearchableField(name="name", type=SearchFieldDataType.String),
            SearchableField(name="brand", type=SearchFieldDataType.String),
            SearchableField(name="category", type=SearchFieldDataType.String),
            SearchableField(name="description", type=SearchFieldDataType.String),

            # Pricing
            SimpleField(name="price", type=SearchFieldDataType.Double, filterable=True, sortable=True),
            SimpleField(name="discounted_price", type=SearchFieldDataType.Double, filterable=True, sortable=True),

            # Inventory
            SimpleField(name="stock", type=SearchFieldDataType.Int32, filterable=True),
            SimpleField(name="store_id", type=SearchFieldDataType.String, filterable=True),

            # Promotion
            SearchableField(name="promotion_name", type=SearchFieldDataType.String),

            # ✅ Metadata fields
            SimpleField(name="veg", type=SearchFieldDataType.Boolean, filterable=True),
            SearchableField(name="nutrition", type=SearchFieldDataType.String),

            # ✅ Vector field
            SearchField(
                name="vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=1536,
                vector_search_profile_name="vector-profile"
            )
        ]

        vector_search = VectorSearch(
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-config"
                )
            ],
            algorithms=[
                HnswAlgorithmConfiguration(name="hnsw-config")
            ]
        )

        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search
        )

        self.index_client.create_index(index)
        print("✅ Index created successfully!")

    # ✅ Keyword Search
    def search_text(self, query, top_k=5):
        results = self.search_client.search(
            search_text=query,
            top=top_k
        )
        return [self._format_result(r) for r in results]

    # ✅ Vector Search
    def vector_search(self, embedding, top_k=5):
        results = self.search_client.search(
            search_text=None,
            vectors=[{
                "value": embedding,
                "fields": "vector",
                "k": top_k
            }]
        )
        return [self._format_result(r) for r in results]

    # ✅ Hybrid Search
    def hybrid_search(self, query, embedding, top_k=5):
        results = self.search_client.search(
            search_text=query,
            vectors=[{
                "value": embedding,
                "fields": "vector",
                "k": top_k
            }],
            top=top_k
        )
        return [self._format_result(r) for r in results]

    # ✅ Filter Search
    def filtered_search(self, query, filter_expr, top_k=5):
        results = self.search_client.search(
            search_text=query,
            filter=filter_expr,
            top=top_k
        )
        return [self._format_result(r) for r in results]

    # ✅ Read JSON file (combined_output.json)
    def read_json(self, file_path="combined_output.json"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Flatten metadata fields
        formatted_data = []
        for item in data:
            formatted_data.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "brand": item.get("brand"),
                "category": item.get("category"),
                "description": item.get("description"),
                "price": item.get("price"),
                "discounted_price": item.get("discounted_price"),
                "stock": item.get("stock"),
                "store_id": item.get("store_id"),
                "promotion_name": item.get("promotion"),

                # ✅ Flatten metadata
                "veg": item.get("metadata", {}).get("veg", False),
                "nutrition": item.get("metadata", {}).get("nutrition", "")
            })

        return formatted_data

    # ✅ Insert documents into Azure AI Search
    def insert(self, docs):
        try:
            result = self.search_client.upload_documents(documents=docs)

            print(f"✅ Uploaded {len(docs)} documents successfully!")
            
            # Optional: return detailed result
            return result

        except Exception as e:
            print(f"❌ Error uploading documents: {str(e)}")
            return None

    # ✅ Result Formatter
    def _format_result(self, r):
        return {
            "id": r.get("id"),
            "name": r.get("name"),
            "brand": r.get("brand"),
            "category": r.get("category"),
            "description": r.get("description"),
            "price": r.get("price"),
            "discounted_price": r.get("discounted_price"),
            "veg": r.get("veg"),
            "nutrition": r.get("nutrition")
        }


if __name__  =="__main__":
    search=AiSearch()
    # data=search.read_json()
    # # print(data)
    # search.create_index()
    # search.insert(data)
    # result=search.search_text("Instant soup")
    # print(result)
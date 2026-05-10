from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import *
from azure.core.credentials import AzureKeyCredential

from config import get_config_value


class AiSearch:

    def __init__(self):
        self.endpoint = get_config_value("AZURE_SEARCH_ENDPOINT")
        self.api_key = get_config_value("AZURE_SEARCH_API_KEY")
        self.index_name = get_config_value("AZURE_SEARCH_INDEX")

        self.credential = AzureKeyCredential(self.api_key)

        # Clients
        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=self.credential
        )

        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=self.credential
        )

    # ✅ Create Index
    def create_index(self):

        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),

            # Product info
            SearchableField(name="product_name", type=SearchFieldDataType.String),
            SearchableField(name="category", type=SearchFieldDataType.String),
            SearchableField(name="description", type=SearchFieldDataType.String),

            # Filterable fields
            SimpleField(
                name="price",
                type=SearchFieldDataType.Double,
                filterable=True,
                sortable=True
            ),

            # Ingredients
            SearchField(
                name="ingredients",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                searchable=True
            ),

            # Planogram
            ComplexField(
                name="planogram_info",
                fields=[
                    SimpleField(name="aisle", type=SearchFieldDataType.String, filterable=True),
                    SimpleField(name="shelf", type=SearchFieldDataType.String, filterable=True),
                    SimpleField(name="position", type=SearchFieldDataType.String),
                ]
            ),

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

    # ✅ Hybrid Search (BEST for production)
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

    # ✅ Optional filter search
    def filtered_search(self, query, filter_expr, top_k=5):
        results = self.search_client.search(
            search_text=query,
            filter=filter_expr,
            top=top_k
        )

        return [self._format_result(r) for r in results]

    # ✅ Standard response formatter
    def _format_result(self, r):
        return {
            "id": r.get("id"),
            "product_name": r.get("product_name"),
            "category": r.get("category"),
            "description": r.get("description"),
            "price": r.get("price"),
            "ingredients": r.get("ingredients"),
            "planogram_info": r.get("planogram_info")
        }
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
        _transport = RequestsTransport()

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

            SimpleField(
                name="product_id",
                type=SearchFieldDataType.Int32,
                filterable=True
            ),


            # ✅ Shelf layout fields
            SimpleField(name="shelf_id", type=SearchFieldDataType.Int32, filterable=True),
            SearchableField(name="shelf_name", type=SearchFieldDataType.String),
            SimpleField(name="row_id", type=SearchFieldDataType.Int32, filterable=True),


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

            # ✅ Additional product info
            SearchableField(name="image_url", type=SearchFieldDataType.String),
            SearchableField(name="country_of_origin", type=SearchFieldDataType.String),
            SearchableField(name="shelf_life", type=SearchFieldDataType.String),

            # Promotion
            SearchableField(name="promotion_name", type=SearchFieldDataType.String),
            SimpleField(name="discount_percentage", type=SearchFieldDataType.Double, filterable=True, sortable=True),


            # ✅ Metadata (flattened)
            SimpleField(name="veg", type=SearchFieldDataType.Boolean, filterable=True),
            SimpleField(name="age_restricted", type=SearchFieldDataType.Boolean, filterable=True),
            SearchableField(name="color", type=SearchFieldDataType.String),


            # ✅ Nutrition (store as text for search)
            SearchableField(name="nutrition", type=SearchFieldDataType.String),


            # ✅ Ingredients & labels (collections)

            SimpleField(
                name="ingredients",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True
            ),
            SimpleField(
                name="allergens",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True
            ),
            SimpleField(
                name="health_labels",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True
            ),



            # ✅ Serving info
            SearchableField(name="serving_size", type=SearchFieldDataType.String),


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

    # ✅ Read JSON file (updated for new schema)
    def read_json(self, file_path="combined_output.json"):
        import json

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        formatted_data = []

        for item in data:
            metadata = item.get("metadata", {})
            promotion = item.get("promotion", {})

            formatted_data.append({
                "id": item.get("id"),
                "product_id": item.get("product_id"),

                # ✅ Product fields
                "name": item.get("name"),
                "brand": item.get("brand"),
                "category": item.get("category"),
                "description": item.get("description"),

                # ✅ Pricing
                "price": item.get("price"),
                "discounted_price": item.get("discounted_price"),

                # ✅ Inventory
                "stock": item.get("stock"),
                "store_id": item.get("store_id"),

                # ✅ Additional fields
                "image_url": item.get("image_url"),
                "country_of_origin": item.get("country_of_origin"),
                "shelf_life": item.get("shelf_life"),

                # ✅ Promotion (flattened)
                "promotion_name": promotion.get("name") if promotion else None,
                "discount_percentage": promotion.get("discount_percentage") if promotion else None,

                # ✅ Metadata (flattened)
                "veg": metadata.get("veg", False),
                "age_restricted": metadata.get("age_restricted", False),
                "color": metadata.get("color"),

                "nutrition": json.dumps(metadata.get("nutrition", {})),

                "ingredients": metadata.get("ingredients", []),
                "allergens": metadata.get("allergens", []),
                "health_labels": metadata.get("health_labels", []),

                "serving_size": metadata.get("serving_size")
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

    # ✅ Result Formatter (Updated)
    def _format_result(self, r):
        return {
            "id": r.get("id"),
            "product_id": r.get("product_id"),
            "name": r.get("name"),
            "brand": r.get("brand"),
            "category": r.get("category"),
            "description": r.get("description"),

            # Pricing
            "price": r.get("price"),
            "discounted_price": r.get("discounted_price"),

            # Inventory
            "stock": r.get("stock"),
            "store_id": r.get("store_id"),

            # Product info
            "image_url": r.get("image_url"),
            "country_of_origin": r.get("country_of_origin"),
            "shelf_life": r.get("shelf_life"),

            # Promotion
            "promotion": {
                "name": r.get("promotion_name"),
                "discount_percentage": r.get("discount_percentage")
            } if r.get("promotion_name") else None,

            # Metadata
            "metadata": {
                "veg": r.get("veg"),
                "age_restricted": r.get("age_restricted"),
                "color": r.get("color"),
                "nutrition": r.get("nutrition"),
                "ingredients": r.get("ingredients"),
                "allergens": r.get("allergens"),
                "health_labels": r.get("health_labels"),
                "serving_size": r.get("serving_size")
            }
        }

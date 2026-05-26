import argparse

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from utils.config import get_config_value


DEFAULT_VECTOR_DIMENSIONS = 1536


def _get_search_config(index_name_override=None):
    endpoint = get_config_value("FOOD_AZURE_SEARCH_ENDPOINT") or get_config_value("AZURE_SEARCH_ENDPOINT")
    api_key = get_config_value("FOOD_AZURE_SEARCH_API_KEY") or get_config_value("AZURE_SEARCH_API_KEY")
    index_name = (
        index_name_override
        or get_config_value("FOOD_AZURE_SEARCH_INDEX")
        or "shopilot_food_recipes"
    )

    missing = []
    if not endpoint:
        missing.append("FOOD_AZURE_SEARCH_ENDPOINT or AZURE_SEARCH_ENDPOINT")
    if not api_key:
        missing.append("FOOD_AZURE_SEARCH_API_KEY or AZURE_SEARCH_API_KEY")
    if not index_name:
        missing.append("FOOD_AZURE_SEARCH_INDEX")

    if missing:
        raise ValueError(f"Missing Azure Search config: {', '.join(missing)}")

    return endpoint, api_key, index_name


def _build_index(index_name: str) -> SearchIndex:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="recipe_number", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="recipe_name", type=SearchFieldDataType.String),
        SearchableField(name="short_name", type=SearchFieldDataType.String),
        SearchableField(name="station", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="menu_portion_size", type=SearchFieldDataType.String),
        SimpleField(name="menu_portion_weight_g", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SearchableField(name="gtin", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="sell_price", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SimpleField(name="kcal_per_100g", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SearchableField(name="color", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="kcal", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SimpleField(name="fat_g", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SimpleField(name="carbohydrates_g", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SimpleField(name="total_sugars_g", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SimpleField(name="protein_g", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SearchableField(name="nutrition_summary", type=SearchFieldDataType.String),
        SearchableField(name="embedding_text", type=SearchFieldDataType.String),
        SearchField(
            name="vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=DEFAULT_VECTOR_DIMENSIONS,
            vector_search_profile_name="food-vector-profile",
        ),
    ]

    vector_search = VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="food-vector-profile",
                algorithm_configuration_name="food-hnsw-config",
            )
        ],
        algorithms=[
            HnswAlgorithmConfiguration(name="food-hnsw-config")
        ],
    )

    return SearchIndex(name=index_name, fields=fields, vector_search=vector_search)


def main():
    parser = argparse.ArgumentParser(description="Create Azure AI Search index for food recipes")
    parser.add_argument("--index-name", default=None, help="Override index name")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete the index first if it exists, then create again",
    )
    args = parser.parse_args()

    endpoint, api_key, index_name = _get_search_config(index_name_override=args.index_name)

    client = SearchIndexClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(api_key),
    )

    if args.recreate:
        try:
            client.delete_index(index_name)
            print(f"Deleted index: {index_name}")
        except Exception as exc:
            print(f"Skip delete for {index_name}: {exc}")

    index = _build_index(index_name)
    client.create_index(index)
    print(f"Created index: {index_name}")


if __name__ == "__main__":
    main()

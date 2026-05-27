from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from utils.config import get_config_value

def main():
    endpoint = get_config_value("AZURE_SEARCH_ENDPOINT")
    api_key = get_config_value("AZURE_SEARCH_API_KEY")
    keep_indexes = {"shopilot_final", "shopilot_new"}

    client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
    indexes = list(client.list_indexes())

    print("Existing indexes:")
    for idx in indexes:
        print(f"- {idx.name}")

    # Filter out the ones to keep
    deletable = [idx for idx in indexes if idx.name not in keep_indexes]
    if not deletable:
        print("No deletable indexes found.")
        return

    # Sort by name (since creation date is not available via SDK)
    deletable.sort(key=lambda x: x.name)
    to_delete = deletable[0]
    print(f"Deleting index: {to_delete.name}")
    client.delete_index(to_delete.name)
    print("Deleted.")

if __name__ == "__main__":
    main()
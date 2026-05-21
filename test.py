
from tools.rag_tools import search_products
from services.cosmos_service import CosmosService
from services.openai_service import OpenAIService
from agent.llm_service import LLMService

def test_query_builder():
    openai_service = OpenAIService()
    cosmos= CosmosService() 

    message = """{
"Category": "instant noodles",
  "Calories": {
    "max": 300
  }
}"""
    result = openai_service.query_builder(message)
    if result["status"] =="success":
        table=result["table"]
        query_data = {"query": result["query"], "parameters": result["parameters"]}
        query_result = cosmos.query_executor(query_data, table)

        print(f"Generated Query:\n{result['query']}\n"
              f"With Parameters:\n{result['parameters']}\n"
              f"Query Result:\n{query_result}\n")

def test_query_exicuter():
    cosmos= CosmosService() 

    query_data = {
        "query": "SELECT * FROM c WHERE CONTAINS(c.Brand, @p1)",
        "parameters": [{"name": "@p1", "value": "Nissin"}]
    }

    result = cosmos.query_executor(query_data, "products")
    print(f"Query Executor Result:\n{result}")


def test_llm_response():
    llm = LLMService()
    system_prompt = "You are a helpful assistant."
    user_prompt = "What is the capital of France?"
    
    response = llm.generate(system_prompt, user_prompt)
    print("LLM Response:")
    print(response)


def test_search_products():
    query = "Cup Noodles Mazedar Masala"
    results = search_products(query)
    print(results)

def test_search_products_no_results():
    query = "Nonexistent Product XYZ"
    results = search_products(query)
    print(results)

def test_products_and_inventory():
    cosmos = CosmosService()
    upc = "28400078909"  # Example UPC, replace with actual UPC in your Cosmos DB
    result = cosmos.get_enriched_product_info(upc)
    print(result)

def test_resolve_effective_price():
    cosmos = CosmosService()
    upc = "28400078909"  # Example UPC, replace with actual UPC in your Cosmos DB
    data = cosmos.get_product_and_inventory(upc)
    product = data['product']
    inventory = data['inventory']

    if product and inventory:
        base_price = inventory.get("Price", 0)
        effective_price, promo_name = cosmos.resolve_effective_price(product, base_price)
        print(f"Base Price: {base_price}, Effective Price: {effective_price}, Promotion: {promo_name}")
    else:
        print("Product or inventory information is missing.")

def test_get_product_by_name():
    cosmos = CosmosService()
    product_name = "Cup Noodles Mazedar Masala"  # Example product name, replace with actual name in your Cosmos DB
    results = cosmos.get_enriched_product_info_by_name(product_name)
    print(results)

if __name__ == "__main__":
    # print("Testing search_products with valid query:")
    # test_search_products()
    
    # print("\nTesting search_products with no results:")
    # test_search_products_no_results()

    # print("\nTesting products and inventory:")
    # test_products_and_inventory()

    # print("\nTesting effective price resolution:")
    # test_resolve_effective_price()

    # print("\nTesting product lookup by name:")
    # test_get_product_by_name()

    # print("\nTesting LLM response generation:")
    # test_llm_response()

    # print("\nTesting Cosmos DB query executor:")
    # test_query_exicuter()

    print("\nTesting LLM query builder:")
    test_query_builder()
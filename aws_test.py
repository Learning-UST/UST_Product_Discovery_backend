from core.llms.bedrock import BedrockLLMService
from core.vectordbs.opensearch import OpenSearchVectorDB


def test_bedrock_inference():
    service = BedrockLLMService()
    response = service.generate(
        system_prompt="You are a helpful assistant.",
        user_prompt="What is the capital of France?")
    print("Bedrock response:", response)
    assert "Paris" in response, "Expected 'Paris' in the response"
    print("✅ Bedrock inference test passed")

def test_bedrock_embedding():
    service = BedrockLLMService()
    response = service.get_embedding(["Hello world", "Test embedding"])

    print(len(response[0]))

def test_opensearch_vector_db():
    os_service = OpenSearchVectorDB()
    bedrock_service = BedrockLLMService()

    query = "Looking for a Arun Italian Delight"
    embedding = bedrock_service.get_embedding([query])[0]
    results = os_service.vector_search(embedding)
    for res in results:
        print(res["_source"]["name"], res["_score"])

if __name__ == "__main__":
    # test_bedrock_inference()
    # test_bedrock_embedding()
    test_opensearch_vector_db()
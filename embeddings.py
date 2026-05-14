from openai import OpenAI
import httpx
from config import get_config_value

_endpoint = get_config_value("AZURE_OPENAI_ENDPOINT")
_api_key = get_config_value("AZURE_OPENAI_API_KEY")

client = OpenAI(
    base_url=f"{_endpoint}/openai/v1",
    api_key=_api_key,
    http_client=httpx.Client()
)

def get_embedding(text: str):
    response = client.embeddings.create(
        model=get_config_value("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        input=text
    )
    return response.data[0].embedding

if __name__ == "__main__":
    result=get_embedding("test")
    print(result)
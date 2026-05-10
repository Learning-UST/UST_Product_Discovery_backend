from openai import OpenAI
from config import get_config_value

client = OpenAI(
    base_url=f"{get_config_value("AZURE_OPENAI_ENDPOINT")}/openai/v1",
    api_key=get_config_value("AZURE_OPENAI_API_KEY")
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
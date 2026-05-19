# llm_service.py

from openai import OpenAI
from utils.config import get_config_value
from utils.logger import get_logger

logger = get_logger()


class LLMService:

    def __init__(self):
        self.client = OpenAI(
            base_url=f"{get_config_value('AZURE_OPENAI_ENDPOINT')}/openai/v1",
            api_key=get_config_value("AZURE_OPENAI_API_KEY")
        )
        self.deployment = get_config_value("AZURE_OPENAI_DEPLOYMENT")

    def generate(self, system_prompt: str, user_prompt: str) -> str:

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )

        return response.choices[0].message.content

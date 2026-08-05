import os
from openai import OpenAI
from .base import BaseLLM

class OpenAIService(BaseLLM):
    def __init__(self, model_name: str = "gpt-4o-mini"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY não encontrada no arquivo .env")
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name

    def invoke(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
        )
        return response.choices[0].message.content
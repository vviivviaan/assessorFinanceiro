import os
from groq import Groq
from .base import BaseLLM

class GroqService(BaseLLM):
    def __init__(self, model_name: str = "llama-3.3-70b-versatile"):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY não encontrada no arquivo .env")
        self.client = Groq(api_key=api_key)
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
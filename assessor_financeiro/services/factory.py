import os
from .base import BaseLLM
from .groq_provider import GroqService
from .openai_provider import OpenAIService

def get_llm_service() -> BaseLLM:
    provider = os.getenv("LLM_PROVIDER", "groq").lower()

    if provider == "groq":
        return GroqService()
    elif provider == "openai":
        return OpenAIService()
    else:
        raise ValueError(f"Provedor '{provider}' não é suportado.")
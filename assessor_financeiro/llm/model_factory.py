"""Fábrica de modelos de LLM.

Permite alternar entre provedores (Groq, OpenAI, Google) apenas mudando a
variável de ambiente LLM_PROVIDER, sem tocar no código dos agentes.

IMPORTANTE: os imports de cada provedor são feitos *dentro* de cada branch
(import tardio / lazy import). No código original, os três eram importados
no topo do módulo — isso significa que, se o pacote `openai` ou o pacote do
Gemini não estivesse instalado, o app quebrava ao iniciar mesmo que você só
usasse o Groq. Com o import tardio, cada provedor só precisa estar instalado
se for realmente o escolhido.
"""
from assessor_financeiro.config import (
    LLM_PROVIDER,
    GROQ_MODEL_ID,
    OPENAI_MODEL_ID,
    GOOGLE_MODEL_ID,
)


def get_llm_model(provider_override: str | None = None):
    """Retorna uma instância do modelo de IA configurado.

    Args:
        provider_override: força um provedor específico ("groq", "openai" ou
            "google"), ignorando o valor de LLM_PROVIDER no .env. Útil para
            testes ou para permitir que o usuário troque de modelo em tempo
            de execução no futuro.
    """
    provider = (provider_override or LLM_PROVIDER).lower()

    if provider == "openai":
        from agno.models.openai import OpenAIChat
        return OpenAIChat(id=OPENAI_MODEL_ID)

    if provider == "google":
        from agno.models.google import Gemini
        return Gemini(id=GOOGLE_MODEL_ID)

    # Padrão / fallback: Groq
    from agno.models.groq import Groq
    return Groq(id=GROQ_MODEL_ID)

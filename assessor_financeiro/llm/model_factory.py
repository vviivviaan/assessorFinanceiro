"""Fábrica de modelos de LLM.

Permite alternar entre provedores (Groq, OpenAI, Google, Claude) apenas mudando a
variável de ambiente LLM_PROVIDER, sem tocar no código dos agentes.

IMPORTANTE: os imports de cada provedor são feitos *dentro* de cada branch
(import tardio / lazy import). No código original, os três eram importados
no topo do módulo — isso significa que, se o pacote `openai` ou o pacote do
Gemini não estivesse instalado, o app quebrava ao iniciar mesmo que você só
usasse o Groq. Com o import tardio, cada provedor só precisa estar instalado
se for realmente o escolhido.
"""
import os

from assessor_financeiro.config import (
    API_KEY_ENV_VARS,
    USAR_CHAVES_DO_ENV,
    LLM_PROVIDER,
    GROQ_MODEL_ID,
    OPENAI_MODEL_ID,
    GOOGLE_MODEL_ID,
    ANTHROPIC_MODEL_ID,
)


class ChaveApiAusente(Exception):
    """O provedor escolhido não tem chave nem da usuária nem no .env."""


def resolver_chave(provider: str, api_keys: dict[str, str] | None = None) -> str | None:
    """Chave a usar para o provedor: a cadastrada pela usuária e, se não
    houver, a do .env (útil em desenvolvimento/Docker)."""
    if api_keys and api_keys.get(provider):
        return api_keys[provider]
    if not USAR_CHAVES_DO_ENV:
        return None
    variavel = API_KEY_ENV_VARS.get(provider)
    return os.getenv(variavel) if variavel else None


def provedor_tem_chave(provider: str, api_keys: dict[str, str] | None = None) -> bool:
    return bool(resolver_chave(provider, api_keys))


def get_llm_model(
    provider_override: str | None = None, api_keys: dict[str, str] | None = None
):
    """Retorna uma instância do modelo de IA configurado.

    Args:
        provider_override: força um provedor específico ("groq", "openai",
            "google" ou "anthropic"), ignorando o valor de LLM_PROVIDER no .env.
        api_keys: chaves da usuária logada ({"groq": "...", ...}). Têm
            prioridade sobre as do .env.

    Raises:
        ChaveApiAusente: se não houver chave para o provedor.
    """
    provider = (provider_override or LLM_PROVIDER).lower()
    if provider not in API_KEY_ENV_VARS:
        provider = "groq"  # padrão / fallback

    chave = resolver_chave(provider, api_keys)
    if not chave:
        raise ChaveApiAusente(provider)

    if provider == "openai":
        from agno.models.openai import OpenAIChat
        return OpenAIChat(id=OPENAI_MODEL_ID, api_key=chave)

    if provider == "google":
        from agno.models.google import Gemini
        return Gemini(id=GOOGLE_MODEL_ID, api_key=chave)

    if provider == "anthropic":
        from agno.models.anthropic import Claude
        return Claude(id=ANTHROPIC_MODEL_ID, api_key=chave)

    from agno.models.groq import Groq
    return Groq(id=GROQ_MODEL_ID, api_key=chave)

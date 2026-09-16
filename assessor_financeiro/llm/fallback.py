"""Tolerância a falhas: alterna para um provedor secundário quando o principal falha.

O AGNO não propaga a maioria dos erros de provedor (rate limit, chave
inválida, instabilidade) como exceção Python — ele captura internamente e
devolve um `RunResponse` com `status == RunStatus.error` e o texto do erro em
`.content`. Por isso a detecção de falha aqui é baseada no `status` da
resposta, e não só em try/except (que continua cobrindo o caso mais raro de
um erro de rede/timeout que escape do tratamento interno do AGNO).
"""
from typing import Callable

from agno.agent import Agent
from agno.run.base import RunStatus

# Provedor secundário a tentar quando o principal falhar. Mantido simples (1
# alternativa por provedor) porque só temos 3 provedores suportados; se um
# dia isso crescer, vira uma lista de fallback em cadeia.
PROVEDOR_SECUNDARIO = {
    "groq": "openai",
    "openai": "groq",
    "google": "groq",
}


def run_with_fallback(
    agent_factory: Callable[[str], Agent],
    provider: str,
    message: str,
) -> tuple[object, str]:
    """Roda `agent_factory(provider).run(message)` com fallback automático.

    Se a chamada falhar (exceção, ou `RunResponse.status == RunStatus.error`),
    tenta uma vez com o provedor secundário de `PROVEDOR_SECUNDARIO` antes de
    desistir.

    Args:
        agent_factory: função que recebe o nome do provedor e devolve um
            `Agent` pronto (ex.: `get_data_extractor_agent`).
        provider: provedor principal configurado para este agente.
        message: mensagem/texto a enviar ao agente.

    Returns:
        Tupla `(response, provedor_que_respondeu)`. `response` pode ainda
        estar em estado de erro se até o fallback falhar — quem chama
        continua responsável por checar isso (ex.: via telemetria).
    """
    response = _run_or_none(agent_factory, provider, message)

    if response is not None and response.status != RunStatus.error:
        return response, provider

    provedor_secundario = PROVEDOR_SECUNDARIO.get(provider)
    if provedor_secundario is None or provedor_secundario == provider:
        return response, provider

    print(f"[fallback] provedor '{provider}' falhou, tentando '{provedor_secundario}'...")
    response_fallback = _run_or_none(agent_factory, provedor_secundario, message)
    if response_fallback is not None:
        return response_fallback, provedor_secundario

    # Fallback também falhou (ex.: exceção de rede) — devolve o que tiver do
    # provedor principal para o chamador decidir o que fazer.
    return response, provider


def _run_or_none(agent_factory: Callable[[str], Agent], provider: str, message: str):
    try:
        return agent_factory(provider).run(message)
    except Exception:
        return None

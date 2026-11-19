"""Tolerância a falhas: alterna para outro provedor quando o principal falha.

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

from assessor_financeiro.config import API_KEY_ENV_VARS
from assessor_financeiro.llm.model_factory import provedor_tem_chave

# Provedor secundário preferido quando o principal falhar.
PROVEDOR_SECUNDARIO = {
    "groq": "openai",
    "openai": "groq",
    "google": "groq",
    "anthropic": "groq",
}


def ordem_de_provedores(provider: str, api_keys: dict[str, str] | None) -> list[str]:
    """Provedores a tentar, em ordem, considerando SÓ os que têm chave.

    Começa pelo preferido, depois o secundário dele e, por fim, qualquer outro
    provedor com chave. É isso que permite a alguém que cadastrou só a chave
    do Google (ou só a do Claude) usar o app inteiro: sem essa lista, o
    extrator tentaria Groq e OpenAI, não acharia chave e desistiria.
    """
    candidatos = [provider, PROVEDOR_SECUNDARIO.get(provider), *API_KEY_ENV_VARS]
    ordem: list[str] = []
    for candidato in candidatos:
        if candidato and candidato not in ordem and provedor_tem_chave(candidato, api_keys):
            ordem.append(candidato)
    return ordem


def run_with_fallback(
    agent_factory: Callable[[str], Agent],
    provider: str,
    message: str,
    api_keys: dict[str, str] | None = None,
) -> tuple[object, str]:
    """Roda `agent_factory(provider).run(message)` com fallback automático.

    Sem `api_keys` (comportamento original): tenta o provedor principal e, se
    falhar (exceção, ou `RunResponse.status == RunStatus.error`), uma vez o
    secundário de `PROVEDOR_SECUNDARIO`.

    Com `api_keys` (as chaves da usuária logada): tenta, na ordem de
    `ordem_de_provedores`, todos os provedores para os quais existe chave.

    Args:
        agent_factory: função que recebe o nome do provedor e devolve um
            `Agent` pronto (ex.: `get_data_extractor_agent`).
        provider: provedor principal configurado para este agente.
        message: mensagem/texto a enviar ao agente.
        api_keys: chaves da usuária ({"groq": "...", ...}); ver acima.

    Returns:
        Tupla `(response, provedor_que_respondeu)`. `response` é None se
        nenhum provedor respondeu, e pode estar em estado de erro se todos
        falharam — quem chama continua responsável por checar isso.
    """
    if api_keys is None:
        secundario = PROVEDOR_SECUNDARIO.get(provider)
        tentativas = [provider] + ([secundario] if secundario and secundario != provider else [])
    else:
        tentativas = ordem_de_provedores(provider, api_keys)

    ultima_resposta, ultimo_provedor = None, provider
    for indice, candidato in enumerate(tentativas):
        if indice > 0:
            print(f"[fallback] provedor '{tentativas[indice - 1]}' falhou, tentando '{candidato}'...")
        response = _run_or_none(agent_factory, candidato, message)
        if response is not None and response.status != RunStatus.error:
            return response, candidato
        if response is not None:
            # Guarda o erro mais recente que veio com conteúdo, pra telemetria.
            ultima_resposta, ultimo_provedor = response, candidato
    return ultima_resposta, ultimo_provedor


def _run_or_none(agent_factory: Callable[[str], Agent], provider: str, message: str):
    try:
        return agent_factory(provider).run(message)
    except Exception:
        return None

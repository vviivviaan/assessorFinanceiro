"""Telemetria comparativa das chamadas de LLM.

Cada chamada de agente (extrator ou conselheiro) é registrada como uma linha
JSON estruturada em `logs/llm_calls.jsonl`, com provedor, modelo, tokens,
latência e custo estimado. O AGNO já expõe essas métricas em
`response.metrics` — este módulo só formata e persiste isso de um jeito fácil
de agregar depois (ex.: lendo o arquivo com `pandas.read_json(..., lines=True)`)
para relatórios comparativos de custo por usuário, latência média por
provedor, e taxa de sucesso da extração.
"""
import json
import logging
from pathlib import Path
from typing import Any

from agno.run.base import RunStatus

from assessor_financeiro.config import DEFAULT_SESSION_ID

_LOG_PATH = Path("logs") / "llm_calls.jsonl"
_LOG_PATH.parent.mkdir(exist_ok=True)

_logger = logging.getLogger("assessor_financeiro.telemetry")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    _handler = logging.FileHandler(_LOG_PATH, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = False  # não duplica essas linhas no log geral do Reflex

# Preço aproximado em USD por 1 milhão de tokens (entrada, saída) de cada
# modelo suportado. São valores de referência para comparação relativa entre
# provedores — ajuste conforme a tabela de preços vigente de cada um.
PRECO_USD_POR_MILHAO_TOKENS: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-120b": (0.15, 0.75),
    "gpt-4o-mini": (0.15, 0.60),
    "gemini-1.5-pro": (1.25, 5.00),
}


def _estimar_custo_usd(model_id: str | None, input_tokens: int | None, output_tokens: int | None) -> float | None:
    if model_id is None or input_tokens is None or output_tokens is None:
        return None
    precos = PRECO_USD_POR_MILHAO_TOKENS.get(model_id)
    if precos is None:
        return None
    preco_input, preco_output = precos
    custo = (input_tokens / 1_000_000) * preco_input + (output_tokens / 1_000_000) * preco_output
    return round(custo, 8)


def log_llm_call(
    agent_name: str,
    session_id: str = DEFAULT_SESSION_ID,
    *,
    response: Any = None,
    provider_fallback: str | None = None,
    success: bool | None = None,
    error: str | None = None,
) -> None:
    """Registra uma linha de telemetria estruturada para uma chamada de agente.

    Args:
        agent_name: qual agente rodou ("extractor" ou "advisor").
        session_id: sessão/usuário dono da chamada (permite relatório por usuário).
        response: o `RunResponse` do AGNO (usado para extrair provedor real,
            modelo, tokens e latência — inclusive quando a chamada falhou, já
            que o AGNO não propaga a maioria dos erros de API como exceção
            Python: ele captura internamente e devolve um `RunResponse` com
            `status == RunStatus.error`).
        provider_fallback: provedor configurado, usado só quando `response` é
            None (a chamada falhou antes mesmo de o AGNO devolver uma resposta).
        success: se a chamada terminou com um resultado utilizável. Quando
            omitido, é derivado de `response.status` automaticamente. Passe
            explicitamente para aplicar um critério mais estrito (ex.: o
            extrator considera falha também um schema de saída inválido).
            Serve como proxy de "taxa de acerto" — não há como validar a
            categorização em si sem rótulo humano.
        error: mensagem de erro, se houver.
    """
    if success is None:
        success = response is not None and getattr(response, "status", None) != RunStatus.error
        if error is None and not success:
            error = getattr(response, "content", None) if response is not None else "sem resposta"

    metrics = getattr(response, "metrics", None)
    model_id = getattr(response, "model", None)
    provider = getattr(response, "model_provider", None) or provider_fallback
    input_tokens = getattr(metrics, "input_tokens", None)
    output_tokens = getattr(metrics, "output_tokens", None)
    duration = getattr(metrics, "duration", None)

    evento = {
        "session_id": session_id,
        "agent": agent_name,
        "provider": provider,
        "model": model_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_seconds": round(duration, 4) if duration is not None else None,
        "estimated_cost_usd": _estimar_custo_usd(model_id, input_tokens, output_tokens),
        "success": success,
        "error": error,
    }
    _logger.info(json.dumps(evento, ensure_ascii=False))

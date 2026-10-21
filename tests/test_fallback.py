"""Testes do fallback entre provedores de LLM (llm/fallback.py), sem chamar nenhum LLM."""
from types import SimpleNamespace

from agno.run.base import RunStatus

from assessor_financeiro.llm.fallback import PROVEDOR_SECUNDARIO, run_with_fallback


def resposta(status=RunStatus.completed, content="ok"):
    return SimpleNamespace(status=status, content=content)


class AgenteFalso:
    """Agente que devolve uma resposta pronta ou levanta uma exceção."""

    def __init__(self, resultado):
        self._resultado = resultado

    def run(self, mensagem):
        if isinstance(self._resultado, Exception):
            raise self._resultado
        return self._resultado


def fabrica(resultados_por_provedor: dict):
    """Cria uma agent_factory que registra quais provedores foram pedidos."""
    chamados: list[str] = []

    def agent_factory(provedor: str):
        chamados.append(provedor)
        return AgenteFalso(resultados_por_provedor[provedor])

    agent_factory.chamados = chamados
    return agent_factory


def test_provedor_principal_funcionando_nao_aciona_o_fallback():
    principal = resposta(content="do groq")
    factory = fabrica({"groq": principal})

    resultado, provedor = run_with_fallback(factory, "groq", "oi")

    assert resultado is principal
    assert provedor == "groq"
    assert factory.chamados == ["groq"]


def test_erro_de_status_aciona_o_provedor_secundario():
    secundaria = resposta(content="do openai")
    factory = fabrica({"groq": resposta(status=RunStatus.error, content="rate limit"), "openai": secundaria})

    resultado, provedor = run_with_fallback(factory, "groq", "oi")

    assert resultado is secundaria
    assert provedor == "openai"
    assert factory.chamados == ["groq", "openai"]


def test_excecao_no_principal_aciona_o_provedor_secundario():
    secundaria = resposta(content="do groq")
    factory = fabrica({"openai": RuntimeError("timeout"), "groq": secundaria})

    resultado, provedor = run_with_fallback(factory, "openai", "oi")

    assert resultado is secundaria
    assert provedor == "groq"


def test_principal_e_secundario_com_excecao_devolve_none():
    factory = fabrica({"groq": RuntimeError("falhou"), "openai": RuntimeError("falhou também")})

    resultado, provedor = run_with_fallback(factory, "groq", "oi")

    assert resultado is None
    assert provedor == "groq"


def test_secundario_tambem_com_erro_de_status_devolve_essa_resposta_de_erro():
    # O chamador é quem decide o que fazer com uma resposta em estado de erro.
    erro_secundario = resposta(status=RunStatus.error, content="sem crédito")
    factory = fabrica({"groq": resposta(status=RunStatus.error), "openai": erro_secundario})

    resultado, provedor = run_with_fallback(factory, "groq", "oi")

    assert resultado is erro_secundario
    assert provedor == "openai"


def test_provedor_sem_secundario_devolve_a_resposta_de_erro_do_principal():
    erro = resposta(status=RunStatus.error, content="falhou")
    factory = fabrica({"desconhecido": erro})

    resultado, provedor = run_with_fallback(factory, "desconhecido", "oi")

    assert resultado is erro
    assert provedor == "desconhecido"
    assert factory.chamados == ["desconhecido"]


def test_google_cai_para_groq():
    secundaria = resposta(content="do groq")
    factory = fabrica({"google": resposta(status=RunStatus.error), "groq": secundaria})

    _, provedor = run_with_fallback(factory, "google", "oi")

    assert provedor == "groq"


def test_nenhum_provedor_e_secundario_de_si_mesmo():
    for principal, secundario in PROVEDOR_SECUNDARIO.items():
        assert principal != secundario

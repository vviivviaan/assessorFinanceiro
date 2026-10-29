"""Testes da escolha de chave de API em llm/model_factory.py (sem chamar nenhum LLM)."""
import pytest

from assessor_financeiro.llm.model_factory import (
    ChaveApiAusente,
    get_llm_model,
    provedor_tem_chave,
    resolver_chave,
)


@pytest.fixture
def sem_chaves_no_env(monkeypatch):
    for variavel in ("GROQ_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(variavel, raising=False)


def test_chave_do_usuario_tem_prioridade_sobre_a_do_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "do-env")
    assert resolver_chave("groq", {"groq": "do-usuario"}) == "do-usuario"


def test_sem_chave_do_usuario_cai_no_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "do-env")
    assert resolver_chave("groq", {}) == "do-env"
    assert resolver_chave("groq", None) == "do-env"


def test_sem_nenhuma_chave(sem_chaves_no_env):
    assert resolver_chave("openai", {"groq": "x"}) is None
    assert not provedor_tem_chave("openai", {"groq": "x"})


def test_sem_chave_levanta_erro_claro(sem_chaves_no_env):
    with pytest.raises(ChaveApiAusente):
        get_llm_model("groq", api_keys={})


def test_modelo_usa_a_chave_do_usuario(sem_chaves_no_env):
    modelo = get_llm_model("groq", api_keys={"groq": "gsk_do_usuario"})
    assert modelo.api_key == "gsk_do_usuario"


def test_cada_provedor_pega_a_propria_chave(sem_chaves_no_env):
    chaves = {"groq": "chave-groq", "openai": "chave-openai"}
    assert get_llm_model("groq", api_keys=chaves).api_key == "chave-groq"
    assert get_llm_model("openai", api_keys=chaves).api_key == "chave-openai"


def test_em_producao_nao_usa_a_chave_do_env(monkeypatch):
    from assessor_financeiro.llm import model_factory

    monkeypatch.setenv("GROQ_API_KEY", "chave-do-dono-do-servidor")
    monkeypatch.setattr(model_factory, "USAR_CHAVES_DO_ENV", False)
    assert model_factory.resolver_chave("groq", {}) is None
    assert model_factory.resolver_chave("groq", {"groq": "do-usuario"}) == "do-usuario"
    with pytest.raises(model_factory.ChaveApiAusente):
        model_factory.get_llm_model("groq", api_keys={})

"""Configuração compartilhada dos testes.

`assessor_financeiro/config.py` valida as chaves de API no momento do import
e levanta erro se faltar alguma. Para os testes unitários (que nunca chamam
um LLM de verdade) isso seria um obstáculo, então definimos chaves falsas
ANTES de qualquer import do pacote.

Os testes marcados com `@pytest.mark.llm` chamam o LLM de verdade: eles só
rodam com `RUN_LLM_TESTS=1` e, nesse caso, usam as chaves reais do `.env`
(por isso as chaves falsas não são definidas nesse modo).
"""
import os

import pytest

RODANDO_TESTES_LLM = os.getenv("RUN_LLM_TESTS") == "1"

if not RODANDO_TESTES_LLM:
    for variavel in ("GROQ_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        os.environ.setdefault(variavel, "chave-falsa-para-testes")


def pytest_collection_modifyitems(config, items):
    if RODANDO_TESTES_LLM:
        return
    pular = pytest.mark.skip(reason="teste de LLM real: rode com RUN_LLM_TESTS=1")
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(pular)


@pytest.fixture
def banco(monkeypatch, tmp_path):
    """SQLite em memória no lugar do banco do Reflex + chave mestra de teste isolada."""
    from contextlib import contextmanager

    from cryptography.fernet import Fernet
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine

    from assessor_financeiro.core import security
    from assessor_financeiro.core import transaction_repository as repo

    monkeypatch.setenv("VIVIA_SECRET_KEY", Fernet.generate_key().decode())
    security.limpar_cache_chave_mestra()

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    @contextmanager
    def sessao():
        with Session(engine) as db:
            yield db

    monkeypatch.setattr(repo.rx, "session", sessao)
    yield engine
    security.limpar_cache_chave_mestra()


@pytest.fixture(autouse=True)
def _zerar_limite_de_login():
    """Cada teste começa sem tentativas de login registradas."""
    from assessor_financeiro.core import auth_service

    auth_service._limpar_falhas()
    yield

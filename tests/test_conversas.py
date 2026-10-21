"""Testes das conversas do chat (core/transaction_repository.py), com um SQLite em memória."""
from contextlib import contextmanager

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from assessor_financeiro.core import transaction_repository as repo
from assessor_financeiro.models.db_models import Transaction


@pytest.fixture(autouse=True)
def banco_em_memoria(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    @contextmanager
    def sessao():
        with Session(engine) as db:
            yield db

    monkeypatch.setattr(repo.rx, "session", sessao)
    return engine


def test_perfil_novo_ganha_a_conversa_inicial():
    conversas = repo.list_conversas("p1")
    assert [(c.conversa_id, c.titulo) for c in conversas] == [("", repo.TITULO_CONVERSA_INICIAL)]


def test_listar_duas_vezes_nao_duplica_a_inicial():
    repo.list_conversas("p1")
    assert len(repo.list_conversas("p1")) == 1


def test_historico_antigo_fica_na_conversa_inicial():
    repo.add_chat_message("user", "antiga", session_id="p1")  # sem conversa_id, como antes
    assert [m.content for m in repo.get_chat_history("p1", "")] == ["antiga"]


def test_mensagens_ficam_isoladas_por_conversa():
    repo.create_conversa("p1", "abc")
    repo.add_chat_message("user", "na inicial", session_id="p1", conversa_id="")
    repo.add_chat_message("user", "na nova", session_id="p1", conversa_id="abc")
    assert [m.content for m in repo.get_chat_history("p1", "")] == ["na inicial"]
    assert [m.content for m in repo.get_chat_history("p1", "abc")] == ["na nova"]


def test_mensagens_ficam_na_ordem_de_envio():
    for texto in ["1", "2", "3"]:
        repo.add_chat_message("user", texto, session_id="p1", conversa_id="abc")
    assert [m.content for m in repo.get_chat_history("p1", "abc")] == ["1", "2", "3"]


def test_conversas_de_perfis_diferentes_nao_se_misturam():
    repo.create_conversa("p1", "abc")
    repo.add_chat_message("user", "do p1", session_id="p1", conversa_id="abc")
    assert repo.get_chat_history("p2", "abc") == []
    assert [c.conversa_id for c in repo.list_conversas("p2")] == [""]


def test_conversa_mais_recente_vem_primeiro():
    repo.list_conversas("p1")
    repo.create_conversa("p1", "nova")
    assert [c.conversa_id for c in repo.list_conversas("p1")] == ["nova", ""]


def test_renomear_conversa():
    repo.create_conversa("p1", "abc")
    repo.rename_conversa("p1", "abc", "Viagem de julho")
    assert repo.list_conversas("p1")[0].titulo == "Viagem de julho"


def test_excluir_apaga_mensagens_mas_preserva_transacoes_e_outras_conversas():
    repo.create_conversa("p1", "abc")
    repo.add_chat_message("user", "vai sumir", session_id="p1", conversa_id="abc")
    repo.add_chat_message("user", "fica", session_id="p1", conversa_id="")
    repo.add_transactions([{"category": "Padaria", "amount": 20.0, "type": "Debito"}], session_id="p1")

    repo.delete_conversa("p1", "abc")

    assert repo.get_chat_history("p1", "abc") == []
    assert [m.content for m in repo.get_chat_history("p1", "")] == ["fica"]
    assert [c.conversa_id for c in repo.list_conversas("p1")] == [""]
    assert len(repo.get_transactions("p1")) == 1


def test_excluir_nao_mexe_em_outro_perfil_com_o_mesmo_conversa_id():
    repo.create_conversa("p1", "abc")
    repo.create_conversa("p2", "abc")
    repo.add_chat_message("user", "do p2", session_id="p2", conversa_id="abc")
    repo.delete_conversa("p1", "abc")
    assert [m.content for m in repo.get_chat_history("p2", "abc")] == ["do p2"]


def test_zerar_dados_apaga_conversas_mensagens_e_transacoes_do_perfil():
    repo.create_conversa("p1", "abc")
    repo.add_chat_message("user", "x", session_id="p1", conversa_id="abc")
    repo.add_transactions([{"category": "A", "amount": 1.0, "type": "Debito"}], session_id="p1")
    repo.add_chat_message("user", "outro perfil", session_id="p2")

    repo.clear_session_data("p1")

    assert repo.get_chat_history("p1", "abc") == []
    assert repo.get_transactions("p1") == []
    assert [c.conversa_id for c in repo.list_conversas("p1")] == [""]  # recria a inicial
    assert len(repo.get_chat_history("p2", "")) == 1

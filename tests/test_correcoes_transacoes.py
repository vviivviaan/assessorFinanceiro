"""Correção de lançamentos pelo chat: o extrator pode apagar transações por id.

Testa a parte que não depende do LLM: o repositório só apaga ids do perfil
ativo, e o schema aceita respostas sem `remover_ids` (compatível com o antigo).
"""
import pytest

from assessor_financeiro.agents.schemas import ListaGastos
from assessor_financeiro.core import transaction_repository as repo

pytestmark = pytest.mark.usefixtures("banco")


def _ids(session_id):
    return {t.category: t.id for t in repo.get_transactions(session_id)}


def test_apaga_so_os_ids_pedidos():
    repo.add_transactions(
        [
            {"category": "Salário", "amount": 2000.0, "type": "Credito"},
            {"category": "Teste", "amount": 10000.0, "type": "Credito"},
        ],
        session_id="usuario_1",
    )
    apagadas = repo.delete_transactions([_ids("usuario_1")["Teste"]], session_id="usuario_1")
    assert [(t.category, t.amount) for t in apagadas] == [("Teste", 10000.0)]
    assert list(_ids("usuario_1")) == ["Salário"]


def test_nao_apaga_transacao_de_outro_perfil():
    repo.add_transactions([{"category": "Dela", "amount": 50.0, "type": "Debito"}], session_id="usuario_2")
    id_outro = _ids("usuario_2")["Dela"]
    assert repo.delete_transactions([id_outro], session_id="usuario_1") == []
    assert "Dela" in _ids("usuario_2")


def test_lista_vazia_nao_faz_nada():
    assert repo.delete_transactions([], session_id="usuario_1") == []


def test_schema_aceita_resposta_sem_remover_ids():
    lista = ListaGastos.model_validate({"gastos": []})
    assert lista.remover_ids == []

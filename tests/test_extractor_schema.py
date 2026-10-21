"""Testes do contrato do agente extrator (agents/schemas.py + conversão para o banco).

O LLM em si não é testado aqui (veja test_extractor_llm.py). O que testamos é
o que o sistema faz com a saída estruturada: o schema precisa rejeitar lixo, e
a conversão para o banco não pode duplicar nem inverter valores.
"""
import pytest
from pydantic import ValidationError

from assessor_financeiro.agents.schemas import ItemGasto, ListaGastos
from assessor_financeiro.state import AdvisorState


class TestSchema:
    def test_aceita_varios_gastos_na_mesma_resposta(self):
        lista = ListaGastos(
            gastos=[
                {"category": "Supermercado", "amount": 50, "type": "Debito"},
                {"category": "Manutenção/Veículo", "amount": 120, "type": "Debito"},
            ]
        )
        assert len(lista.gastos) == 2

    def test_lista_vazia_e_valida(self):
        # Mensagem sem transação ("Quais as dicas para economizar?").
        assert ListaGastos(gastos=[]).gastos == []

    def test_valor_numerico_em_texto_e_convertido(self):
        assert ItemGasto(category="Padaria", amount="40", type="Debito").amount == 40.0

    def test_valor_por_extenso_nao_passa_no_schema(self):
        # Converter "quarenta e cinco" em 45 é trabalho do LLM, não do schema.
        # Se ele devolver o texto por extenso, o schema precisa barrar.
        with pytest.raises(ValidationError):
            ItemGasto(category="Padaria", amount="quarenta e cinco", type="Debito")

    @pytest.mark.parametrize("tipo", ["Débito", "Crédito", "gasto", "receita", "", "debito"])
    def test_tipo_fora_de_debito_ou_credito_e_rejeitado(self, tipo):
        with pytest.raises(ValidationError):
            ItemGasto(category="Padaria", amount=10, type=tipo)

    def test_categoria_fora_da_lista_conhecida_e_aceita(self):
        item = ItemGasto(category="Mensalidade da Academia", amount=120, type="Debito")
        assert item.category == "Mensalidade da Academia"


class TestGastosParaTransacoes:
    def test_converte_para_o_formato_do_banco(self):
        itens = [ItemGasto(category="Padaria", amount=20, type="Debito")]
        assert AdvisorState._gastos_para_transacoes(itens) == [
            {"category": "Padaria", "amount": 20.0, "type": "Debito"}
        ]

    def test_valor_negativo_vira_modulo(self):
        itens = [ItemGasto(category="Padaria", amount=-20, type="Debito")]
        assert AdvisorState._gastos_para_transacoes(itens)[0]["amount"] == 20.0

    def test_varios_gastos_mantem_um_registro_por_gasto(self):
        itens = [
            ItemGasto(category="Supermercado", amount=50, type="Debito"),
            ItemGasto(category="Manutenção/Veículo", amount=120, type="Debito"),
            ItemGasto(category="Salário", amount=2000, type="Credito"),
        ]
        resultado = AdvisorState._gastos_para_transacoes(itens)
        assert [r["category"] for r in resultado] == ["Supermercado", "Manutenção/Veículo", "Salário"]
        assert [r["type"] for r in resultado] == ["Debito", "Debito", "Credito"]

    def test_lista_vazia_nao_gera_registros(self):
        assert AdvisorState._gastos_para_transacoes([]) == []

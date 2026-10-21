"""Testes do cálculo de saldo e agregação por categoria (core/transaction_service.py).

É a parte determinística do sistema: o saldo nunca depende do LLM.
"""
import pytest

from assessor_financeiro.config import PALETA_FINANCEIRA
from assessor_financeiro.core.transaction_service import (
    formatar_reais,
    summarize_transactions,
)
from assessor_financeiro.models.db_models import Transaction


def tx(categoria: str, valor: float, tipo: str) -> Transaction:
    return Transaction(category=categoria, amount=valor, type=tipo)


class TestFormatarReais:
    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [
            (0, "R$ 0,00"),
            (40, "R$ 40,00"),
            (1234.5, "R$ 1.234,50"),
            (1000000, "R$ 1.000.000,00"),
            (0.5, "R$ 0,50"),
            (-40, "R$ -40,00"),
        ],
    )
    def test_formata_no_padrao_brasileiro(self, valor, esperado):
        assert formatar_reais(valor) == esperado


class TestSaldo:
    def test_lista_vazia_zera_tudo(self):
        resumo = summarize_transactions([])
        assert resumo.total_receitas == 0
        assert resumo.total_gastos == 0
        assert resumo.saldo_atual == 0
        assert resumo.category_totals == {}
        assert resumo.chart_data == []

    def test_saldo_e_creditos_menos_debitos(self):
        resumo = summarize_transactions(
            [tx("Salário", 2000, "Credito"), tx("Mercado", 500, "Debito")]
        )
        assert resumo.total_receitas == 2000
        assert resumo.total_gastos == 500
        assert resumo.saldo_atual == 1500

    def test_saldo_pode_ficar_negativo(self):
        resumo = summarize_transactions([tx("Borracharia", 40, "Debito")])
        assert resumo.saldo_atual == -40

    def test_valores_negativos_salvos_por_engano_sao_tratados_em_modulo(self):
        # O extrator já devolve valor absoluto, mas o CSV traz débitos como
        # negativos (ex.: -43.13). O sinal não pode inverter a conta.
        resumo = summarize_transactions(
            [tx("Netflix", -43.13, "Debito"), tx("Salário", 6500, "Credito")]
        )
        assert resumo.total_gastos == pytest.approx(43.13)
        assert resumo.saldo_atual == pytest.approx(6500 - 43.13)

    @pytest.mark.parametrize("tipo", ["Credito", "credito", "CREDITO", "Crédito", "  crédito  "])
    def test_aceita_variacoes_de_credito(self, tipo):
        resumo = summarize_transactions([tx("Salário", 100, tipo)])
        assert resumo.total_receitas == 100

    @pytest.mark.parametrize("tipo", ["Debito", "debito", "DEBITO", "Débito", "  débito  "])
    def test_aceita_variacoes_de_debito(self, tipo):
        resumo = summarize_transactions([tx("Mercado", 100, tipo)])
        assert resumo.total_gastos == 100

    def test_tipo_desconhecido_e_ignorado_nos_totais(self):
        # Comportamento atual: uma transação cujo tipo não é crédito nem
        # débito não entra em nenhuma conta (some silenciosamente). Isso é o
        # que acontece quando uma planilha traz a categoria na coluna "tipo".
        # Veja também o teste xfail em test_file_import_service.py.
        resumo = summarize_transactions(
            [tx("Mercado", 100, "Debito"), tx("Farmácia", 65, "farmacia")]
        )
        assert resumo.total_gastos == 100
        assert "Farmácia" not in resumo.category_totals


class TestCategorias:
    def test_agrega_varios_gastos_na_mesma_categoria(self):
        resumo = summarize_transactions(
            [
                tx("Alimentação", 20, "Debito"),
                tx("Alimentação", 30, "Debito"),
                tx("Supermercado", 100, "Debito"),
            ]
        )
        assert resumo.category_totals == {"Alimentação": 50, "Supermercado": 100}

    def test_receitas_nao_entram_no_detalhamento_por_categoria(self):
        resumo = summarize_transactions(
            [tx("Salário", 2000, "Credito"), tx("Mercado", 100, "Debito")]
        )
        assert resumo.category_totals == {"Mercado": 100}

    def test_categoria_fora_da_lista_conhecida_e_aceita_como_esta(self):
        # O sistema não restringe categorias a uma lista fixa.
        resumo = summarize_transactions([tx("Aluguel de Fantasia", 80, "Debito")])
        assert resumo.category_totals == {"Aluguel de Fantasia": 80}

    def test_categorias_diferentes_so_no_acento_ou_caixa_sao_separadas(self):
        # Documenta o comportamento atual: não há normalização de categoria.
        resumo = summarize_transactions(
            [tx("Alimentação", 10, "Debito"), tx("alimentacao", 10, "Debito")]
        )
        assert len(resumo.category_totals) == 2


class TestGraficoETexto:
    def test_chart_data_vem_ordenado_do_maior_para_o_menor(self):
        resumo = summarize_transactions(
            [
                tx("Pequena", 10, "Debito"),
                tx("Grande", 300, "Debito"),
                tx("Media", 50, "Debito"),
            ]
        )
        assert [item["name"] for item in resumo.chart_data] == ["Grande", "Media", "Pequena"]

    def test_chart_data_tem_nome_valor_e_cor(self):
        resumo = summarize_transactions([tx("Mercado", 12.345, "Debito")])
        item = resumo.chart_data[0]
        assert item == {"name": "Mercado", "value": 12.35, "fill": PALETA_FINANCEIRA[0]}

    def test_cores_se_repetem_quando_ha_mais_categorias_que_a_paleta(self):
        transacoes = [tx(f"cat{i}", 100 - i, "Debito") for i in range(len(PALETA_FINANCEIRA) + 2)]
        chart = summarize_transactions(transacoes).chart_data
        assert chart[len(PALETA_FINANCEIRA)]["fill"] == PALETA_FINANCEIRA[0]

    def test_category_list_fmt_traz_valor_formatado(self):
        resumo = summarize_transactions([tx("Mercado", 1234.5, "Debito")])
        assert resumo.category_list_fmt[0]["value_fmt"] == "R$ 1.234,50"

    def test_propriedades_formatadas(self):
        resumo = summarize_transactions(
            [tx("Salário", 2000, "Credito"), tx("Mercado", 500, "Debito")]
        )
        assert resumo.receitas_fmt == "R$ 2.000,00"
        assert resumo.gastos_fmt == "R$ 500,00"
        assert resumo.saldo_fmt == "R$ 1.500,00"

    def test_texto_do_prompt_contem_os_totais_reais(self):
        resumo = summarize_transactions(
            [tx("Salário", 1000, "Credito"), tx("Padaria", 20, "Debito")]
        )
        texto = resumo.as_text
        assert "Total Recebido (Créditos): R$ 1000.00" in texto
        assert "Total Gasto Registrado (Débitos): R$ 20.00" in texto
        assert "Saldo Atual: R$ 980.00" in texto
        assert "- Padaria: R$ 20.00" in texto

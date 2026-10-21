"""Testes das funções novas do projeto real: datas, aba Transações e relatório mensal."""
from datetime import date, datetime

import pytest

from assessor_financeiro.core.transaction_service import (
    calcular_relatorio_mensal,
    filtrar_e_agrupar_transacoes,
    listar_transacoes_detalhadas,
    montar_opcoes_de_mes,
    parse_data_flexivel,
)
from assessor_financeiro.models.db_models import Transaction
from assessor_financeiro.state import AdvisorState


class TestParseDataFlexivel:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("12/08/2026", datetime(2026, 8, 12)),
            ("01/09/2026", datetime(2026, 9, 1)),
            ("2026-08-12", datetime(2026, 8, 12)),  # ISO: não pode inverter dia/mês
            ("2026-09-01", datetime(2026, 9, 1)),
            ("20260820", datetime(2026, 8, 20)),
            (date(2026, 8, 12), datetime(2026, 8, 12)),
            (datetime(2026, 8, 12, 9, 30), datetime(2026, 8, 12, 9, 30)),
        ],
    )
    def test_formatos_validos(self, entrada, esperado):
        assert parse_data_flexivel(entrada) == esperado

    def test_iso_com_hora_e_fuso_mantem_dia_e_mes(self):
        resultado = parse_data_flexivel("2026-09-01T10:00:00+00:00")
        assert (resultado.month, resultado.day) == (9, 1)

    @pytest.mark.parametrize("entrada", [None, "", "   ", "nan", "NaT", "none", "lixo qualquer"])
    def test_valores_invalidos_viram_none(self, entrada):
        assert parse_data_flexivel(entrada) is None


class TestParseDataExtraida:
    def test_formato_do_agente(self):
        assert AdvisorState._parse_data_extraida("2026-08-12") == datetime(2026, 8, 12)

    @pytest.mark.parametrize("entrada", [None, "", "12/08/2026", "ontem"])
    def test_formato_inesperado_vira_none(self, entrada):
        assert AdvisorState._parse_data_extraida(entrada) is None


def tx(tipo, valor, cat="X", quando=None, id_=1):
    t = Transaction(category=cat, amount=valor, type=tipo, created_at=quando)
    t.id = id_
    return t


class TestAbaTransacoes:
    def test_ordena_mais_recente_primeiro_e_sem_data_no_fim(self):
        itens = listar_transacoes_detalhadas([
            tx("Debito", 10, quando=datetime(2026, 8, 1), id_=1),
            tx("Debito", 20, quando=datetime(2026, 9, 1), id_=2),
            tx("Debito", 30, quando=None, id_=3),
        ])
        assert [i["id"] for i in itens] == [2, 1, 3]
        assert itens[-1]["data_iso"] == "sem-data"

    def test_sinal_e_formatacao(self):
        itens = listar_transacoes_detalhadas([
            tx("Credito", 1000, quando=datetime(2026, 8, 1)),
            tx("Debito", 40, quando=datetime(2026, 8, 2)),
        ])
        por_tipo = {i["type"]: i["amount_fmt_signed"] for i in itens}
        assert por_tipo["Credito"] == "+ R$ 1.000,00"
        assert por_tipo["Debito"] == "- R$ 40,00"

    def test_opcoes_de_mes_mais_recente_primeiro(self):
        itens = listar_transacoes_detalhadas([
            tx("Debito", 1, quando=datetime(2026, 7, 5)),
            tx("Debito", 1, quando=datetime(2026, 9, 5)),
            tx("Debito", 1, quando=None),
        ])
        opcoes = montar_opcoes_de_mes(itens)
        assert [o["value"] for o in opcoes] == ["Todos", "2026-09", "2026-07"]
        assert opcoes[1]["label"] == "Setembro/2026"

    def test_filtro_por_tipo_e_mes(self):
        itens = listar_transacoes_detalhadas([
            tx("Credito", 100, quando=datetime(2026, 8, 1), id_=1),
            tx("Debito", 10, quando=datetime(2026, 8, 2), id_=2),
            tx("Debito", 20, quando=datetime(2026, 9, 2), id_=3),
        ])
        saidas = filtrar_e_agrupar_transacoes(itens, tipo="Saidas")
        assert sorted(i["id"] for g in saidas for i in g["itens"]) == [2, 3]
        entradas_ago = filtrar_e_agrupar_transacoes(itens, tipo="Entradas", mes="2026-08")
        assert [i["id"] for g in entradas_ago for i in g["itens"]] == [1]

    def test_agrupa_por_dia_com_rotulos(self):
        agora = datetime.now()
        itens = listar_transacoes_detalhadas([
            tx("Debito", 1, quando=agora, id_=1),
            tx("Debito", 2, quando=agora, id_=2),
            tx("Debito", 3, quando=datetime(2020, 1, 15), id_=3),
        ])
        grupos = filtrar_e_agrupar_transacoes(itens)
        assert [g["rotulo"] for g in grupos] == ["Hoje", "15/01/2020"]
        assert len(grupos[0]["itens"]) == 2


class TestRelatorioMensal:
    def test_devolve_n_meses_continuos_incluindo_vazios(self):
        rel = calcular_relatorio_mensal([], meses=6)
        assert len(rel) == 6
        assert all(r["Entradas"] == 0 and r["Saidas"] == 0 for r in rel)

    def test_soma_entradas_e_saidas_do_mes_atual(self):
        agora = datetime.now()
        rel = calcular_relatorio_mensal([
            tx("Credito", 1000, quando=agora),
            tx("Debito", 40, quando=agora),
            tx("Debito", -10, quando=agora),  # negativo vira módulo
            tx("Debito", 99, quando=None),  # sem data é ignorada
        ], meses=3)
        assert rel[-1]["Entradas"] == 1000.0
        assert rel[-1]["Saidas"] == 50.0

    def test_transacao_fora_da_janela_e_ignorada(self):
        rel = calcular_relatorio_mensal([tx("Debito", 500, quando=datetime(2000, 1, 1))], meses=6)
        assert sum(r["Saidas"] for r in rel) == 0

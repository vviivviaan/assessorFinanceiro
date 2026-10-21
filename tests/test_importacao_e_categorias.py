"""Testes de fatura/extrato (normalização, validação do tipo) e categorização automática."""
import pytest

from assessor_financeiro.core.categorizacao import categoria_ou_descricao, categorizar
from assessor_financeiro.core.file_import_service import (
    ORIGEM_EXTRATO,
    ORIGEM_FATURA,
    ErroImportacao,
    parse_extrato_com_resumo,
    parse_extrato_tabular,
)
from assessor_financeiro.state import AdvisorState


def csv(texto: str) -> bytes:
    return texto.encode("utf-8")


class TestCategorizacao:
    @pytest.mark.parametrize(
        ("descricao", "esperada"),
        [
            ("Netflix", "Assinaturas"),
            ("NETFLIX.COM 03/10", "Assinaturas"),
            ("Padaria Pão Quente", "Alimentação"),
            ("Supermercado Extrabom", "Supermercado"),
            ("UBER *TRIP", "Transporte"),
            ("Drogaria Raia", "Saúde"),
            ("Farmácia Popular", "Saúde"),
            ("Posto Ipiranga", "Combustível"),
            ("Borracharia do Zé", "Manutenção/Veículo"),
            ("Salário setembro", "Salário"),
            ("Mensalidade Smart Fit", "Academia"),
        ],
    )
    def test_reconhece(self, descricao, esperada):
        assert categorizar(descricao) == esperada

    def test_ignora_acentos_e_caixa(self):
        assert categorizar("FARMÁCIA") == categorizar("farmacia") == "Saúde"

    def test_nao_casa_no_meio_de_outra_palavra(self):
        # "oi" não deve casar dentro de "boi", "luz" dentro de "luzia"...
        assert categorizar("Boi Gordo") is None
        assert categorizar("Churrasco do Boi Gordo") is None
        assert categorizar("Luzia Costa") is None

    def test_sem_regra_devolve_none_e_mantem_a_descricao(self):
        assert categorizar("Fulano de Tal") is None
        assert categoria_ou_descricao("  Fulano de Tal ") == "Fulano de Tal"

    def test_descricao_vazia(self):
        assert categoria_ou_descricao("") == "Sem descrição"
        assert categoria_ou_descricao(None) == "Sem descrição"


class TestValidacaoDoTipo:
    def test_categoria_na_coluna_tipo_e_rejeitada_com_mensagem_util(self):
        with pytest.raises(ErroImportacao, match="Linha 1.*'supermercado'.*Credito"):
            parse_extrato_tabular("g.csv", csv("01/09/2026,compras,156,supermercado\n"))

    def test_erro_aponta_a_linha_certa(self):
        bruto = csv("01/09/2026,a,10,Debito\n02/09/2026,b,20,lixo\n")
        with pytest.raises(ErroImportacao, match="Linha 2"):
            parse_extrato_tabular("g.csv", bruto)

    def test_valor_nao_numerico_e_rejeitado(self):
        with pytest.raises(ErroImportacao, match="não é um número"):
            parse_extrato_tabular("g.csv", csv("01/09/2026,ok,10,Debito\n02/09/2026,a,abc,Debito\n"))

    def test_erro_de_importacao_continua_sendo_value_error(self):
        assert issubclass(ErroImportacao, ValueError)

    @pytest.mark.parametrize("tipo", ["Credito", "Crédito", "credito", "CRÉDITO"])
    def test_variacoes_de_credito_viram_credito(self, tipo):
        df = parse_extrato_tabular("g.csv", csv(f"01/09/2026,x,10,{tipo}\n"))
        assert df.iloc[0]["tipo"] == "Credito"

    def test_valor_com_virgula_e_real(self):
        df = parse_extrato_tabular("g.csv", csv('01/09/2026,x,"1.234,50",Debito\n'))
        assert df.iloc[0]["valor"] == 1234.5

    def test_valor_sai_em_modulo(self):
        df = parse_extrato_tabular("g.csv", csv("01/09/2026,x,-43.13,Debito\n"))
        assert df.iloc[0]["valor"] == 43.13


class TestTipoDeduzidoPeloSinal:
    def test_extrato_sem_coluna_tipo(self):
        df = parse_extrato_tabular("e.csv", csv("01/09/2026,Salário,2500\n02/09/2026,Padaria,-30\n"))
        assert list(df["tipo"]) == ["Credito", "Debito"]

    def test_fatura_sem_coluna_tipo_compra_positiva_e_debito(self):
        df, _ = parse_extrato_com_resumo(
            "f.csv", csv("01/09/2026,Netflix,43.13\n02/09/2026,Estorno loja,-20\n"), ORIGEM_FATURA
        )
        assert list(df["tipo"]) == ["Debito", "Credito"]

    def test_tipo_explicito_vence_o_sinal(self):
        df = parse_extrato_tabular("e.csv", csv("01/09/2026,x,-50,Credito\n"))
        assert df.iloc[0]["tipo"] == "Credito"


class TestFatura:
    def test_pagamento_da_fatura_e_descartado_e_contado(self):
        bruto = csv(
            "01/09/2026,Netflix,43.13\n"
            "05/09/2026,PAGAMENTO RECEBIDO,-1500\n"
            "06/09/2026,Saldo anterior,900\n"
            "07/09/2026,Uber,18.90\n"
        )
        df, ignoradas = parse_extrato_com_resumo("f.csv", bruto, ORIGEM_FATURA)
        assert list(df["descricao"]) == ["Netflix", "Uber"]
        assert ignoradas == 2

    def test_extrato_nao_descarta_linha_com_palavra_pagamento(self):
        bruto = csv("01/09/2026,Pagamento de boleto,100,Debito\n")
        df, ignoradas = parse_extrato_com_resumo("e.csv", bruto, ORIGEM_EXTRATO)
        assert len(df) == 1 and ignoradas == 0

    def test_extrato_sintetico_do_repositorio_continua_valido(self):
        from pathlib import Path

        caminho = Path(__file__).parent.parent / "dados" / "extrato_sintetico.csv"
        df = parse_extrato_tabular("extrato.csv", caminho.read_bytes())
        assert len(df) > 0 and set(df["tipo"]) <= {"Credito", "Debito"}


class TestResumoDaImportacao:
    def test_lista_principais_categorias_e_pagamentos_ignorados(self):
        texto = AdvisorState._resumo_importacao(
            "fatura do cartão",
            [
                {"category": "Assinaturas", "amount": 1.0, "type": "Debito"},
                {"category": "Assinaturas", "amount": 1.0, "type": "Debito"},
                {"category": "Transporte", "amount": 1.0, "type": "Debito"},
            ],
            pagamentos_ignorados=1,
        )
        assert "3 transação(ões)" in texto
        assert "Assinaturas (2), Transporte (1)" in texto
        assert "Ignorei 1 linha(s)" in texto

    def test_sem_pagamentos_nao_menciona_ignoradas(self):
        texto = AdvisorState._resumo_importacao(
            "extrato", [{"category": "A", "amount": 1.0, "type": "Debito"}], 0
        )
        assert "Ignorei" not in texto


def test_regra_mais_especifica_vence_a_generica():
    assert categorizar("Mercado Livre") == "Compras"
    assert categorizar("Amazon Prime") == "Assinaturas"
    assert categorizar("Mercado Central") == "Supermercado"


class TestTresColunas:
    def test_csv_com_cabecalho_e_sem_coluna_tipo(self):
        df = parse_extrato_tabular("f.csv", csv("data,descricao,valor\n01/09/2026,Netflix,43.13\n"))
        assert len(df) == 1 and df.iloc[0]["tipo"] == "Credito"  # extrato: positivo = entrada

    def test_xlsx_com_tres_colunas(self):
        import io

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["data", "descricao", "valor"])
        ws.append(["01/09/2026", "Uber", 18.9])
        buffer = io.BytesIO()
        wb.save(buffer)
        df, _ = parse_extrato_com_resumo("f.xlsx", buffer.getvalue(), ORIGEM_FATURA)
        assert list(df["tipo"]) == ["Debito"]

    def test_menos_de_tres_colunas_da_mensagem_clara(self):
        with pytest.raises(ErroImportacao, match="pelo menos 3 colunas"):
            parse_extrato_tabular("f.csv", csv("a,b\n1,2\n"))

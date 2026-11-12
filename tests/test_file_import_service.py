"""Testes da importação de extratos (core/file_import_service.py)."""
import io

import pytest
from openpyxl import Workbook

from assessor_financeiro.core.file_import_service import (
    COLUNAS_PADRAO,
    parse_extrato_tabular,
    parse_transacoes_csv,
    parse_transacoes_ofx,
    parse_transacoes_xlsx,
)

CSV_SEM_CABECALHO = (
    "22/05/2026,Salário,6500.00,Crédito\n"
    "22/05/2026,Netflix,-43.13,Debito\n"
    "30/05/2026,Mercado,120.50,Debito\n"
).encode("utf-8")

CSV_COM_CABECALHO = ("data,descricao,valor,tipo\n" + CSV_SEM_CABECALHO.decode("utf-8")).encode("utf-8")


class TestCsv:
    def test_le_csv_sem_cabecalho(self):
        df = parse_transacoes_csv(CSV_SEM_CABECALHO)
        assert list(df.columns) == COLUNAS_PADRAO
        assert len(df) == 3
        assert df.iloc[0]["descricao"] == "Salário"
        assert df.iloc[0]["valor"] == 6500.0

    def test_detecta_e_descarta_linha_de_cabecalho(self):
        df = parse_transacoes_csv(CSV_COM_CABECALHO)
        assert len(df) == 3
        assert df.iloc[0]["descricao"] == "Salário"
        assert "valor" not in df["valor"].astype(str).tolist()

    def test_com_e_sem_cabecalho_dao_o_mesmo_resultado(self):
        sem = parse_transacoes_csv(CSV_SEM_CABECALHO)
        com = parse_transacoes_csv(CSV_COM_CABECALHO)
        assert sem.reset_index(drop=True).equals(com.reset_index(drop=True))

    def test_preserva_acentos(self):
        df = parse_transacoes_csv(CSV_SEM_CABECALHO)
        assert df.iloc[0]["tipo"] == "Crédito"

    def test_remove_espacos_extras_em_descricao_e_tipo(self):
        bruto = "01/09/2026,  Padaria  ,30.00,  Debito  \n".encode("utf-8")
        df = parse_transacoes_csv(bruto)
        assert df.iloc[0]["descricao"] == "Padaria"
        assert df.iloc[0]["tipo"] == "Debito"

    def test_le_o_csv_de_exemplo_do_repositorio(self):
        from pathlib import Path

        caminho = Path(__file__).parent.parent / "dados" / "extrato_sintetico.csv"
        df = parse_transacoes_csv(caminho.read_bytes())
        assert len(df) > 0
        assert set(df["tipo"].str.lower()) <= {"credito", "crédito", "debito", "débito"}


class TestXlsx:
    @staticmethod
    def _xlsx(linhas: list[list]) -> bytes:
        wb = Workbook()
        ws = wb.active
        for linha in linhas:
            ws.append(linha)
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    def test_le_xlsx_sem_cabecalho(self):
        bruto = self._xlsx([["01/09/2026", "Padaria", 30.0, "Debito"]])
        df = parse_transacoes_xlsx(bruto)
        assert len(df) == 1
        assert df.iloc[0]["descricao"] == "Padaria"

    def test_le_xlsx_com_cabecalho(self):
        bruto = self._xlsx(
            [
                ["data", "descricao", "valor", "tipo"],
                ["01/09/2026", "Padaria", 30.0, "Debito"],
                ["02/09/2026", "Salário", 2500.0, "Credito"],
            ]
        )
        df = parse_transacoes_xlsx(bruto)
        assert len(df) == 2
        assert df.iloc[1]["tipo"] == "Credito"


OFX_EXEMPLO = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20260901120000<LANGUAGE>POR</SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>
<STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>001<ACCTID>12345<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST><DTSTART>20260801<DTEND>20260901
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260820120000<TRNAMT>-45.90<FITID>1<MEMO>Padaria</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260825120000<TRNAMT>2500.00<FITID>2<MEMO>Salario</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>2454.10<DTASOF>20260901</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
"""


class TestOfx:
    def test_tipo_vem_do_sinal_do_valor(self):
        df = parse_transacoes_ofx(OFX_EXEMPLO)
        por_descricao = {linha.descricao: linha for linha in df.itertuples()}
        assert por_descricao["Padaria"].tipo == "Debito"
        assert por_descricao["Salario"].tipo == "Credito"

    def test_valor_sai_em_modulo(self):
        df = parse_transacoes_ofx(OFX_EXEMPLO)
        assert (df["valor"] > 0).all()
        assert sorted(df["valor"].tolist()) == [45.9, 2500.0]


class TestDespachoPorExtensao:
    def test_csv(self):
        assert len(parse_extrato_tabular("extrato.csv", CSV_SEM_CABECALHO)) == 3

    def test_extensao_em_maiusculas(self):
        assert len(parse_extrato_tabular("EXTRATO.CSV", CSV_SEM_CABECALHO)) == 3

    def test_ofx(self):
        assert len(parse_extrato_tabular("banco.ofx", OFX_EXEMPLO)) == 2

    @pytest.mark.parametrize("nome", ["notas.txt", "foto.png", "semextensao"])
    def test_formato_nao_suportado_levanta_erro(self, nome):
        with pytest.raises(ValueError, match="não suportado"):
            parse_extrato_tabular(nome, b"qualquer coisa")


class TestLacunasConhecidas:
    # Era uma lacuna conhecida (xfail): a validação da coluna "tipo" já foi feita.
    def test_tipo_que_nao_e_credito_nem_debito_deveria_ser_rejeitado(self):
        bruto = "01/09/2026,compras do mês,156,supermercado\n".encode("utf-8")
        with pytest.raises(ValueError):
            parse_extrato_tabular("gastos.csv", bruto)

"""Testes das melhorias de base: fallback que respeita as chaves da usuária e
importação de CSV no formato dos bancos/Excel brasileiros."""
from types import SimpleNamespace

import pytest
from agno.run.base import RunStatus

from assessor_financeiro.core.file_import_service import ErroImportacao, parse_extrato_com_resumo
from assessor_financeiro.core.transaction_service import parse_data_flexivel
from assessor_financeiro.llm.fallback import ordem_de_provedores, run_with_fallback


@pytest.fixture(autouse=True)
def sem_chaves_no_env(monkeypatch):
    for variavel in ("GROQ_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(variavel, raising=False)


class TestFallbackComChavesDaUsuaria:
    def test_quem_so_tem_chave_do_google_usa_o_google(self):
        assert ordem_de_provedores("groq", {"google": "k"}) == ["google"]

    def test_ordem_preferido_secundario_e_depois_os_demais(self):
        chaves = {"google": "g", "groq": "q", "anthropic": "a"}
        assert ordem_de_provedores("anthropic", chaves) == ["anthropic", "groq", "google"]

    def test_sem_nenhuma_chave_nao_ha_o_que_tentar(self):
        assert ordem_de_provedores("groq", {}) == []
        resposta, provedor = run_with_fallback(lambda p: None, "groq", "oi", api_keys={})
        assert resposta is None and provedor == "groq"

    def test_pula_provedor_sem_chave_e_responde_com_o_que_tem(self):
        chamados = []

        def fabrica(provedor):
            chamados.append(provedor)
            return SimpleNamespace(
                run=lambda mensagem: SimpleNamespace(status=RunStatus.completed, content=provedor)
            )

        resposta, provedor = run_with_fallback(fabrica, "groq", "oi", api_keys={"anthropic": "a"})
        assert (resposta.content, provedor, chamados) == ("anthropic", "anthropic", ["anthropic"])

    def test_se_o_primeiro_falha_tenta_o_proximo_com_chave(self):
        def fabrica(provedor):
            status = RunStatus.error if provedor == "groq" else RunStatus.completed
            return SimpleNamespace(run=lambda mensagem: SimpleNamespace(status=status, content=provedor))

        resposta, provedor = run_with_fallback(
            fabrica, "groq", "oi", api_keys={"groq": "q", "google": "g"}
        )
        assert (resposta.content, provedor) == ("google", "google")


class TestCsvBrasileiro:
    def test_ponto_e_virgula_e_latin1(self):
        bruto = "Data;Descrição;Valor;Tipo\n01/09/2026;Farmácia;-43,13;\n02/09/2026;Salário;2.500,00;Crédito\n"
        df, _ = parse_extrato_com_resumo("extrato.csv", bruto.encode("cp1252"))
        assert df.values.tolist() == [
            ["01/09/2026", "Farmácia", 43.13, "Debito"],
            ["02/09/2026", "Salário", 2500.0, "Credito"],
        ]

    def test_utf8_com_bom(self):
        df, _ = parse_extrato_com_resumo("x.csv", "﻿01/09/2026;Mercado;-156,00\n".encode("utf-8"))
        assert df.values.tolist() == [["01/09/2026", "Mercado", 156.0, "Debito"]]

    def test_tabulacao(self):
        df, _ = parse_extrato_com_resumo("x.csv", b"01/09/2026\tMercado\t156.00\tDebito\n")
        assert df.values.tolist() == [["01/09/2026", "Mercado", 156.0, "Debito"]]

    @pytest.mark.parametrize("bruto", [b"", b"a,b,c\n1,2,3,4,5,6\n"])
    def test_arquivo_vazio_ou_torto_da_mensagem_clara(self, bruto):
        with pytest.raises(ErroImportacao):
            parse_extrato_com_resumo("x.csv", bruto)


def test_data_compacta_de_ofx():
    assert parse_data_flexivel("20260812").strftime("%d/%m/%Y") == "12/08/2026"

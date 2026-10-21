"""Testes da PoC de Open Finance (core/open_finance/): fluxo de consentimento e conversão."""
import pytest

from assessor_financeiro.core.open_finance.importer import transacao_ofb_para_transacao_app
from assessor_financeiro.core.open_finance.mock_client import (
    ConsentimentoNaoAutorizado,
    ConsentimentoNaoEncontrado,
    OpenFinanceMockClient,
)
from assessor_financeiro.core.open_finance.schemas import (
    CreditoDebito,
    Permissao,
    StatusConsentimento,
    TipoTransacao,
    TransacaoData,
    ValorMonetario,
)

TODAS = [Permissao.ACCOUNTS_READ, Permissao.ACCOUNTS_TRANSACTIONS_READ]


def transacao(tipo: CreditoDebito, valor: str, nome: str = "Teste") -> TransacaoData:
    return TransacaoData(
        transactionId="1",
        creditDebitType=tipo,
        transactionName=nome,
        type=TipoTransacao.PIX,
        transactionAmount=ValorMonetario(amount=valor),
        transactionDateTime="2026-09-01T10:00:00+00:00",
    )


class TestConversao:
    def test_credito_vira_credito(self):
        resultado = transacao_ofb_para_transacao_app(transacao(CreditoDebito.CREDITO, "2500.00", "Salário"))
        assert {k: resultado[k] for k in ("category", "amount", "type")} == {
            "category": "Salário", "amount": 2500.0, "type": "Credito"}
        assert (resultado["created_at"].month, resultado["created_at"].day) == (9, 1)

    def test_debito_vira_debito(self):
        resultado = transacao_ofb_para_transacao_app(transacao(CreditoDebito.DEBITO, "45.90", "Padaria"))
        assert {k: resultado[k] for k in ("category", "amount", "type")} == {
            "category": "Padaria", "amount": 45.9, "type": "Debito"}

    def test_valor_negativo_vira_modulo(self):
        resultado = transacao_ofb_para_transacao_app(transacao(CreditoDebito.DEBITO, "-45.90"))
        assert resultado["amount"] == 45.9


class TestFluxoDeConsentimento:
    def test_consentimento_nasce_aguardando_autorizacao(self):
        consentimento = OpenFinanceMockClient().criar_consentimento(TODAS)
        assert consentimento.status == StatusConsentimento.AWAITING_AUTHORISATION

    def test_nao_lista_contas_sem_autorizacao(self):
        cliente = OpenFinanceMockClient()
        consentimento = cliente.criar_consentimento(TODAS)
        with pytest.raises(ConsentimentoNaoAutorizado):
            cliente.listar_contas(consentimento.consentId)

    def test_consentimento_inexistente_levanta_erro(self):
        with pytest.raises(ConsentimentoNaoEncontrado):
            OpenFinanceMockClient().autorizar_consentimento("nao-existe")

    def test_fluxo_completo_devolve_contas_e_transacoes(self):
        cliente = OpenFinanceMockClient()
        consentimento = cliente.criar_consentimento(TODAS)
        cliente.autorizar_consentimento(consentimento.consentId)

        contas = cliente.listar_contas(consentimento.consentId)
        transacoes = cliente.listar_transacoes(consentimento.consentId, contas[0].accountId, quantidade=12)

        assert len(contas) == 1
        assert len(transacoes) == 12
        assert sum(t.creditDebitType == CreditoDebito.CREDITO for t in transacoes) == 1

    def test_permissao_nao_concedida_e_negada(self):
        cliente = OpenFinanceMockClient()
        consentimento = cliente.criar_consentimento([Permissao.ACCOUNTS_READ])
        cliente.autorizar_consentimento(consentimento.consentId)
        contas = cliente.listar_contas(consentimento.consentId)

        with pytest.raises(ConsentimentoNaoAutorizado, match="ACCOUNTS_TRANSACTIONS_READ"):
            cliente.listar_transacoes(consentimento.consentId, contas[0].accountId)

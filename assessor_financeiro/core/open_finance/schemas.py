"""Schemas fiéis à especificação oficial do Open Finance Brasil.

Campos e enums retirados das especificações OpenAPI oficiais publicadas em
github.com/OpenBanking-Brasil/openapi:
- swagger-apis/consents (versão 3.3.1) — consentimento
- swagger-apis/accounts (versão 2.4.2) — contas e transações

Isso é o que permite trocar o `OpenFinanceMockClient` por um cliente real no
futuro sem mudar mais nada no resto do app: quem consome estes schemas não
precisa saber se os dados vieram de uma simulação ou de uma chamada HTTP real.
"""
from enum import Enum

from pydantic import BaseModel


class Permissao(str, Enum):
    """Subconjunto das permissões oficiais relevantes para esta PoC (leitura de contas/transações)."""

    ACCOUNTS_READ = "ACCOUNTS_READ"
    ACCOUNTS_BALANCES_READ = "ACCOUNTS_BALANCES_READ"
    ACCOUNTS_TRANSACTIONS_READ = "ACCOUNTS_TRANSACTIONS_READ"
    RESOURCES_READ = "RESOURCES_READ"


class StatusConsentimento(str, Enum):
    AWAITING_AUTHORISATION = "AWAITING_AUTHORISATION"
    AUTHORISED = "AUTHORISED"
    REJECTED = "REJECTED"


class TipoConta(str, Enum):
    CONTA_DEPOSITO_A_VISTA = "CONTA_DEPOSITO_A_VISTA"
    CONTA_POUPANCA = "CONTA_POUPANCA"
    CONTA_PAGAMENTO_PRE_PAGA = "CONTA_PAGAMENTO_PRE_PAGA"


class CreditoDebito(str, Enum):
    CREDITO = "CREDITO"
    DEBITO = "DEBITO"


class TipoTransacao(str, Enum):
    """Subconjunto do enum oficial `type` da API de Transações — o suficiente
    para gerar uma amostra realista sem replicar as ~17 categorias inteiras."""

    TED = "TED"
    PIX = "PIX"
    BOLETO = "BOLETO"
    DEPOSITO = "DEPOSITO"
    SAQUE = "SAQUE"
    CARTAO = "CARTAO"
    TARIFA_SERVICOS_AVULSOS = "TARIFA_SERVICOS_AVULSOS"
    OUTROS = "OUTROS"


class Consentimento(BaseModel):
    """Espelha `data` da resposta de POST/GET /consents."""

    consentId: str
    status: StatusConsentimento
    permissions: list[Permissao]
    creationDateTime: str
    expirationDateTime: str


class ContaData(BaseModel):
    """Espelha um item de `data` da resposta de GET /accounts."""

    accountId: str
    brandName: str
    companyCnpj: str
    type: TipoConta
    compeCode: str
    branchCode: str | None = None
    number: str
    checkDigit: str


class ValorMonetario(BaseModel):
    """Espelha o objeto `transactionAmount` (valor + moeda)."""

    amount: str
    currency: str = "BRL"


class TransacaoData(BaseModel):
    """Espelha um item de `data` da resposta de GET /accounts/{accountId}/transactions."""

    transactionId: str
    completedAuthorisedPaymentType: str = "TRANSACAO_EFETIVADA"
    creditDebitType: CreditoDebito
    transactionName: str
    type: TipoTransacao
    transactionAmount: ValorMonetario
    transactionDateTime: str

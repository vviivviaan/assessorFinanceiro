"""Cliente MOCK das APIs de Dados do Open Finance Brasil (Fase 2).

Esta é uma PoC (prova de conceito): o app não está credenciado no Diretório
de Participantes nem tem certificado ICP-Brasil, então uma chamada real às
APIs de produção do Open Finance não é possível. Este cliente SIMULA o fluxo
oficial (consentimento -> autorização -> consulta de contas/transações) e
devolve dados fake, mas usando os MESMOS campos e enums da especificação real
(ver `schemas.py`).

Para plugar uma instituição real no futuro, a mudança fica isolada aqui: um
`OpenFinanceHttpClient` reimplementaria estes mesmos métodos com chamadas
HTTP (mTLS + FAPI) às APIs verdadeiras, devolvendo os mesmos schemas — nada
em `state.py` ou `importer.py` precisaria mudar.
"""
import random
import uuid
from datetime import datetime, timedelta, timezone

from faker import Faker

from assessor_financeiro.core.open_finance.schemas import (
    Consentimento,
    ContaData,
    CreditoDebito,
    Permissao,
    StatusConsentimento,
    TipoConta,
    TipoTransacao,
    TransacaoData,
    ValorMonetario,
)

_faker = Faker("pt_BR")

_CATEGORIAS_DEBITO: list[tuple[str, TipoTransacao]] = [
    ("Supermercado", TipoTransacao.CARTAO),
    ("Restaurante", TipoTransacao.PIX),
    ("Posto de Combustível", TipoTransacao.CARTAO),
    ("Farmácia", TipoTransacao.CARTAO),
    ("Assinatura de Streaming", TipoTransacao.TARIFA_SERVICOS_AVULSOS),
    ("Conta de Internet", TipoTransacao.BOLETO),
    ("Transferência PIX", TipoTransacao.PIX),
    ("Saque", TipoTransacao.SAQUE),
]


class ConsentimentoNaoEncontrado(Exception):
    pass


class ConsentimentoNaoAutorizado(Exception):
    pass


class OpenFinanceMockClient:
    """Simula um cliente de dados do Open Finance Brasil para uma instituição."""

    def __init__(self):
        self._consentimentos: dict[str, Consentimento] = {}

    def criar_consentimento(self, permissoes: list[Permissao]) -> Consentimento:
        """Equivalente a `POST /consents` — cria o consentimento em estado inicial."""
        agora = datetime.now(timezone.utc)
        consentimento = Consentimento(
            consentId=f"urn:bancomock:consent:{uuid.uuid4()}",
            status=StatusConsentimento.AWAITING_AUTHORISATION,
            permissions=permissoes,
            creationDateTime=agora.isoformat(),
            expirationDateTime=(agora + timedelta(days=90)).isoformat(),
        )
        self._consentimentos[consentimento.consentId] = consentimento
        return consentimento

    def autorizar_consentimento(self, consent_id: str) -> Consentimento:
        """Simula o retorno do fluxo de autorização (OAuth2/FAPI) no banco do usuário.

        Numa integração real, entre `criar_consentimento` e este método
        aconteceria um redirecionamento do usuário para o app/site da
        instituição detentora dos dados, onde ele revisaria e aprovaria o
        compartilhamento. Aqui, simulamos a aprovação acontecendo direto.
        """
        consentimento = self._consentimentos.get(consent_id)
        if consentimento is None:
            raise ConsentimentoNaoEncontrado(consent_id)
        consentimento.status = StatusConsentimento.AUTHORISED
        return consentimento

    def listar_contas(self, consent_id: str) -> list[ContaData]:
        """Equivalente a `GET /accounts`."""
        self._exigir_permissao(consent_id, Permissao.ACCOUNTS_READ)
        return [
            ContaData(
                accountId=str(uuid.uuid4()),
                brandName="Banco Mock S.A.",
                companyCnpj="00000000000191",
                type=TipoConta.CONTA_DEPOSITO_A_VISTA,
                compeCode="001",
                branchCode="0001",
                number=str(_faker.random_number(digits=7, fix_len=True)),
                checkDigit=str(random.randint(0, 9)),
            )
        ]

    def listar_transacoes(
        self, consent_id: str, account_id: str, quantidade: int = 12
    ) -> list[TransacaoData]:
        """Equivalente a `GET /accounts/{accountId}/transactions`."""
        self._exigir_permissao(consent_id, Permissao.ACCOUNTS_TRANSACTIONS_READ)

        hoje = datetime.now(timezone.utc)
        transacoes = [self._gerar_transacao(hoje, credito=True)]
        transacoes += [self._gerar_transacao(hoje, credito=False) for _ in range(quantidade - 1)]
        return transacoes

    def _gerar_transacao(self, referencia: datetime, credito: bool) -> TransacaoData:
        data = referencia - timedelta(days=random.randint(0, 28))

        if credito:
            nome, tipo = "Salário", TipoTransacao.TED
            valor = round(random.uniform(2500, 6000), 2)
        else:
            nome, tipo = random.choice(_CATEGORIAS_DEBITO)
            valor = round(random.uniform(15, 450), 2)

        return TransacaoData(
            transactionId=str(uuid.uuid4()),
            creditDebitType=CreditoDebito.CREDITO if credito else CreditoDebito.DEBITO,
            transactionName=nome,
            type=tipo,
            transactionAmount=ValorMonetario(amount=f"{valor:.2f}"),
            transactionDateTime=data.isoformat(),
        )

    def _exigir_permissao(self, consent_id: str, permissao: Permissao) -> None:
        consentimento = self._consentimentos.get(consent_id)
        if consentimento is None:
            raise ConsentimentoNaoEncontrado(consent_id)
        if consentimento.status != StatusConsentimento.AUTHORISED:
            msg = f"Consentimento '{consent_id}' não autorizado (status: {consentimento.status.value})."
            raise ConsentimentoNaoAutorizado(msg)
        if permissao not in consentimento.permissions:
            msg = f"Consentimento '{consent_id}' não cobre a permissão '{permissao.value}'."
            raise ConsentimentoNaoAutorizado(msg)

"""Converte transações no formato Open Finance Brasil para o formato interno do app."""
from assessor_financeiro.core.open_finance.schemas import CreditoDebito, TransacaoData
from assessor_financeiro.core.transaction_service import parse_data_flexivel


def transacao_ofb_para_transacao_app(transacao: TransacaoData) -> dict:
    """Mapeia um `TransacaoData` (schema oficial) para o dict aceito por `add_transactions`."""
    resultado = {
        "category": transacao.transactionName,
        "amount": abs(float(transacao.transactionAmount.amount)),
        "type": "Credito" if transacao.creditDebitType == CreditoDebito.CREDITO else "Debito",
    }
    data_dt = parse_data_flexivel(transacao.transactionDateTime)
    if data_dt is not None:
        resultado["created_at"] = data_dt
    return resultado

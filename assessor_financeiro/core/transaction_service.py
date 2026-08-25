"""Regras de negócio puras para agregação de transações.

Este módulo não importa `reflex` nem toca o banco — recebe uma lista de
transações e devolve os cálculos prontos. Isso o torna fácil de testar
isoladamente (ex.: `pytest`) sem precisar subir o app inteiro.
"""
from dataclasses import dataclass, field

from assessor_financeiro.config import PALETA_FINANCEIRA
from assessor_financeiro.models.db_models import Transaction

CREDITO_ALIASES = {"credito", "crédito"}
DEBITO_ALIASES = {"debito", "débito"}


@dataclass
class FinancialSummary:
    total_receitas: float = 0.0
    total_gastos: float = 0.0
    saldo_atual: float = 0.0
    category_totals: dict[str, float] = field(default_factory=dict)

    @property
    def chart_data(self) -> list[dict]:
        """Formato pronto para alimentar o `rx.recharts.pie_chart` do dashboard."""
        return [
            {
                "name": str(categoria),
                "value": float(round(valor, 2)),
                "fill": PALETA_FINANCEIRA[i % len(PALETA_FINANCEIRA)],
            }
            for i, (categoria, valor) in enumerate(self.category_totals.items())
        ]

    @property
    def as_text(self) -> str:
        """Texto formatado injetado no prompt do agente conselheiro."""
        texto = (
            "RESUMO ATUAL DO BANCO DE DADOS:\n"
            f"Total Recebido (Créditos): R$ {self.total_receitas:.2f}\n"
            f"Total Gasto Registrado (Débitos): R$ {self.total_gastos:.2f}\n"
            f"Saldo Atual: R$ {self.saldo_atual:.2f}\n\n"
            "Detalhamento de Gastos por Categoria:\n"
        )
        for categoria, valor in self.category_totals.items():
            texto += f"- {categoria}: R$ {valor:.2f}\n"
        return texto


def summarize_transactions(transactions: list[Transaction]) -> FinancialSummary:
    """Calcula totais, saldo e agregação por categoria a partir de uma lista de transações."""
    summary = FinancialSummary()

    for t in transactions:
        # abs() garante que não teremos erros matemáticos se a IA salvar valores negativos acidentalmente
        valor = abs(float(t.amount))
        tipo = t.type.lower().strip()

        if tipo in CREDITO_ALIASES:
            summary.total_receitas += valor
        elif tipo in DEBITO_ALIASES:
            summary.total_gastos += valor
            summary.category_totals[t.category] = (
                summary.category_totals.get(t.category, 0.0) + valor
            )

    summary.saldo_atual = summary.total_receitas - summary.total_gastos
    return summary

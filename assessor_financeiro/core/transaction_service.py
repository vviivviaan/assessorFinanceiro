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


def formatar_reais(valor: float) -> str:
    """Formata um número como moeda brasileira: 1234.5 -> "R$ 1.234,50"."""
    texto = f"{valor:,.2f}"  # ex.: "1,234.50" (formato US)
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


@dataclass
class FinancialSummary:
    total_receitas: float = 0.0
    total_gastos: float = 0.0
    saldo_atual: float = 0.0
    category_totals: dict[str, float] = field(default_factory=dict)

    def _categorias_ordenadas(self) -> list[tuple[str, float]]:
        """Categorias por valor decrescente — destaca as super-categorias primeiro."""
        return sorted(self.category_totals.items(), key=lambda item: item[1], reverse=True)

    @property
    def chart_data(self) -> list[dict]:
        """Formato pronto para alimentar o `rx.recharts.pie_chart` do dashboard."""
        return [
            {
                "name": str(categoria),
                "value": float(round(valor, 2)),
                "fill": PALETA_FINANCEIRA[i % len(PALETA_FINANCEIRA)],
            }
            for i, (categoria, valor) in enumerate(self._categorias_ordenadas())
        ]

    @property
    def category_list_fmt(self) -> list[dict]:
        """Mesma ordem/cores do `chart_data`, mas com o valor já formatado em R$ para exibir em texto."""
        return [
            {**item, "value_fmt": formatar_reais(item["value"])}
            for item in self.chart_data
        ]

    @property
    def saldo_fmt(self) -> str:
        return formatar_reais(self.saldo_atual)

    @property
    def receitas_fmt(self) -> str:
        return formatar_reais(self.total_receitas)

    @property
    def gastos_fmt(self) -> str:
        return formatar_reais(self.total_gastos)

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

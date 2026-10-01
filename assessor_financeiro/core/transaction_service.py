"""Regras de negócio puras para agregação de transações.

Este módulo não importa `reflex` nem toca o banco — recebe uma lista de
transações e devolve os cálculos prontos. Isso o torna fácil de testar
isoladamente (ex.: `pytest`) sem precisar subir o app inteiro.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TypedDict

import pandas as pd

from assessor_financeiro.config import PALETA_FINANCEIRA
from assessor_financeiro.models.db_models import Transaction

CREDITO_ALIASES = {"credito", "crédito"}
DEBITO_ALIASES = {"debito", "débito"}

MESES_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


class ItemTransacao(TypedDict):
    """Uma transação já formatada para exibição na aba de Transações."""

    id: int
    category: str
    type: str
    is_credito: bool
    amount_fmt_signed: str
    created_at_sort: str
    data_iso: str
    mes_iso: str
    hora: str


class GrupoTransacoes(TypedDict):
    """Um bloco de transações do mesmo dia (usado pelo `rx.foreach` aninhado
    da aba de Transações — precisa de um tipo concreto, não `Any`, pra que o
    Reflex consiga iterar `itens` dentro do foreach externo)."""

    data_iso: str
    rotulo: str
    itens: list[ItemTransacao]


class OpcaoMes(TypedDict):
    """Uma opção do seletor de mês (filtro da aba de Transações)."""

    value: str
    label: str


class RelatorioMensal(TypedDict):
    """Um ponto do gráfico de barras Entradas x Saídas (um mês)."""

    mes: str
    Entradas: float
    Saidas: float


def parse_data_flexivel(valor) -> "datetime | None":
    """Converte valores de data heterogêneos (string em formatos variados,
    `datetime.date`, `datetime.datetime`, `Timestamp` do pandas, ou
    vazio/NaN/None) num único `datetime`. Usado por todo caminho de
    importação de transação — chat (agente extrator), upload de arquivo
    (CSV/XLSX/OFX) e Open Finance — pra que a data real da transação vire
    `created_at` de forma padronizada, em vez de cada formato tratar isso
    (ou simplesmente descartar a data) de um jeito diferente.

    Retorna None se não der pra interpretar nada — quem chama decide o que
    fazer (normalmente: deixar o banco usar o padrão dele, a data/hora atual,
    em vez de travar a importação inteira por causa de uma data ruim).
    """
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, date):
        return datetime.combine(valor, datetime.min.time())

    texto = str(valor).strip()
    if not texto or texto.lower() in ("nat", "none", "nan", ""):
        return None

    try:
        convertido = pd.to_datetime(texto, dayfirst=True, errors="coerce")
    except (ValueError, TypeError):
        return None
    if convertido is None or pd.isna(convertido):
        return None
    return convertido.to_pydatetime()


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


def listar_transacoes_detalhadas(transactions: list[Transaction]) -> list[ItemTransacao]:
    """Converte as transações do banco num formato plano, já formatado e ordenado
    (mais recentes primeiro), pronto para a aba de Transações.

    Transações sem `created_at` (não deveria acontecer após a migração, mas por
    segurança) vão para o final da lista, num grupo "Sem data".
    """
    itens = []
    for t in transactions:
        dt = t.created_at
        tem_data = dt is not None
        is_credito = t.type.lower().strip() in CREDITO_ALIASES
        sinal = "+" if is_credito else "-"
        itens.append({
            "id": t.id,
            "category": t.category,
            "type": t.type,
            "is_credito": is_credito,
            "amount_fmt_signed": f"{sinal} {formatar_reais(abs(t.amount))}",
            "created_at_sort": dt.isoformat() if tem_data else "",
            "data_iso": dt.strftime("%Y-%m-%d") if tem_data else "sem-data",
            "mes_iso": dt.strftime("%Y-%m") if tem_data else "sem-data",
            "hora": dt.strftime("%H:%M") if tem_data else "",
        })
    itens.sort(key=lambda item: item["created_at_sort"], reverse=True)
    return itens


def montar_opcoes_de_mes(itens_detalhados: list[ItemTransacao]) -> list[OpcaoMes]:
    """Monta a lista de meses distintos presentes nas transações, mais recente
    primeiro, para alimentar o filtro 'mês' da aba de Transações."""
    meses = sorted(
        {item["mes_iso"] for item in itens_detalhados if item["mes_iso"] != "sem-data"},
        reverse=True,
    )
    opcoes = [{"value": "Todos", "label": "Todos os meses"}]
    for mes_iso in meses:
        ano, mes_num = mes_iso.split("-")
        opcoes.append({"value": mes_iso, "label": f"{MESES_PT[int(mes_num)]}/{ano}"})
    return opcoes


def filtrar_e_agrupar_transacoes(
    itens_detalhados: list[ItemTransacao], tipo: str = "Todas", mes: str = "Todos"
) -> list[GrupoTransacoes]:
    """Aplica os filtros de tipo (Todas/Entradas/Saidas) e mês, e agrupa o
    resultado por dia — cada grupo já vem com um rótulo amigável
    (Hoje/Ontem/dd/mm/aaaa), do mais recente para o mais antigo."""
    filtrados = itens_detalhados
    if tipo == "Entradas":
        filtrados = [i for i in filtrados if i["is_credito"]]
    elif tipo == "Saidas":
        filtrados = [i for i in filtrados if not i["is_credito"]]
    if mes != "Todos":
        filtrados = [i for i in filtrados if i["mes_iso"] == mes]

    hoje = datetime.now().strftime("%Y-%m-%d")
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    grupos: dict[str, GrupoTransacoes] = {}
    ordem: list[str] = []
    for item in filtrados:
        chave = item["data_iso"]
        if chave not in grupos:
            if chave == "sem-data":
                rotulo = "Sem data"
            elif chave == hoje:
                rotulo = "Hoje"
            elif chave == ontem:
                rotulo = "Ontem"
            else:
                ano, mes_num, dia = chave.split("-")
                rotulo = f"{dia}/{mes_num}/{ano}"
            grupos[chave] = {"data_iso": chave, "rotulo": rotulo, "itens": []}
            ordem.append(chave)
        grupos[chave]["itens"].append(item)

    return [grupos[chave] for chave in ordem]


def calcular_relatorio_mensal(transactions: list[Transaction], meses: int = 6) -> list[RelatorioMensal]:
    """Agrega entradas e saídas por mês, para os últimos `meses` meses (incluindo
    meses sem nenhuma transação, pra manter o eixo do gráfico de barras contínuo)."""
    cursor = datetime.now().replace(day=1)
    chaves_mes: list[str] = []
    for _ in range(meses):
        chaves_mes.append(cursor.strftime("%Y-%m"))
        ano, mes_num = cursor.year, cursor.month
        if mes_num == 1:
            cursor = cursor.replace(year=ano - 1, month=12)
        else:
            cursor = cursor.replace(month=mes_num - 1)
    chaves_mes.reverse()  # mais antigo -> mais recente

    totais = {chave: {"Entradas": 0.0, "Saidas": 0.0} for chave in chaves_mes}
    for t in transactions:
        if t.created_at is None:
            continue
        chave = t.created_at.strftime("%Y-%m")
        if chave not in totais:
            continue
        valor = abs(float(t.amount))
        tipo = t.type.lower().strip()
        if tipo in CREDITO_ALIASES:
            totais[chave]["Entradas"] += valor
        elif tipo in DEBITO_ALIASES:
            totais[chave]["Saidas"] += valor

    resultado: list[RelatorioMensal] = []
    for chave in chaves_mes:
        ano, mes_num = chave.split("-")
        resultado.append({
            "mes": f"{MESES_PT[int(mes_num)][:3]}/{ano[2:]}",
            "Entradas": round(totais[chave]["Entradas"], 2),
            "Saidas": round(totais[chave]["Saidas"], 2),
        })
    return resultado


def gerar_insight_textual(transactions: list[Transaction]) -> str:
    """Gera uma frase curta em linguagem natural resumindo os gastos do mês
    atual. Determinístico (não chama LLM), pra carregar instantaneamente
    junto com o resto do dashboard."""
    hoje = datetime.now()
    mes_atual = hoje.strftime("%Y-%m")
    mes_anterior = (hoje.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    gastos_categoria_mes_atual: dict[str, float] = {}
    total_gasto_mes_atual = 0.0
    total_gasto_mes_anterior = 0.0

    for t in transactions:
        if t.created_at is None or t.type.lower().strip() not in DEBITO_ALIASES:
            continue
        valor = abs(float(t.amount))
        chave = t.created_at.strftime("%Y-%m")
        if chave == mes_atual:
            total_gasto_mes_atual += valor
            gastos_categoria_mes_atual[t.category] = (
                gastos_categoria_mes_atual.get(t.category, 0.0) + valor
            )
        elif chave == mes_anterior:
            total_gasto_mes_anterior += valor

    if total_gasto_mes_atual == 0:
        return (
            "Ainda não há gastos registrados este mês — assim que você "
            "registrar algo, o insight aparece aqui."
        )

    categoria_top, valor_top = max(
        gastos_categoria_mes_atual.items(), key=lambda item: item[1]
    )
    percentual_top = (valor_top / total_gasto_mes_atual) * 100

    frase = (
        f"Sua maior categoria de gasto este mês é **{categoria_top}**, "
        f"respondendo por {percentual_top:.0f}% do total gasto "
        f"({formatar_reais(valor_top)} de {formatar_reais(total_gasto_mes_atual)})."
    )

    if total_gasto_mes_anterior > 0:
        variacao = (
            (total_gasto_mes_atual - total_gasto_mes_anterior) / total_gasto_mes_anterior
        ) * 100
        if variacao > 1:
            frase += f" Isso é {variacao:.0f}% a mais do que no mês passado."
        elif variacao < -1:
            frase += f" Isso é {abs(variacao):.0f}% a menos do que no mês passado — parabéns!"
        else:
            frase += " Praticamente igual ao mês passado."

    return frase

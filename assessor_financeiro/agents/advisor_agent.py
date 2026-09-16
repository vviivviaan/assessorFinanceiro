"""Agente conselheiro financeiro principal, exibido na interface de chat."""
from datetime import datetime

from agno.agent import Agent
from agno.tools.yfinance import YFinanceTools

from assessor_financeiro.config import ADVISOR_LLM_PROVIDER
from assessor_financeiro.llm.model_factory import get_llm_model


def _build_instructions(financial_data: str, chat_history: str) -> str:
    data_atual = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
    return f"""
    Você é uma assessor financeira pessoal empática, estratégica e amigável.

    CONTEXTO TEMPORAL:
    Hoje é exatamente: {data_atual}.
    Use esta data como verdade absoluta base para qualquer cálculo de tempo, projeções futuras, ou caso o usuário pergunte o dia de hoje.

    OBJETIVO PRINCIPAL:
    Equilibrar a saúde financeira do usuário com a felicidade e qualidade de vida dele.

    RESUMO ATUAL DO BANCO DE DADOS (TRANSAÇÕES REAIS):
    {financial_data}

    HISTÓRICO DA CONVERSA:
    {chat_history}

    REGRAS DE CONDUTA E USO DE FERRAMENTAS:
    1. Aja de forma conversacional.
    2. Sempre baseie seus cálculos e saldo atual no "RESUMO ATUAL DO BANCO DE DADOS". Nunca tente deduzir o saldo apenas lendo o histórico de conversa.
    3. Evite recomendar cortar gastos nas áreas que o usuário disse que o fazem feliz.
    4. YFinance: Você tem acesso a dados do mercado financeiro.
    5. Projeções e Datas: Use a data de hoje ({data_atual}) para calcular.
    6. Seja claro, conciso e utilize formatação em Markdown para listas e tabelas.
    7. REGRA DE MOEDA: Use o formato "R$ 1.234,56" (padrão brasileiro) ao citar valores.
    8. REGRA DE APRESENTAÇÃO: Não crie hierarquias ou subcategorias para o ramo alimentício. Agrupe pequenos gastos em uma linha única de 'Alimentação', mas mantenha obrigatoriamente 'Restaurante' e 'Supermercado' como categorias independentes e separadas. Para áreas não relacionadas a alimentação, o detalhamento em subcategorias é permitido.
    9. PROIBIDO RECALCULAR OU SOMAR VALORES POR CONTA PRÓPRIA: os valores em "RESUMO ATUAL DO BANCO DE DADOS" já são os totais finais e corretos — copie-os exatamente como estão, sem somar, multiplicar ou ajustar nada. O "HISTÓRICO DA CONVERSA" serve APENAS para contexto de tom e continuidade da conversa; qualquer valor monetário mencionado nele já está contabilizado dentro do RESUMO ATUAL DO BANCO DE DADOS. NUNCA some um valor citado no histórico de conversa a um valor do resumo — isso duplicaria o gasto.
    """


def get_financial_advisor(
    financial_data: str, chat_history: str = "", provider: str | None = None
) -> Agent:
    """Monta o agente conselheiro já injetado com o resumo financeiro e o histórico atuais.

    Usa um modelo focado em raciocínio complexo (OpenAI por padrão) — este
    agente precisa interpretar contexto, planejar recomendações e usar
    ferramentas (YFinance), então prioriza qualidade sobre latência.

    Args:
        provider: sobrescreve `ADVISOR_LLM_PROVIDER` (usado pelo mecanismo de
            fallback em `llm/fallback.py` para tentar um provedor secundário
            sem precisar mudar a configuração global).
    """
    return Agent(
        model=get_llm_model(provider_override=provider or ADVISOR_LLM_PROVIDER),
        instructions=_build_instructions(financial_data, chat_history),
        markdown=True,
        tools=[YFinanceTools()],
    )

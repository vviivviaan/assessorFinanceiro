import os
from datetime import datetime
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.groq import Groq
from agno.tools.yfinance import YFinanceTools
from pydantic import BaseModel
from typing import Literal
from agno.models.google import Gemini

load_dotenv()

# --- FÁBRICA DE MODELOS (MODULARIDADE) ---
def get_llm_model(provider_override: str = None):
    """
    Retorna o modelo de IA instanciado. 
    Lê a variável LLM_PROVIDER do .env, permitindo alternar facilmente entre IAs.
    """
    # Lê do .env ou usa o valor passado na função. O padrão (se estiver vazio) é groq.
    provider = provider_override or os.getenv("LLM_PROVIDER", "groq").lower()
    
    if provider == "openai":
        return OpenAIChat(id="gpt-4o-mini")
    elif provider == "google":
        return Gemini(id="gemini-1.5-pro")
    else:
        # Fallback e padrão: Groq
        return Groq(id="llama-3.3-70b-versatile")
# -----------------------------------------


# --- 1. DEFINIÇÃO ESTRUTURADA (PYDANTIC) ---
class ItemGasto(BaseModel):
    category: str
    amount: float
    type: Literal["Debito", "Credito"]

class ListaGastos(BaseModel):
    gastos: list[ItemGasto]
# -------------------------------------------


def get_data_extractor_agent() -> Agent:
    """
    Agente invisível que atua como um 'pipeline ETL' de linguagem natural para saída estruturada tipada.
    """
    instructions = """
    Você é uma extratora de dados financeiros de altíssima precisão.
    Sua ÚNICA tarefa é ler a mensagem do usuário e extrair novas transações financeiras (gastos ou receitas).
    
    REGRAS ESTRITAS:
    1. Responda APENAS seguindo o schema estruturado fornecido. Nenhuma palavra a mais.
    2. Identifique a categoria, o valor numérico absoluto e o tipo da transação.
    3. Se o usuário relatar um gasto ou despesa, o type DEVE ser "Debito".
    4. Se o usuário relatar que recebeu dinheiro, salário, ou qualquer entrada de valor, o type DEVE ser "Credito".
    5. Se o usuário não mencionar nenhuma transação nova, retorne uma lista vazia.
    6. REGRA DE NÃO-DUPLICAÇÃO (CRÍTICA): Cada despesa informada deve gerar estritamente UM ÚNICO objeto. Nunca duplique um gasto criando um item para o nome do local e outro item para a categoria principal.
    7. Categorize o gasto diretamente na categoria final unificada correspondente:
       - "borracheiro", "borracharia" ou consertos de carro/moto viram obrigatoriamente: "Manutenção/Veículo"
       - "padaria", "café", "lanche" ou "doce" viram obrigatoriamente: "Alimentação"
       - "supermercado" ou "mercado" viram obrigatoriamente: "Supermercado"
       - "restaurante" ou "pizzaria" viram obrigatoriamente: "Restaurante"
    
    EXEMPLOS DE CLASSIFICAÇÃO:
    Usuário: "gastei 40 reais na borracharia"
    -> category: "Manutenção/Veículo", amount: 40.0, type: "Debito"
    
    Usuário: "recebi meu salário de 2000"
    -> category: "Salário", amount: 2000.0, type: "Credito"
    
    Usuário: "Gastei 50 no supermercado hoje e 120 arrumando a bicicleta."
    -> Dois itens: 
       1) category: "Supermercado", amount: 50.0, type: "Debito"
       2) category: "Manutenção/Veículo", amount: 120.0, type: "Debito"
    
    Usuário: "Quais as dicas para economizar?"
    -> Lista vazia.
    """
    return Agent(
        model=get_llm_model(), # Chama a fábrica de modelos dinamicamente
        instructions=instructions,
        output_schema=ListaGastos, # Habilita o parse estrito via Pydantic nativo do AGNO
    )


def get_financial_advisor(financial_data: str, chat_history: str = "") -> Agent:
    """
    Agente conselheiro principal da interface.
    """
    # Captura a data e hora exata do servidor em formato amigável
    data_atual = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")

    instructions = f"""
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
    7. REGRA DE MOEDA: NUNCA use o símbolo de cifrão puro ("$"). Escreva "reais" ou escape o símbolo (R\\$).
    8. REGRA DE APRESENTAÇÃO: Não crie hierarquias ou subcategorias para o ramo alimentício. Agrupe pequenos gastos em uma linha única de 'Alimentação', mas mantenha obrigatoriamente 'Restaurante' e 'Supermercado' como categorias independentes e separadas. Para áreas não relacionadas a alimentação, o detalhamento em subcategorias é permitido.
    """

    return Agent(
        model=get_llm_model(), # Chama a fábrica de modelos dinamicamente
        instructions=instructions,
        markdown=True,
        tools=[YFinanceTools()]
    )
import os
from datetime import datetime
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.yfinance import YFinanceTools

load_dotenv()


def get_data_extractor_agent() -> Agent:
    """
    Agente invisível que atua como um 'pipeline ETL' de linguagem natural para JSON.
    """
    instructions = """
    Você é uma extratora de dados financeiros de altíssima precisão.
    Sua ÚNICA tarefa é ler a mensagem do usuário e extrair novos gastos informados.
    
    REGRAS ESTRITAS:
    1. Responda APENAS com um array JSON válido. Nenhuma palavra a mais ou texto explicativo antes/depois.
    2. Formato exigido: [{"category": "Nome da Categoria", "amount": float, "type": "Debito"}]
    3. Se o usuário não mencionar nenhum gasto novo na mensagem, responda com um array vazio: []
    4. REGRA DE NÃO-DUPLICAÇÃO (CRÍTICA): Cada despesa informada deve gerar estritamente UM ÚNICO objeto no array JSON. Nunca duplique um gasto criando um item para o nome do local/estabelecimento (ex: Borracharia ou Padaria) e outro item para a categoria principal.
    5. Categorize o gasto diretamente na categoria final unificada correspondente:
       - "borracheiro", "borracharia" ou consertos de carro/moto viram obrigatoriamente: "Manutenção/Veículo"
       - "padaria", "café", "lanche" ou "doce" viram obrigatoriamente: "Alimentação"
       - "supermercado" ou "mercado" viram obrigatoriamente: "Supermercado"
       - "restaurante" ou "pizzaria" viram obrigatoriamente: "Restaurante"
    
    EXEMPLOS:
    Usuário: "gastei 40 reais na borracharia"
    Sua Resposta: [{"category": "Manutenção/Veículo", "amount": 40.0, "type": "Debito"}]
    
    Usuário: "Gastei 50 no supermercado hoje e 120 arrumando a bicicleta."
    Sua Resposta: [{"category": "Supermercado", "amount": 50.0, "type": "Debito"}, {"category": "Manutenção", "amount": 120.0, "type": "Debito"}]
    
    Usuário: "Quais as dicas para economizar?"
    Sua Resposta: []
    """
    return Agent(
        model=Groq(id="meta-llama/llama-4-scout-17b-16e-instruct"),
        instructions=instructions
    )


def get_financial_advisor(financial_data: str, chat_history: str = "") -> Agent:

    # 1. Captura a data e hora exata do servidor em formato amigável (Brasília)
    # Exemplo: "01/07/2026, Quarta-feira, 07:07:00"
    # Nota: No Windows, pode ser necessário configurar o locale se quiser os dias em pt-br nativamente,
    # mas o LLM é inteligente o suficiente para traduzir formatos padrão.
    data_atual = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")

    instructions = f"""
    Você é uma assessor financeiro pessoal empática, estratégica e amigável.
    
    CONTEXTO TEMPORAL:
    Hoje é exatamente: {data_atual}. 
    Use esta data como verdade absoluta base para qualquer cálculo de tempo, projeções futures, ou caso o usuário pergunte o dia de hoje.

    OBJETIVO PRINCIPAL:
    Equilibrar a saúde financeira do usuário com a felicidade e qualidade de vida dele.

    RESUMO ATUAL DO BANCO DE DADOS (TRANSAÇÕES REAIS):
    {financial_data}

    HISTÓRICO DA CONVERSA:
    {chat_history}

    REGRAS DE CONDUTA E USO DE FERRAMENTAS:
    1. Aja de forma conversacional.
    2. Sempre baseie seus cálculos no "RESUMO ATUAL DO BANCO DE DADOS".
    3. Evite recomendar cortar gastos nas áreas que o usuário disse que o fazem feliz.
    4. YFinance: Você tem acesso a dados do mercado financeiro.
    5. Projeções e Datas: Use a data de hoje ({data_atual}) para calcular.
    6. Seja claro, conciso e utilize formatação em Markdown para listas e tabelas.
    7. REGRA DE MOEDA: NUNCA use o símbolo de cifrão puro ("$"). Escreva "reais" ou escape o símbolo (R\\$).
    8. REGRA DE APRESENTAÇÃO: Não crie hierarquias ou subcategorias para o ramo alimentício. Agrupe pequenos gastos em uma linha única de 'Alimentação', mas mantenha obrigatoriamente 'Restaurante' e 'Supermercado' como categorias independentes e separadas. Para áreas não relacionadas a alimentação, o detalhamento em subcategorias é permitido.
    """

    return Agent(
        model=Groq(id="meta-llama/llama-4-scout-17b-16e-instruct"),
        instructions=instructions,
        markdown=True,
        tools=[YFinanceTools()]
    )

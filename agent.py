import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.groq import Groq

# Carrega as variáveis do .env (protegendo a API Key)
load_dotenv()

def get_financial_advisor(lifestyle_context: str, financial_data: str) -> Agent:
    """
    Instancia o agente AGNO com o contexto do usuário.
    """
    instructions = f"""
    Você é um assessor financeiro pessoal empático, estratégico e amigável.
    Seu objetivo é equilibrar a saúde financeira do usuário com a felicidade e qualidade de vida dele.

    ESTILO DE VIDA E HOBBIES DO USUÁRIO:
    {lifestyle_context if lifestyle_context else 'Não informado ainda.'}

    DADOS FINANCEIROS (MÊS ATUAL):
    {financial_data if financial_data else 'Não informado ainda.'}

    REGRAS DE CONDUTA:
    1. Analise os gastos, categorize as despesas e identifique padrões (ex: assinaturas esquecidas).
    2. Sugira metas realistas de economia.
    3. NUNCA recomende cortar gastos que são essenciais para o bem-estar e hobbies descritos no "Estilo de Vida". Otimize outras áreas para manter o usuário feliz.
    4. Seja claro e utilize formatação em Markdown para listas e tabelas.
    """

    return Agent(
        # Llama 3 (via Groq) é excelente para raciocínio rápido
        model=Groq(id="llama3-70b-8192"),
        instructions=instructions,
        #show_tool_calls=True, # Fundamental para a avaliação dos reasoning traces exigida no projeto 
        markdown=True
    )
"""Configurações centrais do projeto: variáveis de ambiente e constantes.

Mantendo tudo isso em um único lugar, qualquer ajuste de "modo padrão"
(provedor de LLM, sessão default, cores do gráfico) é feito em um só arquivo,
sem precisar caçar valores espalhados pelo código.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Sessão ---
# Hoje o app trata todo mundo como um único usuário fixo. Se no futuro vocês
# quiserem multiusuário de verdade, esse é o único ponto que precisa mudar
# (por exemplo, gerando um session_id por login).
DEFAULT_SESSION_ID = "default_user"

# --- Provedor de LLM ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

GROQ_MODEL_ID = "openai/gpt-oss-120b"
OPENAI_MODEL_ID = "gpt-4o-mini"
GOOGLE_MODEL_ID = "gemini-1.5-pro"

# --- Dashboard ---
# Paleta usada para colorir as fatias do gráfico de pizza, na ordem em que as
# categorias aparecem.
PALETA_FINANCEIRA = [
    "#3b82f6",  # Azul Royal
    "#10b981",  # Verde Esmeralda (Principal)
    "#ef4444",  # Vermelho Alerta
    "#f97316",  # Laranja Vívido
    "#14b8a6",  # Teal
    "#8b5cf6",  # Roxo Violeta
    "#f59e0b",  # Âmbar
    "#06b6d4",  # Ciano
    "#a855f7",  # Púrpura
]

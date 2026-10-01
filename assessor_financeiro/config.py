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

# --- Modo de uso (Fase 7 — Pessoal x Assessor Financeiro multiempresa) ---
MODO_PESSOAL = "pessoal"
MODO_MULTIEMPRESA = "multiempresa"

# --- Provedor de LLM ---
# Roteamento inteligente: cada agente usa o provedor mais adequado ao seu
# trabalho por padrão (Groq é rápido/barato, ideal para o parsing do
# extrator; OpenAI raciocina melhor, ideal para o conselho financeiro).
# Qualquer um dos dois pode ser sobrescrito via .env sem tocar no código.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
EXTRACTOR_LLM_PROVIDER = os.getenv("EXTRACTOR_LLM_PROVIDER", "groq").lower()
ADVISOR_LLM_PROVIDER = os.getenv("ADVISOR_LLM_PROVIDER", "openai").lower()

GROQ_MODEL_ID = "openai/gpt-oss-120b"
OPENAI_MODEL_ID = "gpt-4o-mini"
GOOGLE_MODEL_ID = "gemini-1.5-pro"

# --- Chaves de API ---
# Cada provedor suportado tem sua chave em uma variável de ambiente própria
# (nunca hardcoded aqui). Isso permite ter as três configuradas ao mesmo
# tempo no .env e alternar entre elas só trocando LLM_PROVIDER /
# EXTRACTOR_LLM_PROVIDER / ADVISOR_LLM_PROVIDER, sem editar código.
API_KEY_ENV_VARS = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def validate_llm_api_keys() -> None:
    """Falha cedo e com mensagem clara se faltar chave de algum provedor em uso.

    Sem isso, um provedor mal configurado só quebraria bem mais tarde, no
    meio de uma chamada de agente, com um erro genérico do SDK dele.
    """
    provedores_em_uso = {LLM_PROVIDER, EXTRACTOR_LLM_PROVIDER, ADVISOR_LLM_PROVIDER}
    variaveis_faltando = sorted({
        API_KEY_ENV_VARS[provider]
        for provider in provedores_em_uso
        if provider in API_KEY_ENV_VARS and not os.getenv(API_KEY_ENV_VARS[provider])
    })

    if variaveis_faltando:
        msg = (
            "Configuração de API incompleta: defina "
            f"{', '.join(variaveis_faltando)} no arquivo .env antes de rodar o app."
        )
        raise RuntimeError(msg)


validate_llm_api_keys()

# --- Dashboard ---
# Paleta usada para colorir as fatias do gráfico de pizza, na ordem em que as
# categorias aparecem.
PALETA_FINANCEIRA = [
    "#142a5c",  # Navy (categoria principal — mesma cor do header)
    "#3b82f6",  # Azul Royal
    "#14b8a6",  # Teal
    "#8b5cf6",  # Roxo Violeta
    "#eab308",  # Âmbar
    "#9ca3af",  # Cinza (Outros)
    "#ef4444",  # Vermelho Alerta
    "#f97316",  # Laranja Vívido
    "#06b6d4",  # Ciano
]

# --- Tokens visuais (Fase 7 — Redesign + responsivo) ---
# Paleta/medidas inspiradas no mockup de referência (header navy, cards
# brancos arredondados, chips/pills). Um único lugar pra trocar o "tema"
# inteiro do app sem caçar cor espalhada pelos componentes.
COR_NAVY = "#142a5c"
COR_NAVY_ESCURO = "#0e1f47"
COR_NAVY_SUAVE = "#e8ecf7"  # fundo do chip/indicador ativo sobre branco
COR_FUNDO_APP = "#f2f4fa"
COR_VERDE = "#16a34a"
COR_VERDE_BG = "#e3f8ea"
COR_VERMELHO = "#e0483a"
COR_VERMELHO_BG = "#fdeceb"
COR_ALERTA = "#c2650b"
COR_ALERTA_BG = "#fdecd3"
RAIO_CARD = "20px"
SOMBRA_CARD = "0 4px 16px rgba(15, 32, 72, 0.08)"

"""Categorização automática de transações importadas (extratos e faturas).

Regras por palavra-chave, determinísticas (sem LLM, sem custo, resultado
sempre igual). As categorias seguem as mesmas que o agente extrator usa no
chat, pra o gráfico por categoria juntar tudo no mesmo lugar. Descrição que
não bate com nenhuma regra mantém o próprio texto como categoria (o mesmo
comportamento de antes) — assim nada é perdido nem classificado errado.

Pra ensinar uma palavra nova, basta acrescentá-la em `REGRAS`.
"""
import re
import unicodedata

# categoria -> palavras-chave (sem acento, minúsculas). Casa por PALAVRA
# INTEIRA (assim "luz" não pega "Luzia"); com "*" no fim casa por começo de
# palavra ("farmac*" pega "farmácia", "farmacias"...).
REGRAS: dict[str, tuple[str, ...]] = {
    # Ordem importa: as mais específicas primeiro ("Mercado Livre" é Compras, não Supermercado).
    "Assinaturas": ("netflix", "spotify", "disney", "hbo", "max.com", "prime video", "amazon prime", "youtube premium", "deezer", "globoplay", "icloud", "google one"),
    "Compras": ("amazon", "mercado livre", "shopee", "magalu", "americanas", "shein", "aliexpress", "renner", "riachuelo", "c&a"),
    "Salário": ("salario", "folha de pagamento", "pro labore", "proventos"),
    "Supermercado": ("supermercado", "mercado", "atacadao", "assai", "carrefour", "extrabom", "hortifruti", "sacolao"),
    "Restaurante": ("restaurante", "pizzaria", "churrascaria", "lanchonete", "burger", "mcdonald", "outback"),
    "Alimentação": ("padaria", "cafe", "cafeteria", "lanche", "doceria", "sorveteria", "ifood", "rappi", "acai"),
    "Transporte": ("uber", "99app", "99 pop", "cabify", "onibus", "metro", "passagem", "pedagio", "estacionamento", "sem parar"),
    "Combustível": ("posto", "combustivel", "gasolina", "etanol", "shell", "ipiranga"),
    "Manutenção/Veículo": ("borracharia", "borracheiro", "mecanica", "oficina", "funilaria", "auto pecas", "lava jato"),
    "Saúde": ("farmac*", "drogaria", "drogasil", "raia", "pague menos", "hospital", "clinica", "laboratorio", "consulta", "plano de saude", "unimed", "odonto", "dentista"),
    "Educação": ("escola", "faculdade", "universidade", "curso", "udemy", "alura", "livraria", "mensalidade escolar", "ifes"),
    "Moradia": ("aluguel", "condominio", "iptu", "luz", "energia", "escelsa", "edp", "agua", "cesan", "internet", "vivo fibra", "claro", "tim ", "oi fibra", "gas "),
    "Lazer": ("cinema", "teatro", "show", "ingresso", "steam", "playstation", "xbox", "parque", "viagem", "hotel", "airbnb", "booking"),
    "Academia": ("academia", "smartfit", "smart fit", "bluefit"),
    "Taxas": ("tarifa", "anuidade", "iof", "juros", "multa", "encargos"),
}

CATEGORIA_FALLBACK = None  # sem regra: quem chama decide (mantém a descrição)


def _compilar(palavra: str) -> "re.Pattern[str]":
    prefixo = palavra.endswith("*")
    base = re.escape(_normalizar(palavra))
    return re.compile(rf" {base}" if prefixo else rf" {base} ")


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    # tudo que não é letra/número vira espaço: "NETFLIX.COM" -> "netflix com"
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


_REGRAS_COMPILADAS = [
    (categoria, [_compilar(p) for p in palavras]) for categoria, palavras in REGRAS.items()
]


def categorizar(descricao: str) -> str | None:
    """Categoria da descrição, ou None se nenhuma regra bater."""
    texto = f" {_normalizar(descricao or '')} "
    for categoria, padroes in _REGRAS_COMPILADAS:
        if any(padrao.search(texto) for padrao in padroes):
            return categoria
    return CATEGORIA_FALLBACK


def categoria_ou_descricao(descricao: str) -> str:
    """Categoria encontrada ou, sem regra, a própria descrição limpa."""
    return categorizar(descricao) or (descricao or "").strip() or "Sem descrição"

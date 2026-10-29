"""Regras de negócio de login e de chaves de API por usuário.

Não importa Reflex: usa `transaction_repository` (acesso ao banco) e
`security` (hash/criptografia). `state.py` só chama estas funções.
"""
import datetime
import re
import threading
import time

from assessor_financeiro.core import security
from assessor_financeiro.core import transaction_repository as repo
from assessor_financeiro.config import DEFAULT_SESSION_ID

PROVEDORES = {"groq": "Groq", "openai": "OpenAI", "google": "Google (Gemini)"}
SENHA_MIN = 8
VALIDADE_SESSAO_DIAS = 30
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# Limite de tentativas de login por e-mail (proteção contra adivinhar senha).
# Fica em memória: vale para uma instância do servidor, o que basta para um
# app pequeno; com várias instâncias, trocar por um contador no banco/Redis.
MAX_TENTATIVAS = 5
JANELA_BLOQUEIO_SEG = 15 * 60
_falhas: dict[str, list[float]] = {}
_trava = threading.Lock()


def _tentativas_recentes(chave: str, agora: float) -> list[float]:
    recentes = [t for t in _falhas.get(chave, []) if agora - t < JANELA_BLOQUEIO_SEG]
    _falhas[chave] = recentes
    return recentes


def _limpar_falhas() -> None:
    """Usado nos testes."""
    with _trava:
        _falhas.clear()


class ErroAutenticacao(Exception):
    """Mensagem já pronta para mostrar à usuária."""


def session_id_pessoal(usuario_id: int) -> str:
    """Perfil 'Pessoal' de cada usuário: isola chat, transações e conversas."""
    return f"usuario_{usuario_id}"


def normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


def registrar(email: str, senha: str):
    email = normalizar_email(email)
    if not _EMAIL_RE.match(email):
        raise ErroAutenticacao("Informe um e-mail válido.")
    if len(senha or "") < SENHA_MIN:
        raise ErroAutenticacao(f"A senha precisa ter pelo menos {SENHA_MIN} caracteres.")
    if repo.get_usuario_por_email(email) is not None:
        raise ErroAutenticacao("Já existe uma conta com esse e-mail.")

    primeiro_usuario = repo.count_usuarios() == 0
    usuario = repo.create_usuario(email, security.hash_senha(senha))
    if primeiro_usuario:
        # Tudo que existia antes do login (perfil único "default_user" e
        # clientes sem dono) passa a ser dela.
        repo.adotar_dados_legados(
            usuario.id, DEFAULT_SESSION_ID, session_id_pessoal(usuario.id)
        )
    return usuario


def autenticar(email: str, senha: str):
    email = normalizar_email(email)
    agora = time.time()
    with _trava:
        if len(_tentativas_recentes(email, agora)) >= MAX_TENTATIVAS:
            raise ErroAutenticacao(
                "Muitas tentativas de login. Aguarde 15 minutos e tente de novo."
            )

    usuario = repo.get_usuario_por_email(email)
    # Mesma mensagem para e-mail inexistente e senha errada (não revela quais e-mails existem).
    if usuario is None or not security.verificar_senha(senha or "", usuario.senha_hash):
        with _trava:
            _falhas.setdefault(email, []).append(agora)
        raise ErroAutenticacao("E-mail ou senha incorretos.")

    with _trava:
        _falhas.pop(email, None)
    return usuario


def criar_sessao(usuario_id: int) -> str:
    """Cria um login persistente e devolve o token (guardado no navegador)."""
    token = security.gerar_token()
    expira = datetime.datetime.now() + datetime.timedelta(days=VALIDADE_SESSAO_DIAS)
    repo.create_sessao(usuario_id, security.hash_token(token), expira)
    return token


def usuario_da_sessao(token: str):
    """Usuário dono do token, ou None se não existir / estiver expirado."""
    if not token:
        return None
    hash_token = security.hash_token(token)
    sessao = repo.get_sessao(hash_token)
    if sessao is None:
        return None
    if sessao.expira_em < datetime.datetime.now():
        repo.delete_sessao(hash_token)
        return None
    return repo.get_usuario(sessao.usuario_id)


def encerrar_sessao(token: str) -> None:
    if token:
        repo.delete_sessao(security.hash_token(token))


# --- Chaves de API ---


def salvar_chave(usuario_id: int, provedor: str, chave: str) -> None:
    if provedor not in PROVEDORES:
        raise ErroAutenticacao("Provedor desconhecido.")
    chave = (chave or "").strip()
    if len(chave) < 8:
        raise ErroAutenticacao("Essa chave parece curta demais. Confira e cole de novo.")
    repo.upsert_chave_api(usuario_id, provedor, security.cifrar(chave))


def remover_chave(usuario_id: int, provedor: str) -> None:
    repo.delete_chave_api(usuario_id, provedor)


def chaves_decifradas(usuario_id: int) -> dict[str, str]:
    """{"groq": "...", ...} — só para uso interno, a caminho do provedor de LLM.
    NUNCA colocar isso numa variável de estado (o Reflex envia o estado ao navegador)."""
    resultado = {}
    for registro in repo.list_chaves_api(usuario_id):
        chave = security.decifrar(registro.chave_cifrada)
        if chave:
            resultado[registro.provedor] = chave
    return resultado


def chaves_mascaradas(usuario_id: int) -> list[dict[str, str]]:
    """Uma linha por provedor, com a chave mascarada ('••••1a2b') — pode ir para a tela."""
    salvas = chaves_decifradas(usuario_id)
    return [
        {
            "provedor": codigo,
            "nome": nome,
            "salva": "sim" if codigo in salvas else "nao",
            "mascara": f"••••{salvas[codigo][-4:]}" if codigo in salvas else "",
        }
        for codigo, nome in PROVEDORES.items()
    ]

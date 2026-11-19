"""Regras de negócio de login e de chaves de API por usuário.

Não importa Reflex: usa `transaction_repository` (acesso ao banco) e
`security` (hash/criptografia). `state.py` só chama estas funções.
"""
import datetime
import re
import threading
import time

from assessor_financeiro.core import email_service, security
from assessor_financeiro.core import transaction_repository as repo
from assessor_financeiro.config import DEFAULT_SESSION_ID

# A ordem aqui é a ordem em que os provedores aparecem na tela de Configurações.
# "anthropic" (Claude) é opcional: melhora a qualidade do conselheiro, mas o app
# funciona sem ele desde que haja pelo menos uma das outras chaves.
PROVEDORES = {
    "groq": "Groq",
    "openai": "OpenAI",
    "google": "Google (Gemini)",
    "anthropic": "Claude (Anthropic)",
}
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

# Pedidos de código de redefinição por e-mail (evita usar o app para disparar spam).
MAX_PEDIDOS_CODIGO = 3
_pedidos_codigo: dict[str, list[float]] = {}


def _tentativas_recentes(chave: str, agora: float) -> list[float]:
    recentes = [t for t in _falhas.get(chave, []) if agora - t < JANELA_BLOQUEIO_SEG]
    _falhas[chave] = recentes
    return recentes


def _limpar_falhas() -> None:
    """Usado nos testes."""
    with _trava:
        _falhas.clear()
        _pedidos_codigo.clear()


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


def _validar_senha_nova(senha: str) -> None:
    if len(senha or "") < SENHA_MIN:
        raise ErroAutenticacao(f"A senha precisa ter pelo menos {SENHA_MIN} caracteres.")


def _bloqueado(chave: str) -> bool:
    with _trava:
        return len(_tentativas_recentes(chave, time.time())) >= MAX_TENTATIVAS


def _registrar_falha(chave: str) -> None:
    with _trava:
        _falhas.setdefault(chave, []).append(time.time())


# --- Esqueci minha senha / alterar senha ---

MSG_MUITAS_TENTATIVAS = "Muitas tentativas. Aguarde 15 minutos e tente de novo."


def recuperacao_disponivel() -> bool:
    """False quando o servidor não tem serviço de e-mail configurado."""
    return email_service.configurado()


def solicitar_redefinicao(email: str) -> None:
    """Envia o código de redefinição por e-mail. Se o e-mail não tem conta, não faz
    nada e não avisa (não revela quais e-mails existem)."""
    email = normalizar_email(email)
    if not _EMAIL_RE.match(email):
        raise ErroAutenticacao("Informe um e-mail válido.")
    if not email_service.configurado():
        raise ErroAutenticacao(
            "A recuperação por e-mail não está configurada neste servidor. "
            "Peça ajuda a quem administra o app."
        )

    agora = time.time()
    with _trava:
        recentes = [t for t in _pedidos_codigo.get(email, []) if agora - t < JANELA_BLOQUEIO_SEG]
        if len(recentes) >= MAX_PEDIDOS_CODIGO:
            _pedidos_codigo[email] = recentes
            raise ErroAutenticacao(MSG_MUITAS_TENTATIVAS)
        recentes.append(agora)
        _pedidos_codigo[email] = recentes

    usuario = repo.get_usuario_por_email(email)
    if usuario is None:
        return
    codigo = security.codigo_redefinicao(email, usuario.senha_hash)
    texto = (
        "Olá!\n\n"
        "Recebemos um pedido para redefinir a senha da sua conta na vivIA.\n\n"
        f"Seu código: {codigo[:4]}-{codigo[4:]}\n\n"
        "Ele vale por até 30 minutos e só pode ser usado uma vez. "
        "Se não foi você, ignore este e-mail: sua senha continua a mesma."
    )
    try:
        email_service.enviar(email, "vivIA — código para redefinir sua senha", texto)
    except email_service.ErroEnvioEmail as erro:
        raise ErroAutenticacao(
            "Não foi possível enviar o e-mail agora. Tente de novo em instantes."
        ) from erro


def redefinir_senha(email: str, codigo: str, senha_nova: str) -> None:
    """Troca a senha usando o código recebido por e-mail e encerra os logins antigos."""
    email = normalizar_email(email)
    chave = f"redefinir:{email}"
    if _bloqueado(chave):
        raise ErroAutenticacao(MSG_MUITAS_TENTATIVAS)
    _validar_senha_nova(senha_nova)

    usuario = repo.get_usuario_por_email(email)
    if usuario is None or not security.codigo_redefinicao_valido(
        email, usuario.senha_hash, codigo
    ):
        _registrar_falha(chave)
        raise ErroAutenticacao("Código inválido ou expirado.")

    repo.atualizar_senha(usuario.id, security.hash_senha(senha_nova))
    repo.delete_sessoes_do_usuario(usuario.id)
    with _trava:
        _falhas.pop(chave, None)
        _falhas.pop(email, None)  # libera também o bloqueio de login, se houver


def alterar_senha(usuario_id: int, senha_atual: str, senha_nova: str) -> None:
    """Troca de senha de quem já está logado (exige a senha atual)."""
    chave = f"alterar:{usuario_id}"
    if _bloqueado(chave):
        raise ErroAutenticacao(MSG_MUITAS_TENTATIVAS)
    usuario = repo.get_usuario(usuario_id)
    if usuario is None:
        raise ErroAutenticacao("Faça login de novo.")
    if not security.verificar_senha(senha_atual or "", usuario.senha_hash):
        _registrar_falha(chave)
        raise ErroAutenticacao("A senha atual está incorreta.")
    _validar_senha_nova(senha_nova)
    if senha_nova == senha_atual:
        raise ErroAutenticacao("A nova senha precisa ser diferente da atual.")
    repo.atualizar_senha(usuario.id, security.hash_senha(senha_nova))
    with _trava:
        _falhas.pop(chave, None)


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

"""Primitivas de segurança: hash de senha, tokens de sessão e criptografia das chaves de API.

Módulo puro (não importa Reflex nem toca o banco), então é fácil de testar.

- Senhas: scrypt (da biblioteca padrão) com salt aleatório. Nunca guardamos a senha.
- Token de login: valor aleatório; no banco só fica o SHA-256 dele, então um
  vazamento do banco não entrega logins válidos.
- Chaves de API dos provedores: precisam ser recuperadas em texto para chamar
  o provedor, então são CRIPTOGRAFADAS (Fernet/AES) com uma chave mestra que
  fica fora do banco: variável de ambiente `VIVIA_SECRET_KEY` ou, se não
  existir, um arquivo local (`VIVIA_SECRET_FILE`, padrão `.vivia_secret_key`),
  criado automaticamente na primeira execução. Quem tiver só o banco não lê
  as chaves; quem perder a chave mestra precisa cadastrar as chaves de novo.
"""
import hashlib
import hmac
import os
import secrets
import time
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_senha(senha: str) -> str:
    salt = secrets.token_bytes(16)
    derivado = hashlib.scrypt(
        senha.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${derivado.hex()}"


def verificar_senha(senha: str, hash_guardado: str) -> bool:
    try:
        algoritmo, n, r, p, salt_hex, hash_hex = hash_guardado.split("$")
        if algoritmo != "scrypt":
            return False
        derivado = hashlib.scrypt(
            senha.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
        )
        return hmac.compare_digest(derivado, bytes.fromhex(hash_hex))
    except (ValueError, TypeError):
        return False


def gerar_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _chave_mestra() -> bytes:
    chave_env = os.getenv("VIVIA_SECRET_KEY")
    if chave_env:
        return chave_env.encode("utf-8")

    caminho = Path(os.getenv("VIVIA_SECRET_FILE", ".vivia_secret_key"))
    if caminho.exists():
        return caminho.read_bytes().strip()

    chave = Fernet.generate_key()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(chave)
    try:
        caminho.chmod(0o600)
    except OSError:  # Windows pode não suportar chmod; o arquivo continua local
        pass
    return chave


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(_chave_mestra())


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode("utf-8")).decode("utf-8")


def decifrar(cifrado: str) -> str | None:
    """Devolve o texto original ou None se a chave mestra mudou / o dado foi corrompido."""
    try:
        return _fernet().decrypt(cifrado.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def limpar_cache_chave_mestra() -> None:
    """Usado nos testes, para trocar a chave mestra entre um teste e outro."""
    _chave_mestra.cache_clear()
    _fernet.cache_clear()


# --- Código de redefinição de senha ---
#
# Sem tabela nova: o código é calculado (HMAC) a partir da chave mestra, do e-mail,
# do hash da senha ATUAL e de uma janela de 15 minutos. Por isso ele:
#   - expira sozinho (vale na janela em que foi gerado e na seguinte: 15 a 30 min);
#   - deixa de valer assim que a senha muda (o hash muda), então só serve uma vez;
#   - não pode ser calculado por quem tem só o banco (falta a chave mestra).
JANELA_CODIGO_SEG = 15 * 60
_ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 32 símbolos, sem I/O/0/1


def _codigo_da_janela(email: str, senha_hash: str, janela: int) -> str:
    mensagem = f"{email}|{senha_hash}|{janela}".encode("utf-8")
    mac = hmac.new(_chave_mestra(), mensagem, hashlib.sha256).digest()
    numero = int.from_bytes(mac[:5], "big")  # 40 bits = 8 símbolos de 5 bits
    return "".join(_ALFABETO_CODIGO[(numero >> (5 * i)) & 31] for i in range(8))


def codigo_redefinicao(email: str, senha_hash: str, agora: float | None = None) -> str:
    janela = int((time.time() if agora is None else agora) // JANELA_CODIGO_SEG)
    return _codigo_da_janela(email, senha_hash, janela)


def codigo_redefinicao_valido(
    email: str, senha_hash: str, codigo: str, agora: float | None = None
) -> bool:
    informado = (codigo or "").upper().replace("-", "").replace(" ", "")
    janela = int((time.time() if agora is None else agora) // JANELA_CODIGO_SEG)
    return any(
        hmac.compare_digest(informado, _codigo_da_janela(email, senha_hash, j))
        for j in (janela, janela - 1)
    )



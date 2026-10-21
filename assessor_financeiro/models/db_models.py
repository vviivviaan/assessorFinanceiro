"""Modelos de banco de dados (ORM via Reflex/SQLModel).

Mantidos exatamente como no projeto original — só foram movidos para cá para
que o resto do sistema não precise saber que o Reflex é o ORM usado por trás.
"""
import datetime
from typing import Optional

import reflex as rx
from sqlmodel import Field


class ChatMessage(rx.Model, table=True):
    """Uma mensagem trocada entre o usuário e o agente, no histórico do chat."""

    role: str
    content: str
    session_id: str = "default_user"
    # Conversa a que a mensagem pertence ("" = a conversa inicial, que
    # reúne o histórico de antes de existir o recurso de várias conversas).
    conversa_id: str = Field(default="", index=True)


class Transaction(rx.Model, table=True):
    """Uma transação financeira (débito ou crédito) registrada pelo usuário."""

    category: str
    amount: float
    type: str
    session_id: str = "default_user"
    created_at: Optional[datetime.datetime] = Field(default_factory=datetime.datetime.now)


class Cliente(rx.Model, table=True):
    """Um cliente do modo 'Assessor Financeiro' (multiempresa/multicliente —
    Fase 7). Cada cliente tem seu próprio `session_id` só dele: é esse
    session_id que entra nos filtros de `ChatMessage`/`Transaction`, então
    o resto do app (chat, transações, relatórios) não precisa saber que
    está olhando pra um cliente em vez do modo pessoal — já funciona do
    jeito que já funciona hoje, só trocando qual session_id está "ativo"."""

    nome: str
    session_id: str
    criado_em: Optional[datetime.datetime] = Field(default_factory=datetime.datetime.now)
    # Dono do cliente (login). Nulo = cliente criado antes do login existir;
    # o primeiro usuário cadastrado adota esses registros.
    usuario_id: Optional[int] = Field(default=None, index=True)


class Conversa(rx.Model, table=True):
    """Uma conversa do chat dentro de um perfil (Pessoal ou um cliente).

    As transações continuam sendo do perfil (`session_id`) e valem para todas
    as conversas; o que muda de uma conversa para outra é só o histórico do
    chat. `conversa_id` = "" identifica a conversa inicial (a que já existia
    antes deste recurso)."""

    session_id: str = Field(index=True)
    conversa_id: str = ""
    titulo: str = "Nova conversa"
    criada_em: Optional[datetime.datetime] = Field(default_factory=datetime.datetime.now)


class Usuario(rx.Model, table=True):
    """Conta de acesso ao app (login por e-mail e senha). Só o hash da senha é guardado."""

    email: str = Field(unique=True, index=True)
    senha_hash: str
    criado_em: Optional[datetime.datetime] = Field(default_factory=datetime.datetime.now)


class ChaveApi(rx.Model, table=True):
    """Chave de API de um provedor de LLM (groq/openai/google) de um usuário,
    guardada CRIPTOGRAFADA (ver core/security.py)."""

    usuario_id: int = Field(index=True)
    provedor: str
    chave_cifrada: str
    atualizada_em: Optional[datetime.datetime] = Field(default_factory=datetime.datetime.now)


class SessaoUsuario(rx.Model, table=True):
    """Login ativo num navegador. Guarda só o hash do token (o token em si fica
    no localStorage do navegador), pra o login sobreviver a um F5."""

    usuario_id: int = Field(index=True)
    token_hash: str = Field(unique=True, index=True)
    expira_em: datetime.datetime

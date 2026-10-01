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

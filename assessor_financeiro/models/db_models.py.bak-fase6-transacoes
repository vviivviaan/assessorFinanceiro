"""Modelos de banco de dados (ORM via Reflex/SQLModel).

Mantidos exatamente como no projeto original — só foram movidos para cá para
que o resto do sistema não precise saber que o Reflex é o ORM usado por trás.
"""
import reflex as rx


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

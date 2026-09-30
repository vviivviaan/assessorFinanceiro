"""Camada de acesso a dados (repositório) para o chat e as transações.

É o ÚNICO módulo do sistema (fora `state.py`) que sabe da existência de
`rx.session`. Isso significa que, se um dia vocês trocarem o Reflex ORM por
outra coisa, só este arquivo precisa mudar — `state.py`, `core/` e `agents/`
continuam intactos.
"""
import reflex as rx

from assessor_financeiro.config import DEFAULT_SESSION_ID
from assessor_financeiro.models.db_models import ChatMessage, Transaction


def get_chat_history(session_id: str = DEFAULT_SESSION_ID) -> list[ChatMessage]:
    with rx.session() as db:
        return (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .all()
        )


def get_transactions(session_id: str = DEFAULT_SESSION_ID) -> list[Transaction]:
    with rx.session() as db:
        return (
            db.query(Transaction)
            .filter(Transaction.session_id == session_id)
            .all()
        )


def add_chat_message(
    role: str, content: str, session_id: str = DEFAULT_SESSION_ID
) -> None:
    with rx.session() as db:
        db.add(ChatMessage(role=role, content=content, session_id=session_id))
        db.commit()


def add_transactions(
    items: list[dict], session_id: str = DEFAULT_SESSION_ID
) -> None:
    """Salva várias transações de uma vez (uma sessão de banco só, um commit só)."""
    with rx.session() as db:
        for item in items:
            db.add(Transaction(session_id=session_id, **item))
        db.commit()


def clear_session_data(session_id: str = DEFAULT_SESSION_ID) -> None:
    with rx.session() as db:
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        db.query(Transaction).filter(Transaction.session_id == session_id).delete()
        db.commit()

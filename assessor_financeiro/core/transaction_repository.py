"""Camada de acesso a dados (repositório) para o chat e as transações.

É o ÚNICO módulo do sistema (fora `state.py`) que sabe da existência de
`rx.session`. Isso significa que, se um dia vocês trocarem o Reflex ORM por
outra coisa, só este arquivo precisa mudar — `state.py`, `core/` e `agents/`
continuam intactos.
"""
import reflex as rx

from assessor_financeiro.config import DEFAULT_SESSION_ID
import datetime

from assessor_financeiro.models.db_models import (
    ChaveApi,
    ChatMessage,
    Cliente,
    Conversa,
    SessaoUsuario,
    Transaction,
    Usuario,
)


def get_chat_history(
    session_id: str = DEFAULT_SESSION_ID, conversa_id: str = ""
) -> list[ChatMessage]:
    with rx.session() as db:
        return (
            db.query(ChatMessage)
            .filter(
                ChatMessage.session_id == session_id,
                ChatMessage.conversa_id == conversa_id,
            )
            .order_by(ChatMessage.id)
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
    role: str,
    content: str,
    session_id: str = DEFAULT_SESSION_ID,
    conversa_id: str = "",
) -> None:
    with rx.session() as db:
        db.add(
            ChatMessage(
                role=role, content=content, session_id=session_id, conversa_id=conversa_id
            )
        )
        db.commit()


def add_transactions(
    items: list[dict], session_id: str = DEFAULT_SESSION_ID
) -> None:
    """Salva várias transações de uma vez (uma sessão de banco só, um commit só)."""
    with rx.session() as db:
        for item in items:
            db.add(Transaction(session_id=session_id, **item))
        db.commit()


def delete_transactions(ids: list[int], session_id: str = DEFAULT_SESSION_ID) -> list[Transaction]:
    """Apaga as transações `ids` DESTE perfil (session_id) e devolve as que foram
    apagadas. O filtro por session_id garante que um id vindo do agente nunca
    apague dado de outro usuário/cliente."""
    if not ids:
        return []
    with rx.session() as db:
        alvos = (
            db.query(Transaction)
            .filter(Transaction.session_id == session_id, Transaction.id.in_(ids))
            .all()
        )
        apagadas = [
            Transaction(
                id=t.id, category=t.category, amount=t.amount, type=t.type,
                session_id=t.session_id, created_at=t.created_at,
            )
            for t in alvos
        ]
        for t in alvos:
            db.delete(t)
        db.commit()
        return apagadas


def clear_session_data(session_id: str = DEFAULT_SESSION_ID) -> None:
    with rx.session() as db:
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        db.query(Conversa).filter(Conversa.session_id == session_id).delete()
        db.query(Transaction).filter(Transaction.session_id == session_id).delete()
        db.commit()


def list_clientes(usuario_id: int | None = None) -> list[Cliente]:
    """Lista os clientes cadastrados no modo 'Assessor Financeiro'
    (multiempresa/multicliente — Fase 7), mais recente primeiro. Com
    `usuario_id`, só os clientes daquele usuário."""
    with rx.session() as db:
        consulta = db.query(Cliente)
        if usuario_id is not None:
            consulta = consulta.filter(Cliente.usuario_id == usuario_id)
        return consulta.order_by(Cliente.criado_em.desc()).all()


def create_cliente(nome: str, session_id: str, usuario_id: int | None = None) -> Cliente:
    """Cadastra um novo cliente com um `session_id` próprio — é esse
    session_id que passa a isolar o chat/transações desse cliente de todos
    os outros (e do modo pessoal)."""
    with rx.session() as db:
        cliente = Cliente(nome=nome, session_id=session_id, usuario_id=usuario_id)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente


# --- Conversas (Fase 5: criar novas conversas e gerenciar as antigas) ---

TITULO_PADRAO_CONVERSA = "Nova conversa"
TITULO_CONVERSA_INICIAL = "Conversa inicial"


def list_conversas(session_id: str = DEFAULT_SESSION_ID) -> list[Conversa]:
    """Conversas do perfil, mais recente primeiro. Se o perfil ainda não tem
    nenhuma, cria a conversa inicial (`conversa_id` = ""), que passa a
    reunir o histórico que já existia antes deste recurso."""
    with rx.session() as db:
        existentes = db.query(Conversa).filter(Conversa.session_id == session_id).count()
        if existentes == 0:
            db.add(
                Conversa(
                    session_id=session_id,
                    conversa_id="",
                    titulo=TITULO_CONVERSA_INICIAL,
                )
            )
            db.commit()
        return (
            db.query(Conversa)
            .filter(Conversa.session_id == session_id)
            .order_by(Conversa.id.desc())
            .all()
        )


def create_conversa(
    session_id: str, conversa_id: str, titulo: str = TITULO_PADRAO_CONVERSA
) -> Conversa:
    with rx.session() as db:
        conversa = Conversa(session_id=session_id, conversa_id=conversa_id, titulo=titulo)
        db.add(conversa)
        db.commit()
        db.refresh(conversa)
        return conversa


def rename_conversa(session_id: str, conversa_id: str, titulo: str) -> None:
    with rx.session() as db:
        conversa = (
            db.query(Conversa)
            .filter(Conversa.session_id == session_id, Conversa.conversa_id == conversa_id)
            .first()
        )
        if conversa is not None:
            conversa.titulo = titulo
            db.add(conversa)
            db.commit()


def delete_conversa(session_id: str, conversa_id: str) -> None:
    """Apaga a conversa e as mensagens dela. As transações do perfil não são afetadas."""
    with rx.session() as db:
        db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id, ChatMessage.conversa_id == conversa_id
        ).delete()
        db.query(Conversa).filter(
            Conversa.session_id == session_id, Conversa.conversa_id == conversa_id
        ).delete()
        db.commit()


# --- Usuários, sessões de login e chaves de API (Fase 5) ---


def count_usuarios() -> int:
    with rx.session() as db:
        return db.query(Usuario).count()


def get_usuario_por_email(email: str) -> Usuario | None:
    with rx.session() as db:
        return db.query(Usuario).filter(Usuario.email == email).first()


def get_usuario(usuario_id: int) -> Usuario | None:
    with rx.session() as db:
        return db.query(Usuario).filter(Usuario.id == usuario_id).first()


def create_usuario(email: str, senha_hash: str) -> Usuario:
    with rx.session() as db:
        usuario = Usuario(email=email, senha_hash=senha_hash)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario


def adotar_dados_legados(usuario_id: int, session_id_legado: str, novo_session_id: str) -> None:
    """Passa para o primeiro usuário tudo que foi criado antes do login existir
    (chat, conversas e transações do perfil antigo + clientes sem dono)."""
    with rx.session() as db:
        for modelo in (ChatMessage, Conversa, Transaction):
            db.query(modelo).filter(modelo.session_id == session_id_legado).update(
                {"session_id": novo_session_id}
            )
        db.query(Cliente).filter(Cliente.usuario_id.is_(None)).update(
            {"usuario_id": usuario_id}
        )
        db.commit()


def create_sessao(usuario_id: int, token_hash: str, expira_em: datetime.datetime) -> None:
    with rx.session() as db:
        db.add(SessaoUsuario(usuario_id=usuario_id, token_hash=token_hash, expira_em=expira_em))
        db.commit()


def get_sessao(token_hash: str) -> SessaoUsuario | None:
    with rx.session() as db:
        return db.query(SessaoUsuario).filter(SessaoUsuario.token_hash == token_hash).first()


def delete_sessao(token_hash: str) -> None:
    with rx.session() as db:
        db.query(SessaoUsuario).filter(SessaoUsuario.token_hash == token_hash).delete()
        db.commit()


def list_chaves_api(usuario_id: int) -> list[ChaveApi]:
    with rx.session() as db:
        return db.query(ChaveApi).filter(ChaveApi.usuario_id == usuario_id).all()


def upsert_chave_api(usuario_id: int, provedor: str, chave_cifrada: str) -> None:
    with rx.session() as db:
        existente = (
            db.query(ChaveApi)
            .filter(ChaveApi.usuario_id == usuario_id, ChaveApi.provedor == provedor)
            .first()
        )
        if existente is None:
            db.add(ChaveApi(usuario_id=usuario_id, provedor=provedor, chave_cifrada=chave_cifrada))
        else:
            existente.chave_cifrada = chave_cifrada
            existente.atualizada_em = datetime.datetime.now()
            db.add(existente)
        db.commit()


def delete_chave_api(usuario_id: int, provedor: str) -> None:
    with rx.session() as db:
        db.query(ChaveApi).filter(
            ChaveApi.usuario_id == usuario_id, ChaveApi.provedor == provedor
        ).delete()
        db.commit()

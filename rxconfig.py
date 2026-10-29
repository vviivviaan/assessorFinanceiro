import os

import reflex as rx


def _url_do_banco() -> str:
    """URL do banco: SQLite local por padrão; em hospedagem, `DB_URL` (ou
    `DATABASE_URL`, que Railway/Render/Neon definem) aponta pro PostgreSQL.
    Provedores costumam entregar "postgres://..." ou "postgresql://...", e o
    SQLAlchemy precisa do driver explícito (psycopg2), então ajustamos."""
    url = os.getenv("DB_URL") or os.getenv("DATABASE_URL") or "sqlite:///reflex.db"
    for prefixo in ("postgres://", "postgresql://"):
        if url.startswith(prefixo):
            return "postgresql+psycopg2://" + url[len(prefixo):]
    return url


config = rx.Config(
    app_name="assessor_financeiro",
    # Permite apontar pra um volume Docker (ex.: sqlite:////app/data/reflex.db)
    # sem mudar nada no dev local, que continua usando o padrão relativo.
    db_url=_url_do_banco(),
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)
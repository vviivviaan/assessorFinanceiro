import os

import reflex as rx

config = rx.Config(
    app_name="assessor_financeiro",
    # Permite apontar pra um volume Docker (ex.: sqlite:////app/data/reflex.db)
    # sem mudar nada no dev local, que continua usando o padrão relativo.
    db_url=os.getenv("DB_URL", "sqlite:///reflex.db"),
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)
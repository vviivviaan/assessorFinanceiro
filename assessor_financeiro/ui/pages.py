"""Páginas do app (frontend). Só monta o layout a partir dos componentes de `ui/components.py`."""
import reflex as rx

from assessor_financeiro.ui.components import chat_panel, dashboard_panel


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading(
                "💰 vivIA: Sua IA Financeira",
                size="8",
                margin_bottom="1em",
                width="100%",
                text_align="center",
            ),
            rx.hstack(
                rx.box(dashboard_panel(), width="40%"),
                chat_panel(),
                width="100vw",
                max_width="1200px",  # Evita que o app estique infinitamente em telas ultra-wide
                spacing="6",
            ),
        ),
        width="100vw",
        min_height="100vh",
        margin="0",
        padding="2em",
        background_color="var(--gray-1)",
    )

"""Páginas do app (frontend). Só monta o layout a partir dos componentes de `ui/components.py`."""
import reflex as rx

from assessor_financeiro.ui.components import right_panel, dashboard_panel


def index() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.box(dashboard_panel(), width="40%", height="100%"),
            right_panel(),
            width="100%",
            max_width="1200px",
            flex="1",
            min_height="0",
            height="100%",
            spacing="6",
            padding="1.5em",
        ),
        display="flex",
        flex_direction="column",
        align_items="center",
        width="100vw",
        height="100vh",
        overflow="hidden",
        background_color="var(--gray-1)",
    )

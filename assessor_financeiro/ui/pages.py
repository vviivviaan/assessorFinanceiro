"""Páginas do app (frontend). Só monta o layout a partir dos componentes de `ui/components.py`."""
import reflex as rx

from assessor_financeiro.state import AdvisorState
from assessor_financeiro.ui.components import (
    app_header,
    clientes_panel,
    dashboard_panel,
    onboarding_screen,
    right_panel,
)
from assessor_financeiro.config import COR_FUNDO_APP, MODO_MULTIEMPRESA


def _app_shell() -> rx.Component:
    """O app "de verdade" (header + dashboard + abas) — o mesmo de sempre,
    só que agora serve tanto o modo Pessoal quanto, reaproveitado sem
    nenhuma mudança, cada cliente do modo Assessor Financeiro (Fase 7):
    quem já trocou de session_id ativo foi `escolher_modo`/`selecionar_cliente`
    no estado, então essas telas nem sabem que isso existe."""
    return rx.box(
        app_header(),
        rx.hstack(
            rx.box(
                dashboard_panel(),
                width="40%",
                height="100%",
                display=["none", "none", "flex"],
            ),
            right_panel(),
            width="100%",
            max_width="1200px",
            flex="1",
            min_height="0",
            height="100%",
            spacing="6",
            padding=["1em", "1em", "1.5em"],
            padding_bottom=["76px", "76px", "1.5em"],
            align_items="stretch",
        ),
        display="flex",
        flex_direction="column",
        align_items="center",
        width="100%",
        height="100%",
    )


def _tela_centralizada(conteudo: rx.Component) -> rx.Component:
    """Wrapper usado pelas telas sem header (onboarding e lista de
    clientes) — centraliza o conteúdo na tela toda, com scroll se precisar."""
    return rx.box(
        conteudo,
        width="100%",
        height="100%",
        display="flex",
        align_items="center",
        justify_content="center",
        overflow_y="auto",
    )


def index() -> rx.Component:
    """Layout raiz. Decide entre três telas conforme o modo salvo
    (`AdvisorState.modo_app`, no localStorage do navegador — Fase 7):
    nenhum modo ainda escolhido -> onboarding; modo multiempresa sem
    cliente selecionado -> lista de clientes; qualquer outro caso (Pessoal,
    ou multiempresa com cliente já selecionado) -> o app normal.

    Responsivo (Fase 6/7): no celular, a coluna fixa do Dashboard do app
    normal fica escondida (vira só mais uma aba dentro de `right_panel`,
    que passa a ocupar 100% da largura); no desktop, aparece lado a lado
    com as abas, como sempre.
    """
    return rx.box(
        rx.cond(
            AdvisorState.modo_app == "",
            _tela_centralizada(onboarding_screen()),
            rx.cond(
                (AdvisorState.modo_app == MODO_MULTIEMPRESA)
                & (AdvisorState.session_id_ativo == ""),
                _tela_centralizada(clientes_panel()),
                _app_shell(),
            ),
        ),
        width="100vw",
        height="100vh",
        overflow="hidden",
        background_color=COR_FUNDO_APP,
    )

"""Componentes visuais reutilizáveis (camada de apresentação / frontend).

Este arquivo só sabe desenhar a UI — toda a lógica de negócio vive em
`state.py` e `core/`. Se um dia vocês quiserem trocar o visual (cores,
layout dos balões, tipo de gráfico), é só mexer aqui.
"""
import reflex as rx

from assessor_financeiro.state import AdvisorState


def message_bubble(message: dict) -> rx.Component:
    """Um balão de mensagem do chat, estilizado conforme o remetente (user/agente)."""
    is_user = message["role"] == "user"
    return rx.box(
        rx.markdown(
            message["content"],
            use_math=False,
            use_katex=False,
            font_size="0.95em",
        ),
        background_color=rx.cond(is_user, "limegreen", "var(--gray-3)"),
        color=rx.cond(is_user, "white", "var(--gray-12)"),
        padding_left="1em",
        padding_right="1em",
        padding_top="none",
        padding_bottom="none",
        border_radius=rx.cond(
            is_user,
            "16px 16px 2px 16px",  # Canto inferior direito reto para o Usuário
            "16px 16px 16px 2px",  # Canto inferior esquerdo reto para a IA
        ),
        margin_y="0.5em",
        align_self=rx.cond(is_user, "flex-end", "flex-start"),
        max_width="80%",
        box_shadow="0 2px 4px rgba(0,0,0,0.20)",
    )


def _saldo_card() -> rx.Component:
    """Card de destaque com o saldo consolidado — primeira coisa que o olho vê no painel."""
    cor_saldo = rx.cond(AdvisorState.saldo_atual >= 0, "#10b981", "#ef4444")
    return rx.vstack(
        rx.text("SALDO ATUAL", size="1", weight="bold", color="gray", letter_spacing="0.05em"),
        rx.heading(AdvisorState.saldo_fmt, size="8", color=cor_saldo),
        rx.hstack(
            rx.hstack(
                rx.icon("trending-up", size=16, color="#10b981"),
                rx.vstack(
                    rx.text("Recebido", size="1", color="gray"),
                    rx.text(AdvisorState.receitas_fmt, size="3", weight="bold"),
                    spacing="0",
                    align_items="start",
                ),
                spacing="2",
                align_items="center",
            ),
            rx.hstack(
                rx.icon("trending-down", size=16, color="#ef4444"),
                rx.vstack(
                    rx.text("Gasto", size="1", color="gray"),
                    rx.text(AdvisorState.gastos_fmt, size="3", weight="bold"),
                    spacing="0",
                    align_items="start",
                ),
                spacing="2",
                align_items="center",
            ),
            spacing="6",
            padding_top="0.5em",
        ),
        spacing="1",
        align_items="start",
        width="100%",
    )


def _categoria_row(item: dict) -> rx.Component:
    """Uma linha da lista de categorias abaixo do gráfico: bolinha colorida + nome + valor."""
    return rx.hstack(
        rx.box(width="10px", height="10px", border_radius="50%", background_color=item["fill"]),
        rx.text(item["name"], size="2"),
        rx.spacer(),
        rx.text(item["value_fmt"], size="2", weight="bold"),
        width="100%",
        align_items="center",
    )


def _dashboard_vazio() -> rx.Component:
    """Estado vazio: nenhuma transação ainda — orienta a usuária a começar pelo chat."""
    return rx.vstack(
        rx.icon("sparkles", size=32, color="gray"),
        rx.text(
            "Nenhuma transação ainda.",
            weight="bold",
            color="gray",
        ),
        rx.text(
            "Conte pra vivIA no chat um gasto ou um recebimento — ex.: "
            '"gastei 50 reais no mercado" — e o painel aparece aqui.',
            size="2",
            color="gray",
            text_align="center",
        ),
        spacing="2",
        align_items="center",
        justify="center",
        padding_y="3em",
        width="100%",
    )


def dashboard_panel() -> rx.Component:
    """Painel esquerdo: saldo consolidado, resumo e distribuição de gastos por categoria."""
    return rx.vstack(
        rx.heading("📊 Visão Geral", size="5"),
        rx.cond(
            AdvisorState.chart_data.length() > 0,
            rx.vstack(
                _saldo_card(),
                rx.divider(margin_y="1em"),
                rx.recharts.pie_chart(
                    rx.recharts.pie(
                        data=AdvisorState.chart_data,
                        data_key="value",
                        name_key="name",
                        cx="50%",
                        cy="50%",
                        outer_radius=90,
                        fill="#8884d8",
                        label=True,
                    ),
                    rx.recharts.tooltip(),
                    height=220,
                    width="100%",
                ),
                rx.vstack(
                    rx.foreach(AdvisorState.category_list, _categoria_row),
                    spacing="2",
                    width="100%",
                    padding_top="0.5em",
                ),
                width="100%",
                spacing="2",
            ),
            _dashboard_vazio(),
        ),
        width="105%",
        padding="1.5em",
        border="1px solid #eaeaea",
        border_radius="12px",
        bg="white",
        background_color="var(--gray-3)",
    )


def chat_loading_indicator() -> rx.Component:
    """Balão de 'pensando...' exibido enquanto o agente processa a resposta."""
    return rx.cond(
        AdvisorState.is_loading,
        rx.box(
            rx.hstack(
                rx.spinner(size="2"),
                rx.text(
                    "Processando e consultando ferramentas...",
                    color="gray",
                    font_size="0.9em",
                    font_style="italic",
                ),
                spacing="3",
                align_items="center",
            ),
            bg="gray.50",
            padding="1em",
            border_radius="8px",
            margin_y="0.5em",
            align_self="flex-start",
            border="1px dashed #ccc",
        ),
    )


def upload_button() -> rx.Component:
    """Botão de anexo/upload de extrato (CSV, XLSX, OFX/QFX ou PDF), com drag-and-drop."""
    return rx.upload(
        rx.button(
            rx.hstack(
                rx.icon("paperclip", size=18),
                align="center",
                width="100%",
            ),
            loading=AdvisorState.is_uploading,
            disabled=False,
            size="3",
            type="button",
            color="blue",
            background_color="var(--gray-1)",
            high_contrast=True,
            cursor="pointer",
            width="100%",
            radius="large",
            border="none",
            margin="none",
            padding="none",
            _hover={"background_color": "blue", "color": "white"},
        ),
        rx.cond(AdvisorState.is_uploading, rx.spinner(size="2")),
        id="csv_upload",
        multiple=False,
        accept={
            "text/csv": [".csv"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
            "application/vnd.ms-excel": [".xls"],
            "application/x-ofx": [".ofx", ".qfx"],
            "application/pdf": [".pdf"],
        },
        max_files=1,
        on_drop=AdvisorState.handle_upload(rx.upload_files(upload_id="csv_upload")),
        border="none",
        padding="0",
        _hover={
            "cursor": "pointer",
            "opacity": 0.9,
            "transform": "scale(1.2)",
            "transition": "transform 0.1s ease",
        },
    )


def chat_input_form() -> rx.Component:
    """Formulário de envio de mensagem (permite usar Enter para enviar)."""
    return rx.form(
        rx.hstack(
            upload_button(),
            rx.input(
                name="chat_input",  # Nome que o form_data vai capturar
                placeholder="Ex: Gastei 150 no borracheiro...",
                width="85%",
                size="3",
            ),
            rx.button(
                rx.icon("send", size=22),
                loading=AdvisorState.is_loading,
                size="3",
                variant="solid",
                _hover={
                    "cursor": "pointer",
                    "opacity": 0.9,
                    "transform": "scale(1.2)",
                    "transition": "transform 0.1s ease",
                },
                type="submit",
                width="10%",
                background_color="limegreen",
                cursor="pointer",
            ),
            width="100%",
        ),
        on_submit=AdvisorState.submit_message,
        reset_on_submit=True,
        width="100%",
    )


def chat_panel() -> rx.Component:
    """Painel direito completo: cabeçalho, histórico de mensagens e formulário."""
    return rx.vstack(
        rx.hstack(
            rx.heading("Chat", size="5"),
            rx.spacer(),
            rx.button(
                rx.icon("trash-2", size=18),
                "Zerar Dados",
                on_click=AdvisorState.clear_chat,
                color_scheme="red",
                variant="soft",
                size="2",
            ),
            width="100%",
            align_items="center",
            padding_bottom="0.5em",
        ),
        rx.auto_scroll(
            rx.vstack(
                rx.foreach(AdvisorState.chat_history, message_bubble),
                chat_loading_indicator(),
                padding_bottom="2em",
            ),
            height="70vh",
            width="100%",
            border="1px solid #eaeaea",
            scroll_behavior="smooth",
            padding_left="1.5em",
            padding_right="1.5em",
            border_radius="12px",
            background_color="#fafafa",
        ),
        chat_input_form(),
        width="60vw",
    )

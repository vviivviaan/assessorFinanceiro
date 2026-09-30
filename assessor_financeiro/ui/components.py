"""Componentes visuais reutilizáveis (camada de apresentação / frontend).

Este arquivo só sabe desenhar a UI — toda a lógica de negócio vive em
`state.py` e `core/`. Se um dia vocês quiserem trocar o visual (cores,
layout dos balões, tipo de gráfico), é só mexer aqui.
"""
import reflex as rx

from assessor_financeiro.state import AdvisorState


def agent_avatar() -> rx.Component:
    """Avatar circular da vivIA, exibido ao lado das mensagens do agente."""
    return rx.box(
        rx.text("💰", font_size="0.95em"),
        width="28px",
        height="28px",
        min_width="28px",
        border_radius="50%",
        background_color="var(--gray-4)",
        display="flex",
        align_items="center",
        justify_content="center",
        flex_shrink="0",
    )


def _chat_bubble(message: dict) -> rx.Component:
    """Um balão de mensagem do chat, estilizado conforme o remetente (user/agente)."""
    is_user = message["role"] == "user"
    bolha = rx.box(
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
        box_shadow="0 2px 4px rgba(0,0,0,0.20)",
        max_width="100%",
    )
    return rx.cond(
        is_user,
        rx.box(
            bolha,
            margin_y="0.5em",
            align_self="flex-end",
            max_width="80%",
        ),
        rx.hstack(
            agent_avatar(),
            bolha,
            spacing="2",
            align_items="flex-end",
            margin_y="0.5em",
            align_self="flex-start",
            max_width="85%",
        ),
    )


def confirmation_card(content: str) -> rx.Component:
    """Card de confirmação exibido quando o agente extrator detecta e salva
    novas transações automaticamente a partir do texto do chat."""
    return rx.box(
        rx.hstack(
            rx.icon("circle-check", size=18, color="#0e7a4b", flex_shrink="0"),
            rx.markdown(content, use_math=False, use_katex=False, font_size="0.9em"),
            spacing="2",
            align_items="start",
        ),
        background_color="#e6f4ec",
        border="1px solid #0e7a4b",
        border_radius="12px",
        padding="0.75em 1em",
        margin_y="0.5em",
        align_self="center",
        max_width="90%",
        width="fit-content",
    )


def warning_card(content: str) -> rx.Component:
    """Card de alerta (ex.: estouro de orçamento/meta). Ainda sem gatilho
    automático — o componente já existe pronto para quando houver dados de
    orçamento/meta no app (Fase 6 [Futuro])."""
    return rx.box(
        rx.hstack(
            rx.icon("triangle-alert", size=18, color="#a8480a", flex_shrink="0"),
            rx.markdown(content, use_math=False, use_katex=False, font_size="0.9em"),
            spacing="2",
            align_items="start",
        ),
        background_color="#fff3e8",
        border="1px solid #a8480a",
        border_radius="12px",
        padding="0.75em 1em",
        margin_y="0.5em",
        align_self="center",
        max_width="90%",
        width="fit-content",
    )


def message_bubble(message: dict) -> rx.Component:
    """Roteia cada mensagem do histórico para o visual certo, conforme o
    'role' salvo no banco: confirmação de transação, alerta, ou balão normal."""
    return rx.cond(
        message["role"] == "confirmation",
        confirmation_card(message["content"]),
        rx.cond(
            message["role"] == "warning",
            warning_card(message["content"]),
            _chat_bubble(message),
        ),
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
        width="100%",
        padding="1.5em",
        border="1px solid #eaeaea",
        border_radius="12px",
        bg="white",
        background_color="var(--gray-3)",
        height="100%",
        overflow_y="auto",
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


def open_finance_button() -> rx.Component:
    """Botão da PoC de Open Finance: importa transações via um fluxo simulado
    de consentimento/autorização, fiel ao contrato oficial (ver `core/open_finance/`)."""
    return rx.button(
        rx.icon("landmark", size=18),
        on_click=AdvisorState.conectar_open_finance,
        loading=AdvisorState.is_uploading,
        disabled=AdvisorState.is_uploading,
        size="3",
        type="button",
        color="blue",
        background_color="var(--gray-1)",
        high_contrast=True,
        cursor="pointer",
        radius="large",
        border="none",
        margin="none",
        padding="none",
        _hover={"background_color": "blue", "color": "white"},
        title="Conectar Open Finance (PoC)",
    )


def chat_input_form() -> rx.Component:
    """Formulário de envio de mensagem (permite usar Enter para enviar)."""
    return rx.form(
        rx.hstack(
            upload_button(),
            open_finance_button(),
            rx.input(
                name="chat_input",  # Nome que o form_data vai capturar
                placeholder="Ex: Gastei 150 no borracheiro...",
                width="75%",
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
        flex_shrink="0",
    )


def _badge_pessoal() -> rx.Component:
    """Chip 'Pessoal' ao lado do logo — identifica o espaço/sessão financeira exibida."""
    return rx.box(
        rx.text("Pessoal", size="1", weight="bold"),
        background_color="var(--gray-4)",
        color="var(--gray-11)",
        padding="0.15em 0.65em",
        border_radius="999px",
    )


def chat_header() -> rx.Component:
    """Header fixo do Chat: logo 'vivIA' + badge 'Pessoal' + botão de zerar dados."""
    return rx.hstack(
        rx.hstack(
            rx.text("💰", font_size="1.3em"),
            rx.heading("vivIA", size="5"),
            _badge_pessoal(),
            spacing="2",
            align_items="center",
        ),
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
        flex_shrink="0",
    )


def chat_panel() -> rx.Component:
    """Conteúdo da aba Chat: cabeçalho, histórico de mensagens e formulário."""
    return rx.vstack(
        chat_header(),
        rx.auto_scroll(
            rx.vstack(
                rx.foreach(AdvisorState.chat_history, message_bubble),
                chat_loading_indicator(),
                padding_bottom="2em",
            ),
            flex="1",
            min_height="0",
            width="100%",
            border="1px solid #eaeaea",
            scroll_behavior="smooth",
            padding_left="1.5em",
            padding_right="1.5em",
            border_radius="12px",
            background_color="#fafafa",
        ),
        chat_input_form(),
        width="100%",
        height="100%",
    )


def _tipo_chip(label: str, valor: str) -> rx.Component:
    """Botão do filtro de tipo (Todas/Entradas/Saidas) — destacado quando ativo."""
    ativo = AdvisorState.filtro_transacoes_tipo == valor
    return rx.button(
        label,
        on_click=AdvisorState.set_filtro_tipo(valor),
        size="2",
        variant=rx.cond(ativo, "solid", "soft"),
        color_scheme=rx.cond(ativo, "grass", "gray"),
        radius="full",
        cursor="pointer",
    )


def _filtros_transacoes() -> rx.Component:
    """Linha de filtros da aba de Transações: tipo (chips) + mês (select)."""
    return rx.hstack(
        rx.hstack(
            _tipo_chip("Todas", "Todas"),
            _tipo_chip("Entradas", "Entradas"),
            _tipo_chip("Saídas", "Saidas"),
            spacing="2",
        ),
        rx.spacer(),
        rx.select.root(
            rx.select.trigger(placeholder="Mês", size="2"),
            rx.select.content(
                rx.foreach(
                    AdvisorState.meses_disponiveis,
                    lambda opcao: rx.select.item(opcao["label"], value=opcao["value"]),
                ),
            ),
            value=AdvisorState.filtro_transacoes_mes,
            on_change=AdvisorState.set_filtro_mes,
        ),
        width="100%",
        align_items="center",
        padding_bottom="0.75em",
        flex_shrink="0",
    )


def _transacao_row(item: dict) -> rx.Component:
    """Uma linha da lista de transações: ícone de entrada/saída, categoria, hora e valor."""
    cor = rx.cond(item["is_credito"], "#0e7a4b", "#ef4444")
    return rx.hstack(
        rx.icon(
            rx.cond(item["is_credito"], "arrow-down-circle", "arrow-up-circle"),
            size=18,
            color=cor,
            flex_shrink="0",
        ),
        rx.vstack(
            rx.text(item["category"], size="2", weight="medium"),
            rx.text(item["hora"], size="1", color="gray"),
            spacing="0",
            align_items="start",
        ),
        rx.spacer(),
        rx.text(item["amount_fmt_signed"], size="2", weight="bold", color=cor),
        width="100%",
        align_items="center",
        padding_y="0.6em",
        border_bottom="1px solid var(--gray-4)",
    )


def _grupo_dia(grupo: dict) -> rx.Component:
    """Um bloco de transações do mesmo dia, com o rótulo do dia (Hoje/Ontem/data) no topo."""
    return rx.vstack(
        rx.text(
            grupo["rotulo"],
            size="2",
            weight="bold",
            color="gray",
            padding_top="0.75em",
            padding_bottom="0.25em",
        ),
        rx.foreach(grupo["itens"], _transacao_row),
        width="100%",
        spacing="0",
        align_items="start",
    )


def _transacoes_vazio() -> rx.Component:
    """Estado vazio da aba de Transações — nenhum resultado para o filtro atual."""
    return rx.vstack(
        rx.icon("inbox", size=32, color="gray"),
        rx.text("Nenhuma transação encontrada para esse filtro.", color="gray", size="2"),
        spacing="2",
        align_items="center",
        justify="center",
        padding_y="3em",
        width="100%",
    )


def transacoes_panel() -> rx.Component:
    """Conteúdo da aba Transações: filtros + lista completa agrupada por dia."""
    return rx.vstack(
        _filtros_transacoes(),
        rx.box(
            rx.cond(
                AdvisorState.transacoes_agrupadas.length() > 0,
                rx.vstack(
                    rx.foreach(AdvisorState.transacoes_agrupadas, _grupo_dia),
                    width="100%",
                    spacing="1",
                ),
                _transacoes_vazio(),
            ),
            flex="1",
            min_height="0",
            width="100%",
            overflow_y="auto",
            border="1px solid #eaeaea",
            border_radius="12px",
            background_color="#fafafa",
            padding_left="1.5em",
            padding_right="1.5em",
            scroll_behavior="smooth",
        ),
        width="100%",
        height="100%",
    )


def _grafico_barras_mensal() -> rx.Component:
    """Gráfico de barras: Entradas x Saídas nos últimos 6 meses."""
    return rx.recharts.bar_chart(
        rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
        rx.recharts.x_axis(data_key="mes"),
        rx.recharts.y_axis(),
        rx.recharts.bar(data_key="Entradas", fill="#10b981"),
        rx.recharts.bar(data_key="Saidas", fill="#ef4444"),
        rx.recharts.legend(),
        rx.recharts.tooltip(),
        data=AdvisorState.relatorio_mensal,
        height=260,
        width="100%",
    )


def _grafico_rosca_categorias() -> rx.Component:
    """Gráfico de rosca (donut) com a distribuição de gastos por categoria."""
    return rx.recharts.pie_chart(
        rx.recharts.pie(
            data=AdvisorState.chart_data,
            data_key="value",
            name_key="name",
            cx="50%",
            cy="50%",
            inner_radius=50,
            outer_radius=85,
            fill="#8884d8",
            label=True,
        ),
        rx.recharts.tooltip(),
        height=220,
        width="100%",
    )


def _insight_card() -> rx.Component:
    """Card com o insight em linguagem natural sobre os gastos do mês atual."""
    return rx.box(
        rx.hstack(
            rx.icon("lightbulb", size=18, color="#a8480a", flex_shrink="0"),
            rx.markdown(
                AdvisorState.insight_texto,
                use_math=False,
                use_katex=False,
                font_size="0.9em",
            ),
            spacing="2",
            align_items="start",
        ),
        background_color="#fff3e8",
        border="1px solid #a8480a",
        border_radius="12px",
        padding="0.9em 1.1em",
        width="100%",
    )


def _relatorios_vazio() -> rx.Component:
    """Estado vazio da aba de Relatórios — nenhuma transação registrada ainda."""
    return rx.vstack(
        rx.icon("chart-no-axes-combined", size=32, color="gray"),
        rx.text(
            "Ainda não há dados suficientes para gerar relatórios.",
            color="gray",
            size="2",
        ),
        spacing="2",
        align_items="center",
        justify="center",
        padding_y="3em",
        width="100%",
    )


def relatorios_panel() -> rx.Component:
    """Conteúdo da aba Relatórios: entradas x saídas (6 meses), distribuição
    por categoria e um card de insight em linguagem natural."""
    return rx.box(
        rx.cond(
            AdvisorState.chart_data.length() > 0,
            rx.vstack(
                _insight_card(),
                rx.vstack(
                    rx.text("Entradas x Saídas (últimos 6 meses)", size="3", weight="bold"),
                    _grafico_barras_mensal(),
                    width="100%",
                    spacing="2",
                    padding_top="1em",
                ),
                rx.vstack(
                    rx.text("Distribuição por Categoria", size="3", weight="bold"),
                    _grafico_rosca_categorias(),
                    rx.vstack(
                        rx.foreach(AdvisorState.category_list, _categoria_row),
                        spacing="2",
                        width="100%",
                    ),
                    width="100%",
                    spacing="2",
                    padding_top="1em",
                ),
                width="100%",
                spacing="3",
                padding_bottom="2em",
            ),
            _relatorios_vazio(),
        ),
        flex="1",
        min_height="0",
        width="100%",
        overflow_y="auto",
        padding_right="0.5em",
    )


def right_panel() -> rx.Component:
    """Painel direito da tela: abas Chat / Transações / Relatórios."""
    return rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger("💬 Chat", value="chat"),
            rx.tabs.trigger("📋 Transações", value="transacoes"),
            rx.tabs.trigger("📊 Relatórios", value="relatorios"),
            flex_shrink="0",
        ),
        rx.tabs.content(
            chat_panel(),
            value="chat",
            width="100%",
            flex="1",
            min_height="0",
            display="flex",
            padding_top="0.75em",
        ),
        rx.tabs.content(
            transacoes_panel(),
            value="transacoes",
            width="100%",
            flex="1",
            min_height="0",
            display="flex",
            padding_top="0.75em",
        ),
        rx.tabs.content(
            relatorios_panel(),
            value="relatorios",
            width="100%",
            flex="1",
            min_height="0",
            display="flex",
            padding_top="0.75em",
        ),
        default_value="chat",
        width="60%",
        height="100%",
        display="flex",
        flex_direction="column",
    )

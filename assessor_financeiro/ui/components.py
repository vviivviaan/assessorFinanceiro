"""Componentes visuais reutilizáveis (camada de apresentação / frontend).

Este arquivo só sabe desenhar a UI — toda a lógica de negócio vive em
`state.py` e `core/`. Se um dia vocês quiserem trocar o visual (cores,
layout dos balões, tipo de gráfico), é só mexer aqui.

Fase 7 (redesign visual + responsivo): paleta/formas inspiradas no mockup
de referência (header navy, cards brancos arredondados, chips/pills) e
layout responsivo via arrays de breakpoint do Reflex — cada prop de estilo
que recebe uma lista `[mobile, mobile, desktop]` usa o valor certo conforme
a largura da tela, sem precisar de JS nem de estado extra.
"""
import reflex as rx

from assessor_financeiro.state import AdvisorState
from assessor_financeiro.config import (
    MODO_MULTIEMPRESA,
    MODO_PESSOAL,
    COR_NAVY,
    COR_NAVY_ESCURO,
    COR_NAVY_SUAVE,
    COR_FUNDO_APP,
    COR_VERDE,
    COR_VERDE_BG,
    COR_VERMELHO,
    COR_VERMELHO_BG,
    COR_ALERTA,
    COR_ALERTA_BG,
    RAIO_CARD,
    SOMBRA_CARD,
)


def _card(*children, **kwargs) -> rx.Component:
    """Card branco arredondado padrão (base de quase todo bloco do app)."""
    estilo = dict(
        background_color="white",
        border_radius=RAIO_CARD,
        box_shadow=SOMBRA_CARD,
        padding="1.25em",
        width="100%",
        spacing="3",
        align_items="stretch",
    )
    estilo.update(kwargs)
    return rx.vstack(*children, **estilo)


def agent_avatar() -> rx.Component:
    """Avatar circular da vivIA, exibido ao lado das mensagens do agente."""
    return rx.box(
        rx.text("💰", font_size="0.95em"),
        width="28px",
        height="28px",
        min_width="28px",
        border_radius="50%",
        background_color=COR_NAVY,
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
        background_color=rx.cond(is_user, COR_NAVY, "#f2f4fa"),
        color=rx.cond(is_user, "white", "#1a2540"),
        padding_left="1em",
        padding_right="1em",
        padding_top="none",
        padding_bottom="none",
        border=rx.cond(is_user, "none", "1px solid #e7e9f5"),
        border_radius=rx.cond(
            is_user,
            "16px 16px 2px 16px",  # Canto inferior direito reto para o Usuário
            "16px 16px 16px 2px",  # Canto inferior esquerdo reto para a IA
        ),
        box_shadow=rx.cond(is_user, "0 2px 6px rgba(20,42,92,0.25)", "none"),
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
            rx.icon("circle-check", size=18, color=COR_VERDE, flex_shrink="0"),
            rx.markdown(content, use_math=False, use_katex=False, font_size="0.9em"),
            spacing="2",
            align_items="start",
        ),
        background_color=COR_VERDE_BG,
        border_radius="16px",
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
            rx.icon("triangle-alert", size=18, color=COR_ALERTA, flex_shrink="0"),
            rx.markdown(content, use_math=False, use_katex=False, font_size="0.9em"),
            spacing="2",
            align_items="start",
        ),
        background_color=COR_ALERTA_BG,
        border_radius="16px",
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


def _badge_modo() -> rx.Component:
    """Chip ao lado do logo — mostra 'Pessoal' ou o nome do cliente ativo no
    modo Assessor Financeiro (multiempresa), pra ficar sempre claro em qual
    espaço de dados você está (Fase 7)."""
    texto = rx.cond(
        AdvisorState.modo_app == MODO_MULTIEMPRESA,
        AdvisorState.cliente_ativo_nome,
        "Pessoal",
    )
    return rx.box(
        rx.text(texto, size="1", weight="bold"),
        background_color="rgba(255,255,255,0.15)",
        color="white",
        padding="0.15em 0.65em",
        border_radius="999px",
    )


def app_header() -> rx.Component:
    """Header navy fixo no topo do app: logo 'vivIA' + badge 'Pessoal' + botão
    de zerar dados. Substitui o antigo header interno da aba Chat — agora
    aparece uma vez só, acima de todas as abas (Fase 7)."""
    return rx.hstack(
        rx.hstack(
            rx.box(
                rx.text("💰", font_size="1.05em"),
                width="34px",
                height="34px",
                border_radius="10px",
                background_color="rgba(255,255,255,0.15)",
                display="flex",
                align_items="center",
                justify_content="center",
                flex_shrink="0",
            ),
            rx.heading("vivIA", size="5", color="white"),
            _badge_modo(),
            spacing="2",
            align_items="center",
        ),
        rx.cond(
            AdvisorState.modo_app == MODO_MULTIEMPRESA,
            rx.button(
                rx.icon("arrow-left", size=16),
                "Clientes",
                on_click=AdvisorState.voltar_para_clientes,
                variant="ghost",
                size="2",
                style={"color": "rgba(255,255,255,0.85)"},
                _hover={"background_color": "rgba(255,255,255,0.14)"},
            ),
            rx.fragment(),
        ),
        rx.spacer(),
        rx.button(
            rx.icon("repeat", size=16),
            rx.text("Trocar de modo", display=["none", "none", "block"]),
            on_click=AdvisorState.trocar_modo,
            variant="ghost",
            size="2",
            style={"color": "rgba(255,255,255,0.85)"},
            _hover={"background_color": "rgba(255,255,255,0.14)"},
        ),
        rx.button(
            rx.icon("trash-2", size=16),
            rx.text("Zerar Dados", display=["none", "none", "block"]),
            on_click=AdvisorState.clear_chat,
            variant="ghost",
            size="2",
            style={"color": "rgba(255,255,255,0.85)"},
            _hover={"background_color": "rgba(255,255,255,0.14)"},
        ),
        width="100%",
        max_width="1200px",
        align_items="center",
        padding=["0.85em 1em", "0.85em 1em", "0.9em 1.5em"],
        background_color=COR_NAVY,
        border_radius="0 0 22px 22px",
        flex_shrink="0",
    )


def _pill_entrada_saida(label: str, valor_fmt, is_credito: bool) -> rx.Component:
    """Sub-card 'Entradas'/'Saídas' do resumo do Dashboard: ícone circular +
    rótulo + valor, sobre um fundo levemente tingido de verde/vermelho."""
    cor = rx.cond(is_credito, COR_VERDE, COR_VERMELHO)
    cor_bg = rx.cond(is_credito, COR_VERDE_BG, COR_VERMELHO_BG)
    icone = rx.cond(is_credito, "arrow-up-right", "arrow-down-right")
    return rx.hstack(
        rx.box(
            rx.icon(icone, size=14, color="white"),
            width="30px",
            height="30px",
            border_radius="50%",
            background_color=cor,
            display="flex",
            align_items="center",
            justify_content="center",
            flex_shrink="0",
        ),
        rx.vstack(
            rx.text(label, size="1", color="var(--gray-9)"),
            rx.text(valor_fmt, size="3", weight="bold", color="#1a2540"),
            spacing="0",
            align_items="start",
        ),
        spacing="2",
        align_items="center",
        background_color=cor_bg,
        border_radius="14px",
        padding="0.6em 0.8em",
        flex="1",
    )


def _resumo_geral_card() -> rx.Component:
    """Card de resumo: saldo geral + badge Positivo/Negativo + pills de
    Entradas/Saídas + barra de progresso (% já gasto do que entrou)."""
    positivo = AdvisorState.saldo_atual >= 0
    cor_saldo = rx.cond(positivo, COR_VERDE, COR_VERMELHO)
    return _card(
        rx.hstack(
            rx.text("Saldo geral", size="2", color="var(--gray-9)"),
            rx.spacer(),
            rx.box(
                rx.text(
                    rx.cond(positivo, "Positivo", "Negativo"),
                    size="1",
                    weight="bold",
                ),
                background_color=rx.cond(positivo, COR_VERDE_BG, COR_VERMELHO_BG),
                color=cor_saldo,
                padding="0.2em 0.7em",
                border_radius="999px",
            ),
            width="100%",
            align_items="center",
        ),
        rx.heading(AdvisorState.saldo_fmt, size="8", color=cor_saldo),
        rx.hstack(
            _pill_entrada_saida("Entradas", AdvisorState.receitas_fmt, True),
            _pill_entrada_saida("Saídas", AdvisorState.gastos_fmt, False),
            spacing="2",
            width="100%",
        ),
        rx.box(
            rx.box(
                width=f"{AdvisorState.percentual_gasto}%",
                height="100%",
                background_color=COR_NAVY,
                border_radius="999px",
            ),
            width="100%",
            height="8px",
            background_color="var(--gray-4)",
            border_radius="999px",
            overflow="hidden",
        ),
        rx.hstack(
            rx.text("Você já gastou", size="2", color="var(--gray-9)"),
            rx.text(f"{AdvisorState.percentual_gasto}%", size="2", weight="bold", color="var(--gray-9)"),
            rx.text("do que recebeu", size="2", color="var(--gray-9)"),
            spacing="1",
        ),
        spacing="3",
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


def _grafico_rosca_categorias() -> rx.Component:
    """Gráfico de rosca (donut) com a distribuição de gastos por categoria,
    com o total gasto centralizado (como no mockup de referência)."""
    return rx.box(
        rx.recharts.pie_chart(
            rx.recharts.pie(
                data=AdvisorState.chart_data,
                data_key="value",
                name_key="name",
                cx="50%",
                cy="50%",
                inner_radius=62,
                outer_radius=95,
                fill="#8884d8",
                stroke="white",
                stroke_width=2,
            ),
            rx.recharts.tooltip(),
            height=230,
            width="100%",
        ),
        rx.vstack(
            rx.text("Total", size="1", color="var(--gray-9)"),
            rx.text(AdvisorState.gastos_fmt, size="4", weight="bold", color=COR_NAVY),
            spacing="0",
            align_items="center",
            position="absolute",
            top="50%",
            left="50%",
            transform="translate(-50%, -52%)",
            pointer_events="none",
        ),
        position="relative",
        width="100%",
    )


def _categorias_card() -> rx.Component:
    """Card 'Gastos por categoria': donut + legenda, usado no Dashboard e
    reaproveitado (mesmo visual) na aba de Relatórios."""
    return _card(
        rx.hstack(
            rx.text("Gastos por categoria", size="3", weight="bold", color="#1a2540"),
            spacing="2",
            align_items="center",
        ),
        _grafico_rosca_categorias(),
        rx.vstack(
            rx.foreach(AdvisorState.category_list, _categoria_row),
            spacing="2",
            width="100%",
        ),
    )


def _mini_transacao_icone(is_credito) -> rx.Component:
    """Ícone quadrado arredondado (entrada/saída) usado nas listas de transações."""
    cor = rx.cond(is_credito, COR_VERDE, COR_VERMELHO)
    cor_bg = rx.cond(is_credito, COR_VERDE_BG, COR_VERMELHO_BG)
    icone = rx.cond(is_credito, "arrow-up-right", "arrow-down-right")
    return rx.box(
        rx.icon(icone, size=16, color=cor),
        width="38px",
        height="38px",
        min_width="38px",
        border_radius="12px",
        background_color=cor_bg,
        display="flex",
        align_items="center",
        justify_content="center",
        flex_shrink="0",
    )


def _mini_transacao_row(item: dict) -> rx.Component:
    """Linha compacta de transação, usada na mini-lista do Dashboard."""
    cor = rx.cond(item["is_credito"], COR_VERDE, COR_VERMELHO)
    return rx.hstack(
        _mini_transacao_icone(item["is_credito"]),
        rx.vstack(
            rx.text(item["category"], size="2", weight="medium", color="#1a2540"),
            rx.text(item["hora"], size="1", color="var(--gray-9)"),
            spacing="0",
            align_items="start",
        ),
        rx.spacer(),
        rx.text(item["amount_fmt_signed"], size="2", weight="bold", color=cor),
        width="100%",
        align_items="center",
    )


def _ultimas_transacoes_card() -> rx.Component:
    """Card 'Últimas transações' do Dashboard — as 5 mais recentes."""
    return _card(
        rx.text("Últimas transações", size="3", weight="bold", color="#1a2540"),
        rx.foreach(AdvisorState.ultimas_transacoes, _mini_transacao_row),
    )


def _dashboard_vazio() -> rx.Component:
    """Estado vazio: nenhuma transação ainda — orienta a usuária a começar pelo chat."""
    return _card(
        rx.vstack(
            rx.icon("sparkles", size=32, color="var(--gray-8)"),
            rx.text("Nenhuma transação ainda.", weight="bold", color="var(--gray-10)"),
            rx.text(
                "Conte pra vivIA no chat um gasto ou um recebimento — ex.: "
                '"gastei 50 reais no mercado" — e o painel aparece aqui.',
                size="2",
                color="var(--gray-9)",
                text_align="center",
            ),
            spacing="2",
            align_items="center",
            justify="center",
            padding_y="2em",
            width="100%",
        ),
    )


def dashboard_panel() -> rx.Component:
    """Painel de visão geral: saldo, entradas/saídas, distribuição por
    categoria e últimas transações — em cards brancos sobre o fundo claro
    do app (Fase 7). No desktop fica fixo à esquerda; no celular vira uma
    aba (ver `right_panel`)."""
    return rx.box(
        rx.cond(
            AdvisorState.transacoes_todas.length() > 0,
            rx.vstack(
                _resumo_geral_card(),
                rx.cond(AdvisorState.chart_data.length() > 0, _categorias_card(), rx.fragment()),
                _ultimas_transacoes_card(),
                width="100%",
                spacing="3",
                padding_bottom="1.5em",
            ),
            _dashboard_vazio(),
        ),
        width="100%",
        height="100%",
        overflow_y="auto",
        padding_right="0.25em",
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
                    color="var(--gray-9)",
                    font_size="0.9em",
                    font_style="italic",
                ),
                spacing="3",
                align_items="center",
            ),
            background_color="#f2f4fa",
            padding="1em",
            border_radius="14px",
            margin_y="0.5em",
            align_self="flex-start",
            border="1px dashed #c7cee3",
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
            color=COR_NAVY,
            background_color="var(--gray-1)",
            high_contrast=True,
            cursor="pointer",
            width="100%",
            radius="large",
            border="none",
            margin="none",
            padding="none",
            _hover={"background_color": COR_NAVY, "color": "white"},
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
        color=COR_NAVY,
        background_color="var(--gray-1)",
        high_contrast=True,
        cursor="pointer",
        radius="large",
        border="none",
        margin="none",
        padding="none",
        _hover={"background_color": COR_NAVY, "color": "white"},
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
                background_color=COR_VERDE,
                cursor="pointer",
            ),
            width="100%",
        ),
        on_submit=AdvisorState.submit_message,
        reset_on_submit=True,
        width="100%",
        flex_shrink="0",
    )


def chat_panel() -> rx.Component:
    """Conteúdo da aba Chat: histórico de mensagens + formulário. O header
    (logo/badge/zerar dados) agora é único e fica em `app_header()`, acima
    de todas as abas (Fase 7)."""
    return rx.vstack(
        rx.auto_scroll(
            rx.vstack(
                rx.foreach(AdvisorState.chat_history, message_bubble),
                chat_loading_indicator(),
                padding_bottom="2em",
            ),
            flex="1",
            min_height="0",
            width="100%",
            border="1px solid #e7e9f5",
            scroll_behavior="smooth",
            padding_left="1.5em",
            padding_right="1.5em",
            border_radius=RAIO_CARD,
            background_color="#fafbfd",
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
        variant="ghost",
        cursor="pointer",
        color=rx.cond(ativo, "white", "var(--gray-10)"),
        background_color=rx.cond(ativo, COR_NAVY, "transparent"),
        border_radius="999px",
        padding="0.4em 1em",
        _hover={"background_color": rx.cond(ativo, COR_NAVY, "var(--gray-4)")},
    )


def _filtros_transacoes() -> rx.Component:
    """Linha de filtros da aba de Transações: tipo (chips segmentados) + mês (select)."""
    return rx.hstack(
        rx.hstack(
            _tipo_chip("Todas", "Todas"),
            _tipo_chip("Entradas", "Entradas"),
            _tipo_chip("Saídas", "Saidas"),
            spacing="1",
            background_color="var(--gray-3)",
            border_radius="999px",
            padding="0.25em",
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
        flex_wrap="wrap",
        gap="0.5em",
    )


def _transacao_row(item: dict) -> rx.Component:
    """Uma linha da lista de transações: ícone quadrado, categoria, hora e valor."""
    cor = rx.cond(item["is_credito"], COR_VERDE, COR_VERMELHO)
    return rx.hstack(
        _mini_transacao_icone(item["is_credito"]),
        rx.vstack(
            rx.text(item["category"], size="2", weight="medium", color="#1a2540"),
            rx.text(item["hora"], size="1", color="var(--gray-9)"),
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
            color="var(--gray-9)",
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
        rx.icon("inbox", size=32, color="var(--gray-8)"),
        rx.text("Nenhuma transação encontrada para esse filtro.", color="var(--gray-9)", size="2"),
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
            border="1px solid #e7e9f5",
            border_radius=RAIO_CARD,
            background_color="#fafbfd",
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
        rx.recharts.bar(data_key="Entradas", fill="#c7d0e8", radius=[4, 4, 0, 0]),
        rx.recharts.bar(data_key="Saidas", fill=COR_NAVY, radius=[4, 4, 0, 0]),
        rx.recharts.legend(),
        rx.recharts.tooltip(),
        data=AdvisorState.relatorio_mensal,
        height=260,
        width="100%",
    )


def _insight_card() -> rx.Component:
    """Card com o insight em linguagem natural sobre os gastos do mês atual,
    com o avatar da vivIA (como no mockup de referência)."""
    return rx.hstack(
        agent_avatar(),
        rx.markdown(
            AdvisorState.insight_texto,
            use_math=False,
            use_katex=False,
            font_size="0.9em",
        ),
        spacing="2",
        align_items="start",
        background_color="white",
        border_radius=RAIO_CARD,
        box_shadow=SOMBRA_CARD,
        padding="1em 1.1em",
        width="100%",
    )


def _relatorios_vazio() -> rx.Component:
    """Estado vazio da aba de Relatórios — nenhuma transação registrada ainda."""
    return rx.vstack(
        rx.icon("chart-no-axes-combined", size=32, color="var(--gray-8)"),
        rx.text(
            "Ainda não há dados suficientes para gerar relatórios.",
            color="var(--gray-9)",
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
            AdvisorState.transacoes_todas.length() > 0,
            rx.vstack(
                rx.hstack(
                    rx.heading("Relatórios", size="4", color="#1a2540"),
                    rx.spacer(),
                    rx.button(
                        rx.icon("download", size=16),
                        "Exportar",
                        on_click=AdvisorState.exportar_relatorio_csv,
                        variant="soft",
                        size="2",
                        cursor="pointer",
                    ),
                    width="100%",
                    align_items="center",
                ),
                _insight_card(),
                _card(
                    rx.text("Entradas x Saídas · últimos 6 meses", size="3", weight="bold", color="#1a2540"),
                    _grafico_barras_mensal(),
                ),
                rx.cond(AdvisorState.chart_data.length() > 0, _categorias_card(), rx.fragment()),
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
        padding_right="0.25em",
    )


def _tab_trigger(icone: str, label: str, valor: str, apenas_mobile: bool = False) -> rx.Component:
    """Botão de aba com ícone + rótulo — funciona tanto como aba comum no
    desktop quanto como item da barra de navegação inferior no celular
    (é a mesma `rx.tabs.list` que muda de posição via CSS responsivo, ver
    `right_panel`).

    `apenas_mobile=True` esconde o próprio botão (não só o conteúdo da aba)
    a partir do desktop — usado pela aba "Dashboard", que no desktop já
    aparece fixa na coluna da esquerda (ver `dashboard_panel`/`pages.py`),
    então o botão duplicado só confundia (clicar nele mostrava uma área
    vazia, já que o conteúdo dessa aba também só existe no celular)."""
    extra = {"display": ["flex", "flex", "none"]} if apenas_mobile else {}
    return rx.tabs.trigger(
        rx.vstack(
            rx.icon(icone, size=19),
            rx.text(label, size="1"),
            spacing="1",
            align_items="center",
        ),
        value=valor,
        style={
            "display": "flex",
            "flex_direction": "column",
            "align_items": "center",
            "padding": "0.35em 0.9em",
            "border_radius": "14px",
            "color": "var(--gray-9)",
            "cursor": "pointer",
            "&[data-state='active']": {
                "color": COR_NAVY,
                "background_color": COR_NAVY_SUAVE,
                "font_weight": "700",
            },
        },
        **extra,
    )


def right_panel() -> rx.Component:
    """Painel principal: abas Dashboard* / Chat / Transações / Relatórios.

    *A aba "Dashboard" só existe (e só aparece na barra) no celular — no
    desktop a visão geral já é exibida fixa na coluna esquerda, então a
    aba fica escondida pra não duplicar. No celular a `rx.tabs.list` some
    do topo e passa a flutuar fixa no rodapé da tela (barra de navegação),
    só trocando alguns estilos via arrays de breakpoint — sem nenhum
    componente nem estado extra."""
    return rx.tabs.root(
        rx.tabs.list(
            _tab_trigger("layout-dashboard", "Dashboard", "dashboard", apenas_mobile=True),
            _tab_trigger("message-circle", "Chat", "chat"),
            _tab_trigger("list", "Transações", "transacoes"),
            _tab_trigger("bar-chart-3", "Relatórios", "relatorios"),
            position=["fixed", "fixed", "static"],
            bottom=["0", "0", "auto"],
            left=["0", "0", "auto"],
            width=["100%", "100%", "auto"],
            background_color=["white", "white", "transparent"],
            box_shadow=["0 -2px 14px rgba(15,32,72,0.12)", "0 -2px 14px rgba(15,32,72,0.12)", "none"],
            padding=["0.4em 0.5em", "0.4em 0.5em", "0"],
            justify_content=["space-around", "space-around", "flex-start"],
            z_index="30",
            gap=["0", "0", "0.5em"],
            flex_shrink="0",
        ),
        rx.tabs.content(
            dashboard_panel(),
            value="dashboard",
            width="100%",
            flex="1",
            min_height="0",
            display=["flex", "flex", "none"],
            padding_top="0.75em",
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
        width=["100%", "100%", "60%"],
        height="100%",
        display="flex",
        flex_direction="column",
    )


# --- Modo de uso: onboarding + lista de clientes (Fase 7) ---


def _onboarding_card(
    titulo: str,
    descricao: str,
    chips: list,
    on_click,
    recomendado: bool = False,
) -> rx.Component:
    """Um dos dois cards da tela de escolha de modo (Pessoal / Assessor
    Financeiro multiempresa) — `titulo`, `descricao` e `chips` são sempre
    texto fixo (não vêm do estado), então usar Python puro aqui é seguro."""
    return rx.vstack(
        rx.cond(
            recomendado,
            rx.box(
                rx.text("Recomendado", size="1", weight="bold", color="white"),
                background_color=COR_NAVY,
                padding="0.2em 0.7em",
                border_radius="999px",
            ),
            rx.fragment(),
        ),
        rx.heading(titulo, size="5", color="#1a2540"),
        rx.text(descricao, size="2", color="var(--gray-9)"),
        rx.hstack(
            *[
                rx.box(
                    rx.text(chip, size="1", color="var(--gray-10)"),
                    background_color="var(--gray-3)",
                    padding="0.2em 0.6em",
                    border_radius="999px",
                )
                for chip in chips
            ],
            spacing="2",
            flex_wrap="wrap",
        ),
        rx.button(
            "Continuar",
            on_click=on_click,
            background_color=COR_NAVY,
            color="white",
            size="3",
            width="100%",
            cursor="pointer",
            margin_top="0.5em",
            _hover={"opacity": "0.9"},
        ),
        spacing="3",
        align_items="start",
        background_color="white",
        border_radius=RAIO_CARD,
        box_shadow=SOMBRA_CARD,
        padding="1.5em",
        width="100%",
        max_width="420px",
        border=f"2px solid {COR_NAVY}" if recomendado else "1px solid #e7e9f5",
    )


def onboarding_screen() -> rx.Component:
    """Tela de escolha de modo — primeira coisa que aparece quando ainda não
    se escolheu Pessoal ou Assessor Financeiro multiempresa (referência:
    página 3 do mockup). Dá pra trocar depois a qualquer momento (botão
    'Clientes'/'Trocar de modo' no header/lista de clientes)."""
    return rx.vstack(
        rx.box(
            rx.text("💰", font_size="1.4em"),
            width="52px",
            height="52px",
            border_radius="16px",
            background_color=COR_NAVY,
            display="flex",
            align_items="center",
            justify_content="center",
        ),
        rx.heading("Como você quer usar a vivIA?", size="6", color="#1a2540", text_align="center"),
        rx.text(
            "Escolha o modo de assessoria. Dá pra trocar depois.",
            size="2",
            color="var(--gray-9)",
            text_align="center",
        ),
        rx.vstack(
            _onboarding_card(
                "Assessor Financeiro Pessoal",
                "Controle o seu dia a dia: saldo, gastos por categoria e "
                "transações, com lançamentos por texto no chat.",
                ["Uso individual"],
                AdvisorState.escolher_modo(MODO_PESSOAL),
                recomendado=True,
            ),
            _onboarding_card(
                "Assessor Financeiro",
                "Análises gerais: várias empresas, carteiras ou clientes "
                "diferentes, cada um com seu próprio histórico.",
                ["Multiempresa", "Múltiplos clientes"],
                AdvisorState.escolher_modo(MODO_MULTIEMPRESA),
            ),
            spacing="4",
            width="100%",
            align_items="center",
            padding_top="1em",
        ),
        spacing="3",
        align_items="center",
        width="100%",
        max_width="480px",
        padding="2em 1.5em",
    )


def _cliente_row(cliente: dict) -> rx.Component:
    """Uma linha clicável da lista de clientes — entra no espaço daquele
    cliente (chat/transações/relatórios próprios)."""
    return rx.hstack(
        rx.box(
            rx.icon("building-2", size=18, color="white"),
            width="36px",
            height="36px",
            border_radius="50%",
            background_color=COR_NAVY,
            display="flex",
            align_items="center",
            justify_content="center",
            flex_shrink="0",
        ),
        rx.text(cliente["nome"], size="3", weight="medium", color="#1a2540"),
        rx.spacer(),
        rx.icon("chevron-right", size=18, color="var(--gray-8)"),
        on_click=AdvisorState.selecionar_cliente(cliente["session_id"], cliente["nome"]),
        width="100%",
        align_items="center",
        padding="0.75em 1em",
        border_radius="14px",
        cursor="pointer",
        _hover={"background_color": "var(--gray-3)"},
    )


def _novo_cliente_form() -> rx.Component:
    """Campo + botão pra cadastrar um cliente novo."""
    return rx.hstack(
        rx.input(
            value=AdvisorState.novo_cliente_nome,
            on_change=AdvisorState.set_novo_cliente_nome,
            placeholder="Nome do cliente ou empresa",
            size="3",
            width="100%",
        ),
        rx.button(
            rx.icon("plus", size=18),
            "Adicionar",
            on_click=AdvisorState.criar_cliente,
            background_color=COR_NAVY,
            color="white",
            size="3",
            cursor="pointer",
            flex_shrink="0",
        ),
        width="100%",
        spacing="2",
    )


def _clientes_vazio() -> rx.Component:
    """Estado vazio da lista de clientes — nenhum cadastrado ainda."""
    return rx.vstack(
        rx.icon("users", size=32, color="var(--gray-8)"),
        rx.text("Nenhum cliente cadastrado ainda.", color="var(--gray-9)", size="2"),
        spacing="2",
        align_items="center",
        justify="center",
        padding_y="2em",
        width="100%",
    )


def clientes_panel() -> rx.Component:
    """Tela de seleção/cadastro de clientes do modo Assessor Financeiro
    (multiempresa) — aparece antes de qualquer dashboard/chat, porque antes
    é preciso dizer QUAL cliente (cada um com seu próprio session_id, então
    os dados nunca se misturam)."""
    return rx.vstack(
        rx.hstack(
            rx.heading("Clientes", size="6", color="#1a2540"),
            rx.spacer(),
            rx.button(
                "Trocar de modo",
                on_click=AdvisorState.trocar_modo,
                variant="ghost",
                size="2",
                color=COR_NAVY,
                cursor="pointer",
            ),
            width="100%",
            align_items="center",
        ),
        _card(_novo_cliente_form()),
        _card(
            rx.cond(
                AdvisorState.clientes.length() > 0,
                rx.vstack(
                    rx.foreach(AdvisorState.clientes, _cliente_row),
                    width="100%",
                    spacing="1",
                ),
                _clientes_vazio(),
            ),
        ),
        width="100%",
        max_width="520px",
        spacing="4",
        padding="2em 1.5em",
        align_items="stretch",
    )

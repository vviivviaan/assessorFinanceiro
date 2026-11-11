"""Estado (controller) da aplicação Reflex.

Conecta a UI ao banco de dados e aos agentes de IA. Não contém nenhum
componente visual nem acesso direto ao banco — ambos ficam em `ui/` e
`core/transaction_repository.py`, respectivamente.
"""
import csv
import datetime
import io
import uuid
from pathlib import Path
from typing import Any

import reflex as rx

from assessor_financeiro.auth_state import AuthMixin
from assessor_financeiro.core.auth_service import session_id_pessoal
from assessor_financeiro.llm.model_factory import provedor_tem_chave
from assessor_financeiro.core.transaction_repository import (
    add_chat_message,
    add_transactions,
    clear_session_data,
    create_cliente,
    create_conversa,
    delete_conversa,
    get_chat_history,
    get_transactions,
    list_clientes,
    list_conversas,
    rename_conversa,
    TITULO_PADRAO_CONVERSA,
)
from assessor_financeiro.core.transaction_service import (
    summarize_transactions,
    formatar_reais,
    listar_transacoes_detalhadas,
    montar_opcoes_de_mes,
    filtrar_e_agrupar_transacoes,
    calcular_relatorio_mensal,
    categorias_por_mes,
    gerar_insight_textual,
    parse_data_flexivel,
    ItemTransacao,
    GrupoTransacoes,
    OpcaoMes,
    RelatorioMensal,
)
from assessor_financeiro.core.categorizacao import categoria_ou_descricao
from assessor_financeiro.core.file_import_service import (
    FORMATOS_SUPORTADOS,
    ORIGEM_EXTRATO,
    ORIGEM_FATURA,
    ErroImportacao,
    extrair_texto_pdf,
    parse_extrato_com_resumo,
)
from assessor_financeiro.core.telemetry import log_llm_call
from assessor_financeiro.core.open_finance.mock_client import (
    ConsentimentoNaoAutorizado,
    OpenFinanceMockClient,
)
from assessor_financeiro.core.open_finance.importer import transacao_ofb_para_transacao_app
from assessor_financeiro.core.open_finance.schemas import Permissao
from assessor_financeiro.agents.advisor_agent import get_financial_advisor
from assessor_financeiro.agents.extractor_agent import get_data_extractor_agent
from assessor_financeiro.config import (
    ADVISOR_LLM_PROVIDER,
    API_KEY_ENV_VARS,
    DEFAULT_SESSION_ID,
    EXTRACTOR_LLM_PROVIDER,
    MODO_MULTIEMPRESA,
    MODO_PESSOAL,
)
from assessor_financeiro.llm.fallback import run_with_fallback

MENSAGEM_BOAS_VINDAS = (
    "Olá! 👋 Sou a vivIA, sua Assessora Financeira Pessoal. "
    "O que te faz feliz no tempo livre?"
)


MENSAGEM_SEM_CHAVE = (
    "🔑 Para conversar comigo, cadastre sua chave de API (Groq, OpenAI, "
    "Google ou, opcionalmente, Claude) em **Configurações** — o ícone de chave "
    "no topo da tela."
)


class AdvisorState(AuthMixin, rx.State):
    chat_history: list[dict[str, str]] = []
    chart_data: list[dict[str, Any]] = []
    category_list: list[dict[str, Any]] = []
    database_summary: str = ""

    # --- Modo de uso: Pessoal x Assessor Financeiro multiempresa (Fase 7) ---
    # `modo_app` fica salvo no localStorage do navegador (sobrevive a um
    # F5/reinício do reflex run); "" significa "ainda não escolheu" e mostra
    # a tela de onboarding (ver `ui/pages.py`). `session_id_ativo` é quem
    # efetivamente isola os dados no banco — no modo Pessoal é sempre
    # `DEFAULT_SESSION_ID`; no multiempresa, é o session_id do cliente
    # selecionado (fica vazio, sem persistir entre recarregamentos, até a
    # usuária escolher um cliente na lista).
    modo_app: str = rx.LocalStorage("", name="vivia_modo_app")
    session_id_ativo: str = ""
    cliente_ativo_nome: str = ""
    clientes: list[dict[str, str]] = []
    novo_cliente_nome: str = ""

    # --- Conversas do chat (Fase 5) ---
    # Cada perfil (Pessoal ou cliente) tem várias conversas; as transações
    # são do perfil e valem para todas, só o histórico do chat muda.
    # "" é um id válido: é a "Conversa inicial" (histórico anterior ao recurso).
    conversa_ativa_id: str = ""
    conversa_ativa_titulo: str = ""
    conversas: list[dict[str, str]] = []
    mostrar_conversas: bool = False

    saldo_atual: float = 0.0
    saldo_fmt: str = "R$ 0,00"
    receitas_fmt: str = "R$ 0,00"
    gastos_fmt: str = "R$ 0,00"
    total_receitas: float = 0.0
    total_gastos: float = 0.0

    # --- Aba de Transações (Fase 6, item 4) ---
    # Tipos concretos (TypedDict), não `dict[str, Any]`: o `rx.foreach` da aba
    # de Transações é aninhado (grupo -> itens do grupo), e o Reflex só
    # consegue iterar o nível interno se souber o tipo exato da lista.
    transacoes_todas: list[ItemTransacao] = []
    ultimas_transacoes: list[ItemTransacao] = []
    transacoes_agrupadas: list[GrupoTransacoes] = []
    meses_disponiveis: list[OpcaoMes] = []
    filtro_transacoes_tipo: str = "Todas"
    filtro_transacoes_mes: str = "Todos"

    # --- Aba de Relatórios (Fase 6, item 5) ---
    relatorio_mensal: list[RelatorioMensal] = []
    insight_texto: str = ""

    # Mês selecionado no gráfico de barras (clique) — filtra o donut abaixo
    relatorio_mes_selecionado: str = ""       # "YYYY-MM" ou "" (geral)
    relatorio_mes_label: str = ""             # ex.: "Jun/26" (para o título)
    relatorio_chart_data_mes: list[dict[str, Any]] = []
    relatorio_category_list_mes: list[dict[str, Any]] = []
    relatorio_gastos_fmt_mes: str = "R$ 0,00"

    @rx.var
    def relatorio_mensal_destaque(self) -> list[dict[str, Any]]:
        """Dados do gráfico de barras com o mês selecionado separado em
        séries próprias (`EntradasSel`/`SaidasSel`), pra poder pintá-lo de
        outra cor. Os valores que não se aplicam ficam None (não aparecem
        nem no gráfico nem no tooltip)."""
        sel = self.relatorio_mes_selecionado
        saida: list[dict[str, Any]] = []
        for p in self.relatorio_mensal:
            marcado = bool(sel) and p["chave"] == sel
            saida.append({
                "mes": p["mes"],
                "Entradas": None if marcado else p["Entradas"],
                "EntradasSel": p["Entradas"] if marcado else None,
                "Saidas": None if marcado else p["Saidas"],
                "SaidasSel": p["Saidas"] if marcado else None,
            })
        return saida

    @rx.var
    def percentual_gasto(self) -> int:
        """Percentual do quanto já foi gasto em relação ao total recebido —
        usado na barra de progresso do card de resumo do Dashboard (Fase 7)."""
        if self.total_receitas <= 0:
            return 0
        return min(int(round((self.total_gastos / self.total_receitas) * 100)), 100)

    is_loading: bool = False
    is_uploading: bool = False

    # O que o arquivo enviado representa: "extrato" (conta) ou "fatura" (cartão).
    origem_importacao: str = ORIGEM_EXTRATO

    def set_origem_importacao(self, valor: str | list[str]):
        if isinstance(valor, list):  # o segmented_control pode mandar lista
            valor = valor[0] if valor else ORIGEM_EXTRATO
        self.origem_importacao = valor if valor in (ORIGEM_EXTRATO, ORIGEM_FATURA) else ORIGEM_EXTRATO

    def on_load(self):
        """Chamado uma vez quando a página carrega. Não sabe ainda se é
        modo Pessoal ou Assessor Financeiro (isso só chega do navegador via
        `modo_app`, salvo no localStorage): Pessoal entra direto nos dados;
        multiempresa carrega a lista de clientes; sem modo nenhum escolhido
        ainda (primeira visita), não faz nada — `ui/pages.py` mostra a tela
        de onboarding nesse caso."""
        if not self._restaurar_login():
            return  # sem login: ui/pages.py mostra a tela de entrada
        self._pos_login()

    def _pos_login(self):
        """Depois de entrar (ou de retomar o login): abre o que corresponde
        ao modo salvo — Pessoal já com os dados; multiempresa com a lista
        de clientes; sem modo ainda, a tela de onboarding."""
        if self.modo_app == MODO_PESSOAL:
            self.session_id_ativo = session_id_pessoal(self.usuario_id)
            self._entrar_na_sessao()
        elif self.modo_app == MODO_MULTIEMPRESA:
            self.carregar_clientes()

    def _limpar_dados_em_memoria(self):
        """Ao sair: não deixa chat/valores da usuária anterior no estado."""
        self.session_id_ativo = ""
        self.cliente_ativo_nome = ""
        self.clientes = []
        self.chat_history = []
        self.chart_data = []
        self.category_list = []
        self.database_summary = ""
        self.transacoes_todas = []
        self.ultimas_transacoes = []
        self.transacoes_agrupadas = []
        self.meses_disponiveis = []
        self.relatorio_mensal = []
        self.insight_texto = ""
        self.relatorio_mes_selecionado = ""
        self.relatorio_mes_label = ""
        self.relatorio_chart_data_mes = []
        self.relatorio_category_list_mes = []
        self.relatorio_gastos_fmt_mes = "R$ 0,00"
        self.saldo_fmt = self.receitas_fmt = self.gastos_fmt = "R$ 0,00"
        self.saldo_atual = self.total_receitas = self.total_gastos = 0.0
        self._esquecer_conversas()

    def _carregar_dados_sessao(self):
        """Carrega e recalcula os dados do banco (chat + transações) para
        `session_id_ativo` — Pessoal sempre usa `DEFAULT_SESSION_ID`; no
        modo multiempresa, cada cliente tem o seu (ver `selecionar_cliente`).
        """
        messages = self._get_chat_history()
        if not messages:
            self._add_chat_message(role="agent", content=MENSAGEM_BOAS_VINDAS)
            messages = self._get_chat_history()

        self.chat_history = [{"role": m.role, "content": m.content} for m in messages]

        transactions = self._get_transactions()
        summary = summarize_transactions(transactions)
        self.chart_data = summary.chart_data
        self.category_list = summary.category_list_fmt
        self.database_summary = summary.as_text
        self.saldo_atual = summary.saldo_atual
        self.saldo_fmt = summary.saldo_fmt
        self.receitas_fmt = summary.receitas_fmt
        self.gastos_fmt = summary.gastos_fmt
        self.total_receitas = summary.total_receitas
        self.total_gastos = summary.total_gastos

        self.transacoes_todas = listar_transacoes_detalhadas(transactions)
        self.ultimas_transacoes = self.transacoes_todas[:5]
        self.meses_disponiveis = montar_opcoes_de_mes(self.transacoes_todas)
        self._recalcular_transacoes_view()

        self.relatorio_mensal = calcular_relatorio_mensal(transactions)
        self.insight_texto = gerar_insight_textual(transactions)
        self.relatorio_mes_selecionado = ""
        self.relatorio_mes_label = ""
        self.relatorio_chart_data_mes = []
        self.relatorio_category_list_mes = []
        self.relatorio_gastos_fmt_mes = "R$ 0,00"

    def selecionar_mes_relatorio(self, data: dict[str, Any]):
        """Handler do clique no gráfico de barras — filtra categorias pelo mês clicado.

        O Recharts envia o estado do gráfico (`activeTooltipIndex`/`activeLabel`);
        se clicar no mesmo mês já selecionado, volta para a visão geral (toggle).
        """
        if not data or not isinstance(data, dict):
            return
        ponto = None
        idx = data.get("activeTooltipIndex", data.get("activeIndex"))
        try:
            ponto = self.relatorio_mensal[int(idx)]
        except (TypeError, ValueError, IndexError):
            rotulo = data.get("activeLabel")
            ponto = next((p for p in self.relatorio_mensal if p["mes"] == rotulo), None)
        if not ponto:
            return
        chave = ponto["chave"]
        label = ponto["mes"]

        # Toggle: clicar de novo no mesmo mês limpa a seleção
        if chave == self.relatorio_mes_selecionado:
            self.relatorio_mes_selecionado = ""
            self.relatorio_mes_label = ""
            self.relatorio_chart_data_mes = []
            self.relatorio_category_list_mes = []
            self.relatorio_gastos_fmt_mes = "R$ 0,00"
            return

        transactions = self._get_transactions()
        chart_data, cat_list, gastos_fmt = categorias_por_mes(transactions, chave)
        self.relatorio_mes_selecionado = chave
        self.relatorio_mes_label = label
        self.relatorio_chart_data_mes = chart_data
        self.relatorio_category_list_mes = cat_list
        self.relatorio_gastos_fmt_mes = gastos_fmt

    def limpar_selecao_mes_relatorio(self):
        """Botão 'Ver geral' — volta a mostrar todas as categorias."""
        self.relatorio_mes_selecionado = ""
        self.relatorio_mes_label = ""
        self.relatorio_chart_data_mes = []
        self.relatorio_category_list_mes = []
        self.relatorio_gastos_fmt_mes = "R$ 0,00"

    # --- Wrappers de repositório escopados pra `session_id_ativo` ---
    # Toda chamada ao banco passa por aqui em vez de usar o
    # `DEFAULT_SESSION_ID` implícito dos módulos de `core/` — é essa troca
    # que faz o mesmo chat/transações/relatórios que já existiam servirem
    # tanto o modo Pessoal quanto cada cliente do modo multiempresa, sem
    # duplicar nenhuma tela.

    def _get_chat_history(self):
        return get_chat_history(self.session_id_ativo, self.conversa_ativa_id)

    def _add_chat_message(self, role: str, content: str):
        add_chat_message(
            role=role,
            content=content,
            session_id=self.session_id_ativo,
            conversa_id=self.conversa_ativa_id,
        )

    def _get_transactions(self):
        return get_transactions(self.session_id_ativo)

    def _add_transactions(self, items: list[dict]):
        add_transactions(items, session_id=self.session_id_ativo)

    def _clear_session_data(self):
        clear_session_data(self.session_id_ativo)

    # --- Modo de uso + clientes (Fase 7) ---

    def escolher_modo(self, modo: str):
        """Define o modo de uso (chamado pelos dois cards da tela de
        onboarding) e já carrega o que for preciso pra cada um."""
        self.modo_app = modo
        if modo == MODO_PESSOAL:
            self.session_id_ativo = session_id_pessoal(self.usuario_id)
            self._entrar_na_sessao()
        else:
            self.session_id_ativo = ""
            self.carregar_clientes()

    def trocar_modo(self):
        """Volta pra tela de escolha de modo (onboarding)."""
        self.modo_app = ""
        self.session_id_ativo = ""
        self.cliente_ativo_nome = ""
        self._esquecer_conversas()

    def carregar_clientes(self):
        """Recarrega a lista de clientes cadastrados no modo multiempresa."""
        self.clientes = [
            {"nome": c.nome, "session_id": c.session_id} for c in list_clientes(self.usuario_id)
        ]

    def set_novo_cliente_nome(self, valor: str):
        self.novo_cliente_nome = valor

    def criar_cliente(self):
        """Cadastra um cliente novo (com um session_id só dele) e já entra
        nele, igual acontece quando você seleciona um cliente existente."""
        nome = self.novo_cliente_nome.strip()
        if not nome:
            return
        novo_session_id = f"cliente_{uuid.uuid4().hex[:12]}"
        cliente = create_cliente(
            nome=nome, session_id=novo_session_id, usuario_id=self.usuario_id
        )
        self.novo_cliente_nome = ""
        self.carregar_clientes()
        self.selecionar_cliente(cliente.session_id, cliente.nome)

    def selecionar_cliente(self, session_id: str, nome: str):
        """Entra no espaço de um cliente — chat, transações e relatórios
        passam a ser só dele (mesmas telas do modo Pessoal, reaproveitadas)."""
        self.session_id_ativo = session_id
        self.cliente_ativo_nome = nome
        self._entrar_na_sessao()

    def voltar_para_clientes(self):
        """Sai do cliente atual e volta pra lista, sem trocar de modo."""
        self.session_id_ativo = ""
        self.cliente_ativo_nome = ""
        self._esquecer_conversas()
        self.carregar_clientes()

    # --- Conversas (Fase 5) ---

    def _esquecer_conversas(self):
        self.conversa_ativa_id = ""
        self.conversa_ativa_titulo = ""
        self.conversas = []
        self.mostrar_conversas = False

    def _carregar_conversas(self):
        """Atualiza a lista de conversas do perfil ativo e o título da ativa."""
        self.conversas = [
            {"conversa_id": c.conversa_id, "titulo": c.titulo}
            for c in list_conversas(self.session_id_ativo)
        ]
        self.conversa_ativa_titulo = next(
            (c["titulo"] for c in self.conversas if c["conversa_id"] == self.conversa_ativa_id),
            "",
        )

    def _entrar_na_sessao(self):
        """Ao entrar num perfil (Pessoal ou cliente): abre a conversa mais
        recente e carrega os dados."""
        self.conversa_ativa_id = ""
        self.mostrar_conversas = False
        self._carregar_conversas()
        if self.conversas:
            self.conversa_ativa_id = self.conversas[0]["conversa_id"]
            self._carregar_conversas()
        self._carregar_dados_sessao()

    def alternar_conversas(self):
        """Abre/fecha a lista de conversas no topo do chat."""
        self.mostrar_conversas = not self.mostrar_conversas

    def nova_conversa(self):
        """Cria uma conversa em branco no perfil ativo e passa a usá-la."""
        if self.is_loading or self.is_uploading:
            return
        nova = create_conversa(
            self.session_id_ativo, conversa_id=uuid.uuid4().hex[:12]
        )
        self.conversa_ativa_id = nova.conversa_id
        self.mostrar_conversas = False
        self._carregar_conversas()
        self._carregar_dados_sessao()

    def selecionar_conversa(self, conversa_id: str):
        """Abre uma conversa antiga."""
        if self.is_loading or self.is_uploading:
            return
        self.conversa_ativa_id = conversa_id
        self.mostrar_conversas = False
        self._carregar_conversas()
        self._carregar_dados_sessao()

    def excluir_conversa(self, conversa_id: str):
        """Apaga uma conversa (e só as mensagens dela — as transações ficam)."""
        if self.is_loading or self.is_uploading:
            return
        delete_conversa(self.session_id_ativo, conversa_id)
        if conversa_id == self.conversa_ativa_id:
            self.conversa_ativa_id = ""
            self._carregar_conversas()  # recria a inicial se não sobrou nenhuma
            if self.conversas:
                self.conversa_ativa_id = self.conversas[0]["conversa_id"]
        self._carregar_conversas()
        self._carregar_dados_sessao()

    def _titular_conversa_se_nova(self, primeira_mensagem: str):
        """A conversa nasce como "Nova conversa"; na primeira mensagem da
        usuária ela ganha um título tirado dessa mensagem."""
        if self.conversa_ativa_titulo != TITULO_PADRAO_CONVERSA:
            return
        titulo = " ".join(primeira_mensagem.split())
        if len(titulo) > 40:
            titulo = titulo[:40].rstrip() + "…"
        rename_conversa(self.session_id_ativo, self.conversa_ativa_id, titulo)
        self._carregar_conversas()

    def set_filtro_tipo(self, valor: str):
        """Muda o filtro de tipo (Todas/Entradas/Saidas) na aba de Transações."""
        self.filtro_transacoes_tipo = valor
        self._recalcular_transacoes_view()

    def set_filtro_mes(self, valor: str):
        """Muda o filtro de mês na aba de Transações."""
        self.filtro_transacoes_mes = valor
        self._recalcular_transacoes_view()

    def _recalcular_transacoes_view(self):
        """Reaplica os filtros atuais sobre `transacoes_todas` e atualiza a lista
        agrupada por dia exibida na aba de Transações."""
        self.transacoes_agrupadas = filtrar_e_agrupar_transacoes(
            self.transacoes_todas,
            tipo=self.filtro_transacoes_tipo,
            mes=self.filtro_transacoes_mes,
        )

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Lê o arquivo enviado (CSV, XLSX, OFX ou PDF) e salva as transações no banco.

        Formatos tabulares (CSV/XLSX/OFX) têm colunas fixas e um parser
        determinístico. PDF de extrato não tem tabela fixa (varia por banco),
        então o texto extraído é interpretado pelo mesmo agente extrator (LLM)
        que já processa o texto do chat.
        """
        self.is_uploading = True

        origem = self.origem_importacao
        rotulo = "fatura do cartão" if origem == ORIGEM_FATURA else "extrato"
        pagamentos_ignorados = 0
        self._add_chat_message(role="user", content=f"📤 **Enviando {rotulo}**...")
        self._carregar_dados_sessao()
        yield

        try:
            self._add_chat_message(
                role="agent", content="⏳ **Processando** seu arquivo de transações..."
            )
            yield

            file = files[0]
            raw_bytes = await file.read()
            extensao = Path(file.name).suffix.lower()

            if extensao not in FORMATOS_SUPORTADOS:
                self._add_chat_message(
                    role="agent",
                    content=(
                        f"❌ Formato '{extensao}' não suportado. Envie um arquivo "
                        "CSV, XLSX, OFX/QFX ou PDF."
                    ),
                )
                self._carregar_dados_sessao()
                self.is_uploading = False
                return

            if extensao == ".pdf":
                texto = extrair_texto_pdf(raw_bytes)
                if origem == ORIGEM_FATURA:
                    texto = (
                        "ATENÇÃO: o texto abaixo é uma FATURA DE CARTÃO DE CRÉDITO. "
                        "Cada compra é um gasto (type Debito) com a data da compra; "
                        "estornos e créditos são type Credito; IGNORE linhas de "
                        "pagamento da fatura, saldo anterior, limites e totais.\n\n"
                        + texto
                    )
                chaves = self._chaves_decifradas()
                response, _ = run_with_fallback(
                    lambda provider: get_data_extractor_agent(provider, api_keys=chaves),
                    EXTRACTOR_LLM_PROVIDER,
                    texto,
                )
                if response is None:
                    log_llm_call(
                        "extractor",
                        provider_fallback=EXTRACTOR_LLM_PROVIDER,
                        success=False,
                        error="agente extrator não respondeu ao processar o PDF",
                    )
                    raise RuntimeError("Nenhum provedor de IA disponível para ler o PDF.")

                lista_extraida = response.content
                schema_valido = hasattr(lista_extraida, "gastos")
                log_llm_call("extractor", response=response, success=schema_valido)
                novas_transacoes = (
                    self._gastos_para_transacoes(lista_extraida.gastos) if schema_valido else []
                )
            else:
                df, pagamentos_ignorados = parse_extrato_com_resumo(
                    file.name, raw_bytes, origem
                )
                novas_transacoes = []
                for linha in df.itertuples(index=False):
                    transacao = {
                        "category": categoria_ou_descricao(linha.descricao),
                        "amount": abs(float(linha.valor)),
                        "type": linha.tipo,
                    }
                    data_dt = parse_data_flexivel(getattr(linha, "data", None))
                    if data_dt is not None:
                        transacao["created_at"] = data_dt
                    novas_transacoes.append(transacao)

            if not novas_transacoes:
                self._add_chat_message(
                    role="agent",
                    content="🤔 Não encontrei nenhuma transação reconhecível nesse arquivo.",
                )
            else:
                self._add_transactions(novas_transacoes)
                self._add_chat_message(
                    role="agent",
                    content=self._resumo_importacao(
                        rotulo, novas_transacoes, pagamentos_ignorados
                    ),
                )

        except ErroImportacao as e:
            self._add_chat_message(role="agent", content=f"❌ {e}")
        except Exception as e:
            print("Erro no upload:", e)
            self._add_chat_message(
                role="agent",
                content="❌ Ocorreu um erro ao tentar salvar os dados da sua planilha... Tente novamente.",
            )

        self._carregar_dados_sessao()
        self.is_uploading = False

    @staticmethod
    def _resumo_importacao(rotulo: str, transacoes: list[dict], pagamentos_ignorados: int) -> str:
        """Texto de confirmação depois de importar um extrato/fatura: quantas
        transações entraram e como ficaram distribuídas por categoria."""
        contagem: dict[str, int] = {}
        for t in transacoes:
            contagem[t["category"]] = contagem.get(t["category"], 0) + 1
        principais = sorted(contagem.items(), key=lambda item: item[1], reverse=True)[:5]
        categorias = ", ".join(f"{nome} ({qtd})" for nome, qtd in principais)

        texto = (
            f"✅ **Importação concluída** ({rotulo})! {len(transacoes)} "
            f"transação(ões) adicionada(s) — o painel já foi atualizado."
        )
        if categorias:
            texto += f"\n\nCategorias: {categorias}."
        if pagamentos_ignorados:
            texto += (
                f"\n\nIgnorei {pagamentos_ignorados} linha(s) de pagamento da fatura "
                "(esse valor já aparece como gasto no extrato da conta)."
            )
        return texto

    def conectar_open_finance(self):
        """PoC: importação automática de transações via Open Finance Brasil.

        O app não é uma instituição credenciada no Diretório de Participantes
        (sem certificado ICP-Brasil), então uma chamada real às APIs de
        produção não é possível. `OpenFinanceMockClient` simula o fluxo
        oficial (consentimento -> autorização -> contas -> transações) com o
        mesmo formato de campos/enums da especificação real — trocar por uma
        instituição de verdade significa reimplementar só aquele cliente.
        """
        self.is_uploading = True
        self._add_chat_message(role="user", content="🏦 **Conectar Open Finance** solicitado.")
        self._carregar_dados_sessao()
        yield

        cliente = OpenFinanceMockClient()
        try:
            self._add_chat_message(
                role="agent",
                content=(
                    "1/4 · Criando consentimento (permissões: leitura de contas "
                    "e de transações)..."
                ),
            )
            yield
            consentimento = cliente.criar_consentimento(
                permissoes=[Permissao.ACCOUNTS_READ, Permissao.ACCOUNTS_TRANSACTIONS_READ],
            )

            self._add_chat_message(
                role="agent",
                content=(
                    f"2/4 · Consentimento `{consentimento.consentId}` criado. Em produção, "
                    "você seria redirecionada agora para o app do seu banco pra autorizar "
                    "o compartilhamento — simulando essa autorização..."
                ),
            )
            yield
            cliente.autorizar_consentimento(consentimento.consentId)

            self._add_chat_message(role="agent", content="3/4 · Consentimento autorizado! Consultando contas...")
            yield
            conta = cliente.listar_contas(consentimento.consentId)[0]

            self._add_chat_message(
                role="agent",
                content=(
                    f"4/4 · Importando transações de {conta.brandName} "
                    f"(ag. {conta.branchCode} / cc {conta.number}-{conta.checkDigit})..."
                ),
            )
            yield
            transacoes_ofb = cliente.listar_transacoes(consentimento.consentId, conta.accountId)
            novas_transacoes = [transacao_ofb_para_transacao_app(t) for t in transacoes_ofb]
            self._add_transactions(novas_transacoes)

            self._add_chat_message(
                role="agent",
                content=(
                    f"✅ **Importação concluída!** {len(novas_transacoes)} transações trazidas "
                    "via Open Finance."
                ),
            )

        except ConsentimentoNaoAutorizado as e:
            self._add_chat_message(role="agent", content=f"❌ Consentimento recusado: {e}")
        except Exception as e:
            print("Erro na PoC de Open Finance:", e)
            self._add_chat_message(
                role="agent",
                content="❌ Não consegui concluir a conexão com o Open Finance. Tente novamente.",
            )

        self._carregar_dados_sessao()
        self.is_uploading = False

    @staticmethod
    def _parse_data_extraida(data_str: str | None) -> "datetime.datetime | None":
        """Converte a string 'AAAA-MM-DD' que o agente extrator devolve (só
        quando o usuário menciona uma data) num `datetime`. Retorna None se
        não veio data nenhuma, ou se veio num formato inesperado — nesses
        casos o banco usa o padrão dele (`created_at` = agora) em vez de
        quebrar o registro da transação."""
        if not data_str:
            return None
        try:
            return datetime.datetime.strptime(data_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _gastos_para_transacoes(gastos: list) -> list[dict]:
        """Converte a lista de `ItemGasto` (schema do agente extrator) para o
        formato aceito por `add_transactions` ({"category", "amount", "type"}
        e, quando o usuário mencionou uma data — ex.: "dia 12 de agosto" —,
        também "created_at", pra a transação cair no mês certo do relatório
        em vez de sempre cair em "hoje")."""
        resultado = []
        for item in gastos:
            transacao = {
                "category": item.category,
                "amount": abs(float(item.amount)),
                "type": item.type,
            }
            data_dt = AdvisorState._parse_data_extraida(getattr(item, "data", None))
            if data_dt is not None:
                transacao["created_at"] = data_dt
            resultado.append(transacao)
        return resultado

    @staticmethod
    def _formatar_confirmacao(itens: list[dict]) -> str:
        """Monta o texto do card de confirmação exibido no chat quando o agente
        extrator reconhece e salva novas transações automaticamente."""
        linhas = "\n".join(
            f"- {item['category']}: {formatar_reais(item['amount'])} "
            f"({'Recebimento' if item['type'] == 'Credito' else 'Gasto'})"
            for item in itens
        )
        plural = "transações" if len(itens) > 1 else "transação"
        return f"✅ **{len(itens)} {plural} registrada(s):**\n{linhas}"

    def extract_transactions_from_text(self, text: str) -> list[dict]:
        """Passo 1 da orquestração: roda o agente extrator para 'pescar' gastos do chat.

        Retorna a lista de transações novas já salvas no banco (ou [] se nada
        foi extraído ou se o agente falhou), para que `submit_message` possa
        exibir um card de confirmação no chat.
        """
        chaves = self._chaves_decifradas()
        response, _ = run_with_fallback(
            lambda provider: get_data_extractor_agent(provider, api_keys=chaves),
            EXTRACTOR_LLM_PROVIDER,
            text,
        )

        if response is None:
            log_llm_call(
                "extractor",
                provider_fallback=EXTRACTOR_LLM_PROVIDER,
                success=False,
                error="agente extrator não respondeu (principal e fallback falharam)",
            )
            print("Erro ao chamar o agente extrator (principal e fallback falharam)")
            return []

        try:
            # Com output_schema, response.content já é a instância de ListaGastos (Pydantic)
            lista_extraida = response.content
            schema_valido = hasattr(lista_extraida, "gastos")

            if schema_valido and lista_extraida.gastos:
                novas_transacoes = self._gastos_para_transacoes(lista_extraida.gastos)
                self._add_transactions(novas_transacoes)
                self._carregar_dados_sessao()  # Atualiza o dashboard e o resumo do banco
                log_llm_call("extractor", response=response, success=schema_valido)
                return novas_transacoes

            # Uma lista vazia também é um resultado válido (mensagem sem
            # transação nova) — só conta como falha se o schema veio quebrado.
            log_llm_call("extractor", response=response, success=schema_valido)
            return []

        except Exception as e:
            log_llm_call("extractor", response=response, success=False, error=str(e))
            print(f"Erro ao extrair e salvar transações estruturadas: {e}")
            return []

    def submit_message(self, form_data: dict):
        """Recebe os dados do formulário quando o usuário aperta Enter ou clica em Enviar."""
        user_query = form_data.get("chat_input", "")

        if not user_query.strip():
            return

        chaves = self._chaves_decifradas()
        if not any(provedor_tem_chave(p, chaves) for p in API_KEY_ENV_VARS):
            self._add_chat_message(role="user", content=user_query)
            self._add_chat_message(role="agent", content=MENSAGEM_SEM_CHAVE)
            self._carregar_dados_sessao()
            return

        historico_formatado = "\n".join(
            f"{msg['role'].upper()}: {msg['content']}" for msg in self.chat_history
        )

        self.chat_history.append({"role": "user", "content": user_query})
        self._add_chat_message(role="user", content=user_query)
        self._titular_conversa_se_nova(user_query)
        self._carregar_dados_sessao()

        self.is_loading = True
        yield  # Atualiza a nova mensagem enviada no chat

        try:
            novas_transacoes = self.extract_transactions_from_text(user_query)

            if novas_transacoes:
                confirmacao = self._formatar_confirmacao(novas_transacoes)
                self.chat_history.append({"role": "confirmation", "content": confirmacao})
                self._add_chat_message(role="confirmation", content=confirmacao)
                yield  # Mostra o card de confirmação antes de chamar o conselheiro

            # Se o usuário cadastrou a chave do Claude (opcional), o conselheiro
            # passa a usá-la por padrão — respostas de maior qualidade. Sem ela,
            # mantém o provedor configurado (ADVISOR_LLM_PROVIDER).
            provider_conselheiro = (
                "anthropic"
                if provedor_tem_chave("anthropic", chaves)
                else ADVISOR_LLM_PROVIDER
            )
            response, _ = run_with_fallback(
                lambda provider: get_financial_advisor(
                    financial_data=self.database_summary,
                    chat_history=historico_formatado,
                    provider=provider,
                    api_keys=chaves,
                ),
                provider_conselheiro,
                user_query,
            )
            if response is None:
                log_llm_call(
                    "advisor",
                    provider_fallback=provider_conselheiro,
                    success=False,
                    error="agente conselheiro não respondeu (principal e fallback falharam)",
                )
                raise RuntimeError("Nenhum provedor de IA disponível no momento.")

            log_llm_call("advisor", response=response)
            resposta_limpa = self._sanitize_markdown(response.content)

            self.chat_history.append({"role": "agent", "content": resposta_limpa})
            self._add_chat_message(role="agent", content=resposta_limpa)

        except Exception as e:
            error_msg = f"Erro de comunicação: {str(e)}"
            self.chat_history.append({"role": "agent", "content": error_msg})

        self.is_loading = False
        yield  # Remove o loading

    @staticmethod
    def _sanitize_markdown(texto: str) -> str:
        """Remove delimitadores de LaTeX que o modelo às vezes inclui na resposta.

        A renderização de matemática (KaTeX) foi desligada no componente
        `rx.markdown` (ui/components.py), então o "$" não precisa mais de
        escape aqui — só limpamos os delimitadores \\(...\\) e \\[...\\].
        """
        for delimitador in ["\\(", "\\)", "\\[", "\\]"]:
            texto = texto.replace(delimitador, "")
        return texto

    def exportar_relatorio_csv(self):
        """Gera um CSV com todas as transações da sessão/cliente ativo e
        dispara o download no navegador — botão "Exportar" da aba
        Relatórios (Fase 7), pra tirar um relatório do que foi registrado
        pelo chat (ou por upload/Open Finance) sem precisar olhar o app."""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Data", "Hora", "Categoria", "Tipo", "Valor (R$)"])
        for item in self.transacoes_todas:
            writer.writerow([
                item["data_iso"] if item["data_iso"] != "sem-data" else "",
                item["hora"],
                item["category"],
                "Receita" if item["is_credito"] else "Gasto",
                item["amount_fmt_signed"],
            ])

        nome_arquivo = "relatorio_vivIA.csv"
        if self.modo_app == MODO_MULTIEMPRESA and self.cliente_ativo_nome:
            slug = "".join(
                ch if ch.isalnum() else "_" for ch in self.cliente_ativo_nome.strip()
            )
            nome_arquivo = f"relatorio_{slug}.csv"

        # BOM UTF-8 no início: sem isso, o Excel no Windows costuma exibir
        # acentuação quebrada ao abrir o CSV diretamente.
        return rx.download(data="\ufeff" + buffer.getvalue(), filename=nome_arquivo)

    def clear_chat(self):
        """Apaga o histórico do chat e as transações do banco de dados."""
        self._clear_session_data()
        self._entrar_na_sessao()

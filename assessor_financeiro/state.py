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

from assessor_financeiro.core.transaction_repository import (
    add_chat_message,
    add_transactions,
    clear_session_data,
    create_cliente,
    get_chat_history,
    get_transactions,
    list_clientes,
)
from assessor_financeiro.core.transaction_service import (
    summarize_transactions,
    formatar_reais,
    listar_transacoes_detalhadas,
    montar_opcoes_de_mes,
    filtrar_e_agrupar_transacoes,
    calcular_relatorio_mensal,
    gerar_insight_textual,
    parse_data_flexivel,
    ItemTransacao,
    GrupoTransacoes,
    OpcaoMes,
    RelatorioMensal,
)
from assessor_financeiro.core.file_import_service import (
    FORMATOS_SUPORTADOS,
    extrair_texto_pdf,
    parse_extrato_tabular,
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


class AdvisorState(rx.State):
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

    @rx.var
    def percentual_gasto(self) -> int:
        """Percentual do quanto já foi gasto em relação ao total recebido —
        usado na barra de progresso do card de resumo do Dashboard (Fase 7)."""
        if self.total_receitas <= 0:
            return 0
        return min(int(round((self.total_gastos / self.total_receitas) * 100)), 100)

    is_loading: bool = False
    is_uploading: bool = False

    def on_load(self):
        """Chamado uma vez quando a página carrega. Não sabe ainda se é
        modo Pessoal ou Assessor Financeiro (isso só chega do navegador via
        `modo_app`, salvo no localStorage): Pessoal entra direto nos dados;
        multiempresa carrega a lista de clientes; sem modo nenhum escolhido
        ainda (primeira visita), não faz nada — `ui/pages.py` mostra a tela
        de onboarding nesse caso."""
        if self.modo_app == MODO_PESSOAL:
            self.session_id_ativo = DEFAULT_SESSION_ID
            self._carregar_dados_sessao()
        elif self.modo_app == MODO_MULTIEMPRESA:
            self.carregar_clientes()

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

    # --- Wrappers de repositório escopados pra `session_id_ativo` ---
    # Toda chamada ao banco passa por aqui em vez de usar o
    # `DEFAULT_SESSION_ID` implícito dos módulos de `core/` — é essa troca
    # que faz o mesmo chat/transações/relatórios que já existiam servirem
    # tanto o modo Pessoal quanto cada cliente do modo multiempresa, sem
    # duplicar nenhuma tela.

    def _get_chat_history(self):
        return get_chat_history(self.session_id_ativo)

    def _add_chat_message(self, role: str, content: str):
        add_chat_message(role=role, content=content, session_id=self.session_id_ativo)

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
            self.session_id_ativo = DEFAULT_SESSION_ID
            self._carregar_dados_sessao()
        else:
            self.session_id_ativo = ""
            self.carregar_clientes()

    def trocar_modo(self):
        """Volta pra tela de escolha de modo (onboarding)."""
        self.modo_app = ""
        self.session_id_ativo = ""
        self.cliente_ativo_nome = ""

    def carregar_clientes(self):
        """Recarrega a lista de clientes cadastrados no modo multiempresa."""
        self.clientes = [
            {"nome": c.nome, "session_id": c.session_id} for c in list_clientes()
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
        cliente = create_cliente(nome=nome, session_id=novo_session_id)
        self.novo_cliente_nome = ""
        self.carregar_clientes()
        self.selecionar_cliente(cliente.session_id, cliente.nome)

    def selecionar_cliente(self, session_id: str, nome: str):
        """Entra no espaço de um cliente — chat, transações e relatórios
        passam a ser só dele (mesmas telas do modo Pessoal, reaproveitadas)."""
        self.session_id_ativo = session_id
        self.cliente_ativo_nome = nome
        self._carregar_dados_sessao()

    def voltar_para_clientes(self):
        """Sai do cliente atual e volta pra lista, sem trocar de modo."""
        self.session_id_ativo = ""
        self.cliente_ativo_nome = ""
        self.carregar_clientes()

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

        self._add_chat_message(role="user", content="📤 **Enviando arquivo** de transações...")
        self._carregar_dados_sessao()
        yield

        try:
            add_chat_message(
                role="agent", content="⏳ **Processando** seu arquivo de transações..."
            )
            yield

            file = files[0]
            raw_bytes = await file.read()
            extensao = Path(file.name).suffix.lower()

            if extensao not in FORMATOS_SUPORTADOS:
                add_chat_message(
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
                response, _ = run_with_fallback(
                    get_data_extractor_agent, EXTRACTOR_LLM_PROVIDER, texto
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
                df = parse_extrato_tabular(file.name, raw_bytes)
                novas_transacoes = []
                for linha in df.itertuples(index=False):
                    transacao = {
                        "category": linha.descricao,
                        "amount": abs(float(linha.valor)),
                        "type": linha.tipo,
                    }
                    data_dt = parse_data_flexivel(getattr(linha, "data", None))
                    if data_dt is not None:
                        transacao["created_at"] = data_dt
                    novas_transacoes.append(transacao)

            if not novas_transacoes:
                add_chat_message(
                    role="agent",
                    content="🤔 Não encontrei nenhuma transação reconhecível nesse arquivo.",
                )
            else:
                self._add_transactions(novas_transacoes)
                add_chat_message(
                    role="agent",
                    content=(
                        f"✅ **Arquivo processado!** {len(novas_transacoes)} transação(ões) "
                        "adicionada(s) — o painel já foi atualizado."
                    ),
                )

        except Exception as e:
            print("Erro no upload:", e)
            add_chat_message(
                role="agent",
                content="❌ Ocorreu um erro ao tentar salvar os dados da sua planilha... Tente novamente.",
            )

        self._carregar_dados_sessao()
        self.is_uploading = False

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
            add_chat_message(
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

            add_chat_message(
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

            add_chat_message(
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

            add_chat_message(
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
            add_chat_message(
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
        response, _ = run_with_fallback(get_data_extractor_agent, EXTRACTOR_LLM_PROVIDER, text)

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

        historico_formatado = "\n".join(
            f"{msg['role'].upper()}: {msg['content']}" for msg in self.chat_history
        )

        self.chat_history.append({"role": "user", "content": user_query})
        self._add_chat_message(role="user", content=user_query)
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

            response, _ = run_with_fallback(
                lambda provider: get_financial_advisor(
                    financial_data=self.database_summary,
                    chat_history=historico_formatado,
                    provider=provider,
                ),
                ADVISOR_LLM_PROVIDER,
                user_query,
            )
            if response is None:
                log_llm_call(
                    "advisor",
                    provider_fallback=ADVISOR_LLM_PROVIDER,
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
        self._carregar_dados_sessao()

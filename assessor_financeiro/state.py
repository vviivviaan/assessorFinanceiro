"""Estado (controller) da aplicação Reflex.

Conecta a UI ao banco de dados e aos agentes de IA. Não contém nenhum
componente visual nem acesso direto ao banco — ambos ficam em `ui/` e
`core/transaction_repository.py`, respectivamente.
"""
from typing import Any

import reflex as rx

from assessor_financeiro.core.transaction_repository import (
    add_chat_message,
    add_transactions,
    clear_session_data,
    get_chat_history,
    get_transactions,
)
from assessor_financeiro.core.transaction_service import summarize_transactions
from assessor_financeiro.core.csv_import_service import parse_transacoes_csv
from assessor_financeiro.core.telemetry import log_llm_call
from assessor_financeiro.agents.advisor_agent import get_financial_advisor
from assessor_financeiro.agents.extractor_agent import get_data_extractor_agent
from assessor_financeiro.config import EXTRACTOR_LLM_PROVIDER, ADVISOR_LLM_PROVIDER
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

    saldo_atual: float = 0.0
    saldo_fmt: str = "R$ 0,00"
    receitas_fmt: str = "R$ 0,00"
    gastos_fmt: str = "R$ 0,00"

    is_loading: bool = False
    is_uploading: bool = False

    def on_load(self):
        """Carrega e recalcula os dados do banco para o Dashboard e para o Agente."""
        messages = get_chat_history()
        if not messages:
            add_chat_message(role="agent", content=MENSAGEM_BOAS_VINDAS)
            messages = get_chat_history()

        self.chat_history = [{"role": m.role, "content": m.content} for m in messages]

        transactions = get_transactions()
        summary = summarize_transactions(transactions)
        self.chart_data = summary.chart_data
        self.category_list = summary.category_list_fmt
        self.database_summary = summary.as_text
        self.saldo_atual = summary.saldo_atual
        self.saldo_fmt = summary.saldo_fmt
        self.receitas_fmt = summary.receitas_fmt
        self.gastos_fmt = summary.gastos_fmt

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Lê o CSV enviado pelo usuário e salva as transações no banco."""
        self.is_uploading = True

        add_chat_message(role="user", content="📤 **Enviando arquivo** de transações...")
        self.on_load()
        yield

        try:
            add_chat_message(
                role="agent", content="⏳ **Processando** seu arquivo de transações..."
            )
            yield

            file = files[0]
            raw_bytes = await file.read()
            df = parse_transacoes_csv(raw_bytes)

            novas_transacoes = [
                {"category": linha.descricao, "amount": linha.valor, "type": linha.tipo}
                for linha in df.itertuples(index=False)
            ]
            add_transactions(novas_transacoes)

            add_chat_message(
                role="agent", content="✅ **Arquivo processado!** O gráfico já foi atualizado."
            )

        except Exception as e:
            print("Erro no upload:", e)
            add_chat_message(
                role="agent",
                content="❌ Ocorreu um erro ao tentar salvar os dados da sua planilha... Tente novamente.",
            )

        self.on_load()
        self.is_uploading = False

    def extract_transactions_from_text(self, text: str):
        """Passo 1 da orquestração: roda o agente extrator para 'pescar' gastos do chat."""
        response, _ = run_with_fallback(get_data_extractor_agent, EXTRACTOR_LLM_PROVIDER, text)

        if response is None:
            log_llm_call(
                "extractor",
                provider_fallback=EXTRACTOR_LLM_PROVIDER,
                success=False,
                error="agente extrator não respondeu (principal e fallback falharam)",
            )
            print("Erro ao chamar o agente extrator (principal e fallback falharam)")
            return

        try:
            # Com output_schema, response.content já é a instância de ListaGastos (Pydantic)
            lista_extraida = response.content
            schema_valido = hasattr(lista_extraida, "gastos")

            if schema_valido and lista_extraida.gastos:
                novas_transacoes = [
                    {
                        "category": item.category,
                        "amount": abs(float(item.amount)),
                        "type": item.type,
                    }
                    for item in lista_extraida.gastos
                ]
                add_transactions(novas_transacoes)
                self.on_load()  # Atualiza o dashboard e o resumo do banco

            # Uma lista vazia também é um resultado válido (mensagem sem
            # transação nova) — só conta como falha se o schema veio quebrado.
            log_llm_call("extractor", response=response, success=schema_valido)

        except Exception as e:
            log_llm_call("extractor", response=response, success=False, error=str(e))
            print(f"Erro ao extrair e salvar transações estruturadas: {e}")

    def submit_message(self, form_data: dict):
        """Recebe os dados do formulário quando o usuário aperta Enter ou clica em Enviar."""
        user_query = form_data.get("chat_input", "")

        if not user_query.strip():
            return

        historico_formatado = "\n".join(
            f"{msg['role'].upper()}: {msg['content']}" for msg in self.chat_history
        )

        self.chat_history.append({"role": "user", "content": user_query})
        add_chat_message(role="user", content=user_query)
        self.on_load()

        self.is_loading = True
        yield  # Atualiza a nova mensagem enviada no chat

        try:
            self.extract_transactions_from_text(user_query)

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
            add_chat_message(role="agent", content=resposta_limpa)

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

    def clear_chat(self):
        """Apaga o histórico do chat e as transações do banco de dados."""
        clear_session_data()
        self.on_load()

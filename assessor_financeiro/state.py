"""Estado (controller) da aplicação Reflex.

Conecta a UI ao banco de dados e aos agentes de IA. Não contém nenhum
componente visual nem acesso direto ao banco — ambos ficam em `ui/` e
`core/transaction_repository.py`, respectivamente.
"""
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
from assessor_financeiro.agents.advisor_agent import get_financial_advisor
from assessor_financeiro.agents.extractor_agent import get_data_extractor_agent

MENSAGEM_BOAS_VINDAS = (
    "Olá! 👋 Sou a vivIA, sua Assessora Financeira Pessoal. "
    "O que te faz feliz no tempo livre?"
)


class AdvisorState(rx.State):
    chat_history: list[dict[str, str]] = []
    chart_data: list[dict[str, any]] = []
    database_summary: str = ""

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
        self.database_summary = summary.as_text

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
        extractor = get_data_extractor_agent()
        response = extractor.run(text)

        try:
            # Com output_schema, response.content já é a instância de ListaGastos (Pydantic)
            lista_extraida = response.content

            if hasattr(lista_extraida, "gastos") and lista_extraida.gastos:
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

        except Exception as e:
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

            agent = get_financial_advisor(
                financial_data=self.database_summary,
                chat_history=historico_formatado,
            )
            response = agent.run(user_query)
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
        """Neutraliza símbolos que poderiam ser interpretados como LaTeX/matemática.

        Remove delimitadores LaTeX e escapa o cifrão como entidade HTML, para
        que o Reflex renderize "$" sem tentar ativar renderização matemática.
        """
        for delimitador in ["\\(", "\\)", "\\[", "\\]"]:
            texto = texto.replace(delimitador, "")
        return texto.replace("$", "&#36;")

    def clear_chat(self):
        """Apaga o histórico do chat e as transações do banco de dados."""
        clear_session_data()
        self.on_load()

import reflex as rx
import pandas as pd
import io
import json
import re
from .agent import get_financial_advisor, get_data_extractor_agent

# --- MODELOS DE BANCO DE DADOS (ORM) ---
class ChatMessage(rx.Model, table=True):
    role: str
    content: str
    session_id: str = "default_user"

class Transaction(rx.Model, table=True):
    category: str
    amount: float
    type: str 
    session_id: str = "default_user"

# --- ESTADO DA APLICAÇÃO ---
class AdvisorState(rx.State):
    # Removida a variável 'current_message' para otimização de performance. Agora usamos formulário.
    chat_history: list[dict[str, str]] = []
    chart_data: list[dict[str, any]] = []
    database_summary: str = ""
    
    is_loading: bool = False
    is_uploading: bool = False

    def on_load(self):
        """Carrega e calcula os dados do banco para o Dashboard e para o Agente."""
        with rx.session() as db:
            messages = db.query(ChatMessage).filter(ChatMessage.session_id == "default_user").all()
            if not messages:
                welcome_msg = ChatMessage(role="agent", content="Olá! 👋 Sou a vivIA, sua Assessora Financeira Pessoal. O que te faz feliz no tempo livre?")
                db.add(welcome_msg)
                db.commit()
                messages = [welcome_msg]
            
            self.chat_history = [{"role": m.role, "content": m.content} for m in messages]
            
            transactions = db.query(Transaction).filter(Transaction.session_id == "default_user").all()
            
            # --- NOVA LÓGICA DE CÁLCULO DETERMINÍSTICO ---
            category_totals = {}
            total_gastos = 0.0
            total_receitas = 0.0

            for t in transactions:
                # abs() garante que não teremos erros matemáticos se a IA salvar valores negativos acidentalmente
                valor = abs(float(t.amount)) 
                tipo = t.type.lower().strip() # .strip() remove espaços extras

                if tipo == "credito" or tipo == "crédito":
                    total_receitas += valor
                elif tipo == "debito" or tipo == "débito":
                    total_gastos += valor
                    category_totals[t.category] = category_totals.get(t.category, 0.0) + valor

            saldo_atual = total_receitas - total_gastos
            # -----------------------------------------------

            ## Mostrando cores diferentes no grafico de pizza 
            paleta_financeira = [
                "#3b82f6",  # Azul Royal
                "#10b981",  # Verde Esmeralda (Principal)
                "#ef4444",  # Vermelho Alerta (para débitos altos, se quiser)
                "#f97316",  # Laranja Vívido
                "#14b8a6",  # Teal
                "#8b5cf6",  # Roxo Violeta
                "#f59e0b",  # Âmbar
                "#06b6d4",  # Ciano
                "#a855f7",  # Púrpura
            ]
            
            self.chart_data = [
                {
                    "name": str(k),
                    "value": float(round(v, 2)),
                    "fill": paleta_financeira[i % len(paleta_financeira)]
                }
                for i, (k, v) in enumerate(category_totals.items())
            ]
            
            # --- NOVA FORMATAÇÃO DO RESUMO PARA O AGENTE ---
            self.database_summary = (
                f"RESUMO ATUAL DO BANCO DE DADOS:\n"
                f"Total Recebido (Créditos): R$ {total_receitas:.2f}\n"
                f"Total Gasto Registrado (Débitos): R$ {total_gastos:.2f}\n"
                f"Saldo Atual: R$ {saldo_atual:.2f}\n\n"
                f"Detalhamento de Gastos por Categoria:\n"
            )

            for k, v in category_totals.items():
                self.database_summary += f"- {k}: R$ {v:.2f}\n"
            
            print(self.database_summary)

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Lê o CSV real enviado pelo usuário e salva no Banco de Dados."""
        self.is_uploading = True

        with rx.session() as db:
            db.add(ChatMessage(role="user", content="📤 **Enviando arquivo** de transações..."))
            db.commit()
            yield

        self.on_load() # Atualiza UI

        try:
            with rx.session() as db:
                db.add(ChatMessage(role="agent", content="⏳ **Processando** seu arquivo de transações..."))
                db.commit()
                yield

            file = files[0]
            upload_data = await file.read()
            df = pd.read_csv(
                io.BytesIO(upload_data),
                header=None,
                names=["data", "descricao", "valor", "tipo"],
                encoding="utf-8" # Garante a leitura correta de acentos como 'Crédito'
            )
            # print(df.head())
            df.columns = df.columns.str.strip()
            
            with rx.session() as db:
                for linha in df.itertuples(index=False):
                    # Remove espaços em branco das strings
                    descricao_limpa = linha.descricao.strip()
                    tipo_limpo = linha.tipo.strip()

                    # print(f"Transação: {linha.data} - {descricao_limpa} | R$ {linha.valor} ({tipo_limpo})")
                    
                    # Colocar data no banco ...
                    db.add(Transaction(category=descricao_limpa, amount=linha.valor, type=tipo_limpo))

                db.commit()
                print("Transações cadastradas no banco.")  

                db.add(ChatMessage(role="agent", content="✅ **Arquivo processado!** O gráfico já foi atualizado."))
                db.commit() 
                yield
            
        except Exception as e:
            print("Erro no upload. ", e)

            with rx.session() as db:
                db.add(ChatMessage(role="agent", content="❌ Ocorreu um erro ao tentar salvar os dados da sua planilha... Tente novamente."))
                db.commit()
                yield

        self.on_load() # Atualiza UI
        self.is_uploading = False

    def extract_transactions_from_text(self, text: str):
            """Passo 1 da Orquestração: Roda o Agente Extrator para pescar gastos do chat."""
            extractor = get_data_extractor_agent()
            response = extractor.run(text)
            
            try:
                # Com o output_schema, response.content já é a instância de ListaGastos (Pydantic)!
                # Diga adeus ao re.search e ao json.loads.
                lista_extraida = response.content 
                
                # Verifica se o agente retornou itens na lista
                if hasattr(lista_extraida, 'gastos') and lista_extraida.gastos:
                    with rx.session() as db:
                        for item in lista_extraida.gastos:
                            db.add(Transaction(
                                category=item.category,
                                amount=abs(float(item.amount)),
                                type=item.type
                            ))
                        db.commit()
                    self.on_load() # Atualiza o dashboard e o resumo do banco
                    
            except Exception as e:
                print(f"Erro ao extrair e salvar transações estruturadas: {e}")

    def submit_message(self, form_data: dict):
        """Recebe os dados do formulário quando o usuário aperta Enter ou clica em Enviar."""
        # Extrai a mensagem pelo nome do input (chat_input)
        user_query = form_data.get("chat_input", "")
        
        if not user_query.strip():
            return

        historico_formatado = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in self.chat_history])

        # Salva msg do usuário
        self.chat_history.append({"role": "user", "content": user_query})
        with rx.session() as db:
            db.add(ChatMessage(role="user", content=user_query))
            db.commit()
        self.on_load()

        self.is_loading = True
        yield # Atualizando a nova mensagem enviada no chat

        try:
            self.extract_transactions_from_text(user_query)
            
            agent = get_financial_advisor(
                financial_data=self.database_summary,
                chat_history=historico_formatado
            )
            response = agent.run(user_query)

# BLINDAGEM DO TEXTO (A Solução Definitiva com HTML)
            resposta_limpa = response.content

            # 1. Remove APENAS os parênteses e colchetes matemáticos do LaTeX
            caracteres_matematicos = ["\\(", "\\)", "\\[", "\\]"]
            for char in caracteres_matematicos:
                resposta_limpa = resposta_limpa.replace(char, "")

            # 2. O Truque do HTML: Transforma o cifrão num código seguro!
            # O navegador vai renderizar um "$" perfeito, mas o Reflex não vai ativar a matemática.
            resposta_limpa = resposta_limpa.replace("$", "&#36;")

            self.chat_history.append(
                {"role": "agent", "content": resposta_limpa})
            with rx.session() as db:
                db.add(ChatMessage(role="agent", content=resposta_limpa))
                db.commit()

        except Exception as e:
            error_msg = f"Erro de comunicação: {str(e)}"
            self.chat_history.append({"role": "agent", "content": error_msg})

        self.is_loading = False
        yield # Removendo loading

    def clear_chat(self):
        """Apaga o histórico do chat E as transações do banco de dados."""
        with rx.session() as db:
            db.query(ChatMessage).filter(ChatMessage.session_id == "default_user").delete()
            db.query(Transaction).filter(Transaction.session_id == "default_user").delete()
            db.commit()
        self.on_load()


# --- COMPONENTES VISUAIS ---
def message_bubble(message: dict) -> rx.Component:
    is_user = message["role"] == "user"
    return rx.box(
        rx.markdown(message["content"], font_size="0.95em"),
        background_color=rx.cond(is_user, "limegreen", "var(--gray-3)"),
        color=rx.cond(is_user, "white", "var(--gray-12)"),
        padding_left="1em",
        padding_right="1em",
        padding_top="none",
        padding_bottom="none",
        # border_radius="8px",
        border_radius=rx.cond(
            is_user, 
            "16px 16px 2px 16px",  # Canto inferior direito reto para o Usuário
            "16px 16px 16px 2px"   # Canto inferior esquerdo reto para a IA
        ),
        margin_y="0.5em",
        align_self=rx.cond(is_user, "flex-end", "flex-start"),
        max_width="80%",
        box_shadow="0 2px 4px rgba(0,0,0,0.20)"
    )

def dashboard_panel() -> rx.Component:
    return rx.vstack(
        rx.heading("📊 Visão Geral", size="5"),
        rx.text("Distribuição de Gastos", color="gray"),
        
        rx.recharts.pie_chart(
            rx.recharts.pie(
                data=AdvisorState.chart_data,
                data_key="value",
                name_key="name",
                cx="50%",
                cy="50%",
                outer_radius=100,
                fill="#8884d8",
                label=True,
            ),
            rx.recharts.tooltip(),
            height=300,
            width="100%",
        ),
        width="105%",
        padding="1.5em",
        border="1px solid #eaeaea",
        border_radius="12px",
        bg="white",
        background_color="var(--gray-3)"
    )

def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("💰 vivIA: Sua IA Financeira",
                       size="8",
                       margin_bottom="1em",
                       width="100%",
                       text_align="center"
                       ),
            rx.hstack(
                # Coluna Esquerda: Dashboard (Reduzido para dar mais espaço ao chat)
                rx.box(dashboard_panel(), width="40%"),
                
                # Coluna Direita: Chat (Aumentado)
                rx.vstack(
                    rx.hstack(
                        rx.heading("Chat", size="5"),
                        rx.spacer(),
                        rx.button(
                            rx.icon("trash-2", size=18),
                            "Zerar Dados",
                            on_click=AdvisorState.clear_chat,
                            color_scheme="red",
                            variant="soft",
                            size="2"
                        ),
                        width="100%",
                        align_items="center",
                        padding_bottom="0.5em"
                    ),
                    rx.auto_scroll(
                        rx.vstack(
                            # Renderiza as mensagens do histórico
                            rx.foreach(AdvisorState.chat_history, message_bubble),
                            
                            # O novo balão de "Pensamento" que só aparece quando está processando
                            rx.cond(
                                AdvisorState.is_loading,
                                rx.box(
                                    rx.hstack(
                                        rx.spinner(size="2"),
                                        rx.text("Processando e consultando ferramentas...", color="gray", font_size="0.9em", font_style="italic"),
                                        spacing="3",
                                        align_items="center"
                                    ),
                                    bg="gray.50",
                                    padding="1em",
                                    border_radius="8px",
                                    margin_y="0.5em",
                                    align_self="flex-start",
                                    border="1px dashed #ccc"
                                )
                            ),
                            # Garante que a rolagem fique ancorada no final
                            padding_bottom="2em" 
                        ),
                        # height="550px", # Aumentamos a altura da caixa de chat
                        height="70vh", # Aumentamos a altura da caixa de chat
                        width="100%",
                        border="1px solid #eaeaea",
                        scroll_behavior="smooth",
                        padding_left="1.5em",
                        padding_right="1.5em",
                        # padding="1.5em",
                        border_radius="12px",
                        background_color="#fafafa"
                    ),
                    
                    # O Formulário que permite usar a tecla Enter
                    rx.form(
                        rx.hstack(
                            rx.upload(
                                rx.button(
                                    rx.hstack(
                                        rx.icon("paperclip", size=18), # Tamanho ajustado para caber bem no botão
                                        # rx.text("Anexar Arquivo"),
                                        align="center",
                                        width="100%"
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
                                    _hover={
                                        "background_color":"blue",
                                        "color": "white"
                                    }
                                ),
                                rx.cond(AdvisorState.is_uploading, rx.spinner(size="2")),
                                id="csv_upload",
                                multiple=False,
                                accept={"text/csv": [".csv"]},
                                max_files=1,
                                on_drop=AdvisorState.handle_upload(rx.upload_files(upload_id="csv_upload")),
                                border="none",
                                padding="0",
                                _hover={
                                    "cursor": "pointer",
                                    "opacity": 0.9,
                                    "transform": "scale(1.2)", # Dá um leve "pulo" ao passar o mouse
                                    "transition": "transform 0.1s ease",
                                },
                            ),
                            rx.input(
                                name="chat_input", # Nome que o form_data vai capturar
                                placeholder="Ex: Gastei 150 no borracheiro...",
                                width="85%",
                                size="3"
                            ),

                            rx.button(
                                # Insere o ícone de envio
                                rx.icon("send", size=22), 
                                loading=AdvisorState.is_loading, 
                                size="3",
                                variant="solid", # Garante que ele fique preenchido
                                _hover={
                                    "cursor": "pointer",
                                    "opacity": 0.9,
                                    "transform": "scale(1.2)", # Dá um leve "pulo" ao passar o mouse
                                    "transition": "transform 0.1s ease",
                                },
                                # "Enviar", 
                                type="submit", # Transforma o botão num gatilho de submit
                                # loading=AdvisorState.is_loading, 
                                # size="3",
                                width="10%",
                                background_color="limegreen",
                                cursor="pointer"
                            ),
                            width="100%"
                        ),
                        on_submit=AdvisorState.submit_message,
                        reset_on_submit=True,
                        width="100%"
                    ),
                    width="60vw" 
                ),
                width="100vw",
                max_width="1200px",    # Garante que em telas ultra-wide o app não estique infinitamente
                # align_items="center",  # Centraliza os filhos (Heading e Grid) horizontalmente entre si
                spacing="6"
            )

        ),
        # --- O SEGREDO PARA QUEBRAR A LIMITAÇÃO DO PAI ---
        width="100vw",          # vw = Viewport Width. Ignora restrições do pai e pega 100% da largura real do monitor
        min_height="100vh",     # vh = Viewport Height. Pega toda a altura disponível da tela
        # max_width="1400px",
        margin="0",             # Remove margens externas residuais do body/div padrão
        padding="2em",
        background_color="var(--gray-1)",
    )

app = rx.App()
app.add_page(index, on_load=AdvisorState.on_load)
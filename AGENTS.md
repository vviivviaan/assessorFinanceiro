# AGENTS.md — vivIA (Agno — Assessor Financeiro)

Guia de contexto para qualquer agente de IA (Claude Code, Cursor, Copilot, etc.) que for trabalhar neste
repositório. Para as regras específicas de acompanhamento de tarefas no Notion, veja `CLAUDE.md`.

## O que é o projeto

**vivIA** (nome do pacote: `assessor_financeiro`, codinome do projeto: "Agno") é um assistente financeiro
pessoal construído em **Reflex** (framework Python full-stack, UI compilada para React). O usuário conversa
em um chat com um agente de IA, que extrai e categoriza transações financeiras (receitas/gastos) a partir de
texto livre, PDFs de extrato bancário, planilhas, ou importação Open Finance — e o app mantém dashboard,
lista de transações e relatórios atualizados a partir disso.

Desde a Fase 7, o app suporta dois modos de uso, escolhidos em uma tela de onboarding:
- **Pessoal**: um único usuário, uso próprio.
- **Multiempresa** (assessor financeiro / contador): o usuário gerencia vários **clientes**, cada um com seus
  próprios dados isolados (pense em "trocar de aba" entre clientes).

## Stack técnica

- **Framework**: Reflex `0.9.6.post1` (`reflex[db]`) — Python no backend e frontend (compila para React/Next.js
  por baixo dos panos). UI declarativa em `rx.*` components, estado em classes `rx.State`.
- **Banco de dados**: SQLite (`reflex.db`, caminho configurável via `DB_URL` em `rxconfig.py` — ex.: para
  apontar para um volume Docker). ORM: SQLModel (via `rx.Model`). Migrations: **Alembic** (`alembic/`).
- **Agentes de IA**: framework **AGNO** (`agno==2.6.20`), com extração estruturada via `output_schema`
  Pydantic (ver `agents/schemas.py`). Dois agentes principais:
  - **Extractor** (`agents/extractor_agent.py`): lê texto livre/arquivos e extrai `ItemGasto`/`ListaGastos`
    (categoria, valor, tipo, data).
  - **Advisor** (`agents/advisor_agent.py`): conversa com o usuário e dá conselho financeiro.
- **LLM providers**: roteamento configurável por agente via `.env` — Groq (`groq`), OpenAI (`openai`) ou
  Google (`google`), ver `config.py` (`LLM_PROVIDER`, `EXTRACTOR_LLM_PROVIDER`, `ADVISOR_LLM_PROVIDER`) e
  `llm/model_factory.py` / `llm/fallback.py`.
- **Outras libs relevantes**: `pandas` (parsing tabular/datas), `ofxparse` (Open Finance / OFX), `pypdf`
  (extração de PDF de extrato), `openpyxl` (planilhas), `yfinance` (cotações, se usado no advisor).
- **Deploy**: Docker (`Dockerfile`, `docker-compose.yml`) — ver seção "Docker" abaixo.

## Estrutura de pastas

```
assessor_financeiro/
├── assessor_financeiro.py      # ponto de entrada do app Reflex (rx.App, registro de página)
├── config.py                   # env vars, provedores de LLM, paleta de cores, tokens visuais, MODO_*
├── state.py                    # rx.State principal — TODA a lógica de app/estado do frontend vive aqui
├── agents/
│   ├── schemas.py               # ItemGasto, ListaGastos (Pydantic — output_schema dos agentes AGNO)
│   ├── extractor_agent.py       # agente que extrai transações de texto/arquivo
│   └── advisor_agent.py         # agente que conversa/aconselha
├── core/
│   ├── transaction_repository.py # acesso a dados: ChatMessage/Transaction/Cliente (CRUD, sempre por session_id)
│   ├── transaction_service.py    # regras de negócio sobre transações (ex.: parse_data_flexivel)
│   ├── file_import_service.py    # importação de arquivos (PDF/planilha) enviados no chat
│   ├── telemetry.py              # logging/telemetria
│   └── open_finance/              # integração Open Finance (mock_client, importer, schemas)
├── llm/
│   ├── model_factory.py          # instancia o client do provedor de LLM configurado
│   └── fallback.py               # fallback entre provedores
├── models/
│   └── db_models.py              # ChatMessage, Transaction, Cliente (rx.Model, table=True)
└── ui/
    ├── components.py              # TODOS os componentes visuais (cards, header, tabs, gráficos, onboarding)
    └── pages.py                   # layout raiz / roteamento (index()), monta os components em cada página

alembic/versions/                 # migrations do schema do banco (sempre criar uma nova ao mudar models/)
```

### Convenções importantes

- **Tudo em `session_id`**: `ChatMessage` e `Transaction` são particionados por `session_id` (default
  `"default_user"`, de `DEFAULT_SESSION_ID`). O modo multiempresa reaproveita esse mecanismo — cada `Cliente`
  tem seu próprio `session_id` único, e "trocar de cliente ativo" é só trocar qual `session_id` é usado nas
  chamadas do repositório. **Nunca** acesse `Transaction`/`ChatMessage` sem filtrar por `session_id`.
- **`state.py` é o único lugar com lógica de app**: `ui/components.py` e `ui/pages.py` só montam layout a
  partir do que `AdvisorState` expõe — não colocar lógica de negócio em componentes.
- **Datas**: qualquer caminho que crie uma `Transaction` (chat, upload tabular, Open Finance) deve passar a
  data por `parse_data_flexivel()` (em `core/transaction_service.py`) antes de gravar `created_at` — isso já
  foi padronizado para evitar o bug de transações caindo no mês errado.
- **Paleta/visual**: cores e espaçamentos ficam centralizados em `config.py` (`COR_*`, `RAIO_CARD`,
  `SOMBRA_CARD`, `PALETA_FINANCEIRA`) — não hardcodar cor solta em `components.py`.
- **Responsividade**: props de estilo Reflex aceitam arrays `[mobile, mobile, desktop]` (breakpoints
  Chakra-style: base/sm=480px/md=768px/lg=992px/xl=1280px). O layout mobile usa uma barra de abas fixa no
  rodapé; no desktop, as abas ficam estáticas no topo e o Dashboard aparece lado a lado (ver `_tab_trigger`
  e `apenas_mobile` em `components.py`).
- **Migrations**: qualquer mudança em `models/db_models.py` precisa de uma migration Alembic nova em
  `alembic/versions/` (`down_revision` apontando pra migration anterior) — não editar o schema do SQLite
  manualmente fora desse fluxo, exceto correções pontuais de dados já existentes.

## Rodando o projeto

```bash
# ambiente já tem um venv próprio em venv/ (Windows: venv\Scripts\python.exe)
pip install -r requirements.txt

# copiar/configurar .env com as chaves necessárias (ver config.py — GROQ_API_KEY, OPENAI_API_KEY,
# GOOGLE_API_KEY conforme os providers escolhidos em LLM_PROVIDER/EXTRACTOR_LLM_PROVIDER/ADVISOR_LLM_PROVIDER)

alembic upgrade head   # aplica migrations pendentes no reflex.db

reflex run              # sobe o app (frontend + backend) em modo dev
```

`config.py` falha cedo (`validate_llm_api_keys()`) se faltar alguma `*_API_KEY` dos providers configurados —
se o app não subir, checar a mensagem de erro específica antes de investigar mais a fundo.

### Docker

`Dockerfile` + `docker-compose.yml` sobem o app containerizado; `DB_URL` pode apontar pro SQLite em um volume
(ex.: `sqlite:////app/data/reflex.db`) sem mudar nada no fluxo de dev local.

## Testes

Ainda não há suite de testes automatizados neste projeto (item pendente no checklist do Notion — Fase 1).
Verificação hoje é manual: rodar `reflex run` e testar o fluxo na UI. Para checagem rápida de sintaxe sem
rodar o app completo, `python -m py_compile <arquivo>` é suficiente.

## Acompanhamento de tarefas

Ver `CLAUDE.md` — o checklist de progresso do projeto é mantido na página do Notion "vivIA — Checklist de
Escala", com regras específicas de quando marcar itens como "Em Andamento"/"Concluído".

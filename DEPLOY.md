# Publicar o vivIA gratuitamente (Render + Neon)

O vivIA (Reflex) precisa de um servidor sempre ligado, que guarda o estado de cada usuário
em memória e fala por WebSocket. Por isso usamos:

- **Render** (Web Service gratuito, via `Dockerfile`) para rodar o app;
- **Neon** (PostgreSQL gratuito) para guardar usuários, chats e transações.

O Postgres gratuito do Render expira em 30 dias, por isso o banco fica no Neon.
O SQLite (`reflex.db`) é só para uso local: no Render o disco é apagado a cada deploy.

> Confira os limites atuais dos planos gratuitos nos sites dos provedores antes de começar.
> **Não informe cartão de crédito.** Se alguma tela pedir cartão, pare.

## Variáveis de ambiente

| Variável | Valor | Para quê |
|---|---|---|
| `DATABASE_URL` | connection string do Neon | guarda os dados |
| `VIVIA_SECRET_KEY` | chave gerada pelo comando abaixo | criptografa as chaves de API dos usuários |
| `VIVIA_USAR_CHAVES_DO_ENV` | `false` | impede que visitantes usem as SUAS chaves |
| `PORT` | (o Render define sozinho) | porta do servidor |

Gere a `VIVIA_SECRET_KEY` uma vez, guarde num lugar seguro e **nunca troque**
(trocar deixa as chaves já salvas ilegíveis):

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

NÃO coloque `GROQ_API_KEY`/`OPENAI_API_KEY` no servidor: cada pessoa cadastra as próprias
em Configurações depois de criar a conta (Groq tem plano gratuito).

## Passo 1 — Banco no Neon

1. Crie conta em neon.com (login com GitHub/Google) e um projeto (região mais próxima, ex.: São Paulo se existir).
2. No painel, clique em **Connect** e copie a connection string
   (`postgresql://usuario:senha@ep-xxxx.../neondb?sslmode=require`).
3. Prefira a conexão **direta** (sem `-pooler` no host): as migrações do Alembic funcionam melhor.
4. Guarde essa URL: ela é a sua `DATABASE_URL`. Ela contém senha, não coloque no GitHub.

## Passo 2 — App no Render

1. Crie conta em render.com (login com GitHub).
2. **New → Web Service → Build and deploy from a Git repository** e escolha `vviivviaan/assessorFinanceiro`.
3. Configure:
   - **Language/Runtime:** Docker (ele detecta o `Dockerfile`)
   - **Branch:** `master`
   - **Instance Type:** Free
4. Em **Environment Variables**, adicione `DATABASE_URL`, `VIVIA_SECRET_KEY` e `VIVIA_USAR_CHAVES_DO_ENV=false`.
5. **Create Web Service**. O primeiro build demora (instala dependências e compila o front).
   Ao subir, o container roda `reflex db migrate` e depois inicia o app.
6. Abra a URL `https://<nome>.onrender.com`, crie a conta e teste.

## O que esperar do plano gratuito

- O serviço **dorme após ~15 min sem acesso**; o primeiro acesso depois disso demora cerca de 1 minuto.
  Avise os testadores ou abra o link você mesma antes da apresentação.
- Memória limitada (512 MB): serve para poucos testadores ao mesmo tempo.
- Se o WebSocket falhar (a página abre mas não reage), veja os logs do Render e me envie o erro.

## Antes de divulgar

- Teste o fluxo completo com uma conta nova (cadastro, chave, chat, extrato).
- O limite de tentativas de login fica na memória: use **uma instância só**.
- Ainda não existe "esqueci minha senha": quem perder a senha precisa de ajuda manual.
- Os dados financeiros ficam no seu banco: avise os testadores e peça dados fictícios.

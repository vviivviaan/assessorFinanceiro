# Imagem única: compila o frontend (Reflex/Bun) em modo produção no build e,
# no start, roda as migrações do Alembic e serve app+API no mesmo processo
# (--single-port), sem precisar de um servidor web separado (nginx/Caddy).
FROM python:3.13-slim

# curl/unzip: necessários para o Reflex baixar o Bun (runtime do frontend)
# na primeira compilação.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        unzip \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# reflex.db mora aqui dentro (volume Docker), não junto do código-fonte.
RUN mkdir -p /app/data
ENV DB_URL=sqlite:////app/data/reflex.db

# Compila o frontend em modo produção (baixa o Bun automaticamente).
# As chaves reais só entram em runtime (docker-compose -> env_file). Como o
# config.py valida as chaves ao ser importado, o build precisa de valores
# placeholder, passados só neste comando (não ficam gravados na imagem).
RUN GROQ_API_KEY=build OPENAI_API_KEY=build GOOGLE_API_KEY=build \
    reflex export --env prod --no-zip

EXPOSE 8000

# Aplica migrações pendentes e sobe app+API no mesmo processo/porta. Em
# hospedagens (Railway, Render...) a porta vem na variável PORT; localmente
# o padrão é 8000.
CMD ["sh", "-c", "reflex db migrate && reflex run --env prod --single-port --backend-host 0.0.0.0 --backend-port ${PORT:-8000}"]

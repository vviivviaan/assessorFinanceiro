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
RUN reflex export --env prod --no-zip

EXPOSE 8000

# Aplica migrações pendentes e sobe app+API no mesmo processo/porta.
CMD ["sh", "-c", "reflex db migrate && reflex run --env prod --single-port --backend-host 0.0.0.0 --backend-port 8000"]

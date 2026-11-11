# Imagem única: o frontend é compilado UMA vez no build e servido como arquivos
# estáticos pelo Caddy; o backend (Reflex) roda só como API/WebSocket. Isso evita
# recompilar o frontend no start (estourava os 512 MB do plano gratuito do Render).
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

# Caddy (servidor web leve) copiado da imagem oficial.
COPY --from=caddy:2-alpine /usr/bin/caddy /usr/bin/caddy

# URL pública do app, usada pelo navegador para falar com o backend (WebSocket).
# No Render: defina a variável API_URL = https://SEU-SERVICO.onrender.com
# Localmente (docker compose) o padrão abaixo funciona.
ARG API_URL=http://localhost:8000
ENV REFLEX_API_URL=${API_URL}

# Compila só o frontend e guarda os estáticos em /srv. As chaves reais só entram
# em runtime; como o config.py valida as chaves ao importar, o build usa
# placeholders passados só neste comando.
RUN GROQ_API_KEY=build OPENAI_API_KEY=build GOOGLE_API_KEY=build \
    reflex export --frontend-only --no-zip \
    && mkdir -p /srv && cp -r .web/build/client/. /srv/ \
    && rm -rf .web/node_modules /root/.bun/install/cache

EXPOSE 8000

# Migra o banco, sobe o backend em 127.0.0.1:8001 e o Caddy na porta pública
# (PORT no Render, 8000 localmente), servindo os estáticos e repassando
# /_event (WebSocket), /ping e /_upload ao backend.
CMD ["sh", "-c", "reflex db migrate && (reflex run --env prod --backend-only --backend-host 127.0.0.1 --backend-port 8001 &) && exec caddy run --config /app/Caddyfile --adapter caddyfile"]

FROM node:20-bookworm-slim AS web-builder

WORKDIR /app/apps/dsa-web

COPY apps/dsa-web/package*.json ./
RUN npm ci

COPY apps/dsa-web/ ./
RUN npm run build


FROM node:20-bookworm-slim AS mozyfin-cli-builder

RUN npm install -g mozyfin-cli


FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    HOME=/home/dsa \
    WEBUI_HOST=0.0.0.0 \
    WEBUI_AUTO_BUILD=false \
    PORT=8000 \
    LOG_DIR=/app/logs \
    DATABASE_PATH=/app/data/stock_analysis.db \
    DATA_CACHE_DIR=/app/data/cache

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gcc \
        git \
        gosu \
        fontconfig \
        libjpeg62-turbo \
        libxext6 \
        libxrender1 \
        wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

COPY --from=mozyfin-cli-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=mozyfin-cli-builder /usr/local/lib/node_modules/mozyfin-cli /usr/local/lib/node_modules/mozyfin-cli
RUN printf '%s\n' \
        '#!/bin/sh' \
        'exec /usr/local/bin/node /usr/local/lib/node_modules/mozyfin-cli/dist/index.js "$@"' \
        > /usr/local/bin/mozyfin-cli \
    && chmod +x /usr/local/bin/mozyfin-cli

RUN groupadd --gid 1000 dsa \
    && useradd --uid 1000 --gid dsa --create-home --home-dir /home/dsa dsa

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY api/ ./api/
COPY bot/ ./bot/
COPY data_provider/ ./data_provider/
COPY src/ ./src/
COPY strategies/ ./strategies/
COPY templates/ ./templates/
COPY apps/dsa-web/public/ ./apps/dsa-web/public/
COPY --from=web-builder /app/static/ ./static/
COPY docker/entrypoint.sh /entrypoint.sh

RUN mkdir -p /app/data/cache /app/logs /app/reports /home/dsa/.longbridge \
    && chown -R dsa:dsa /app /home/dsa \
    && chmod 700 /home/dsa/.longbridge \
    && chmod +x /entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD sh -c 'curl -fsS "http://127.0.0.1:${PORT:-8000}/api/health" >/dev/null || exit 1'

USER dsa
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "main.py", "--webui-only"]

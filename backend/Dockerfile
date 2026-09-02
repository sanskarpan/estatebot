FROM python:3.12-slim AS builder
WORKDIR /build
COPY backend/requirements.txt /build/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /build/requirements.txt

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DATABASE_PATH=/app/data/estatebot.db \
    INDEX_PATH=/app/data/index \
    RAW_SNAPSHOT_DIR=/app/data/raw \
    SEED_CORPUS_PATH=/app/seed_corpus.json
COPY --from=builder /install /usr/local
COPY backend /app/backend
COPY scraper /app/scraper
COPY ingestion /app/ingestion
COPY data/seed_corpus.json /app/seed_corpus.json
RUN mkdir -p /app/data /app/backend/static/assets
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=4)" || exit 1
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend /app/backend
COPY scraper /app/scraper
COPY ingestion /app/ingestion
RUN mkdir -p /app/data
CMD ["python", "-m", "scraper.run_all"]

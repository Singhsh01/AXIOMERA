FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN useradd -r -u 10001 orkestr && mkdir -p /data/storage && chown -R orkestr /data /app
USER orkestr
ENV ORKESTR_STORAGE_DIR=/data/storage ORKESTR_N8N_WORKFLOWS_DIR=/workflows
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=10 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
# Migrations and seed run once; then N worker processes share Redis-backed caches and rate limits.
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=* --workers ${WEB_CONCURRENCY:-2}"]

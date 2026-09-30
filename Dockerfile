FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COLLOQUILY_DATA_DIR=/data \
    HOST=0.0.0.0 \
    PORT=8000 \
    DEBUG=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY meditech_rag/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt
COPY meditech_rag/ ./

EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
  CMD curl --fail --silent http://127.0.0.1:8000/login >/dev/null || exit 1

CMD ["gunicorn", "--workers", "1", "--threads", "4", "--timeout", "600", "--bind", "0.0.0.0:8000", "app:app"]

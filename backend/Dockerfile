# ── Builder Stage ──────────────────────────────────────────
FROM python:3.13.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip

# ── Runtime Stage ─────────────────────────────────────────
FROM python:3.13.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local

COPY . .

RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 9000

ENV RUNTIME_ENV=production

CMD ["gunicorn", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", \
     "-b", "0.0.0.0:9000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--preload", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app.main:app"]

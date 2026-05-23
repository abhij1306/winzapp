FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements-prod.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --prefix=/install -r requirements-prod.txt


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system appuser \
    && adduser --system --ingroup appuser --no-create-home appuser

COPY --from=builder /install /usr/local
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

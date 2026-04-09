# --- Stage 1: Build frontend ---
FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# --- Stage 2: Python API + static files ---
FROM python:3.12-slim

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY alembic.ini .
COPY migrations/ ./migrations/
COPY entrypoint.sh .

# Копируем собранный фронтенд в static/
COPY --from=frontend-build /frontend/dist ./static/

RUN mkdir -p /app/data/attachments && chmod +x /app/entrypoint.sh && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["/app/entrypoint.sh"]

#!/bin/sh
set -e

export PYTHONPATH=/app:${PYTHONPATH:-}

echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

echo "Starting application..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000

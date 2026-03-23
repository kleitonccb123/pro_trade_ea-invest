#!/bin/bash
set -e

# Entrypoint script for Crypto Trade Hub Backend
# Handles database initialization, migrations, and starts Gunicorn

echo "🚀 Starting Crypto Trade Hub Backend..."

# Function to wait for database
wait_for_db() {
    echo "⏳ Waiting for database to be ready..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if python -c "
import os
import sys
sys.path.insert(0, '/app')
from app.core.database import connect_db
try:
    connect_db()
    print('✅ Database connection successful')
    exit(0)
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
"; then
            echo "✅ Database is ready!"
            return 0
        fi

        echo "⏳ Database not ready yet (attempt $attempt/$max_attempts). Waiting..."
        sleep 2
        ((attempt++))
    done

    echo "❌ Database failed to become ready after $max_attempts attempts"
    exit 1
}

# Wait for database if DATABASE_URL is set
if [ -n "$DATABASE_URL" ]; then
    wait_for_db
fi

# Run database migrations if alembic is available
if [ -f "alembic.ini" ]; then
    echo "🔄 Running database migrations..."
    if alembic upgrade head; then
        echo "✅ Database migrations completed"
    else
        echo "⚠️  Database migrations failed, but continuing..."
    fi
fi

# Create necessary directories
mkdir -p /app/logs
mkdir -p /app/data

# Set proper permissions for logs
touch /app/logs/access.log
touch /app/logs/error.log

echo "🎯 Starting Gunicorn with Uvicorn workers..."

# Get number of workers (default to CPU cores * 2 + 1, max 8)
if [ -z "$WORKERS" ]; then
    WORKERS=$(python -c "
import multiprocessing
workers = min(multiprocessing.cpu_count() * 2 + 1, 8)
print(workers)
")
fi

echo "👷 Using $WORKERS worker processes"

# Start Gunicorn with Uvicorn workers
exec gunicorn \
    --bind 0.0.0.0:8000 \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --timeout 30 \
    --keep-alive 10 \
    --access-logfile /app/logs/access.log \
    --error-logfile /app/logs/error.log \
    --log-level info \
    --capture-output \
    app.main:app
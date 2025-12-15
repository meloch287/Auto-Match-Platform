# syntax=docker/dockerfile:1

FROM python:3.11-slim as base

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package installation
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml README.md ./

# Install dependencies
RUN uv pip install --system -e .

# Copy application code
COPY . .

# -------------------
# API Service
# -------------------
FROM base as api

EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# -------------------
# Bot Service
# -------------------
FROM base as bot

CMD ["python", "-m", "app.bot.main"]

# -------------------
# Worker Service
# -------------------
FROM base as worker

CMD ["arq", "app.workers.main.WorkerSettings"]

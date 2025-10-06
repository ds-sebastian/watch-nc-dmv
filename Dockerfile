# syntax=docker/dockerfile:1

# Use official uv image as builder
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Set environment variables for uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv with cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY main.py ./

# Install project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Final stage - minimal runtime image
FROM python:3.12-slim-bookworm

WORKDIR /app

# Update system packages 
RUN apt-get update && apt-get upgrade -y && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application
COPY --from=builder /app/main.py /app/

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Label for GitHub Container Registry
LABEL org.opencontainers.image.source=https://github.com/ds-sebastian/watch-nc-dmv
LABEL org.opencontainers.image.description="NC DMV Appointment Monitor"

CMD ["python", "main.py"]

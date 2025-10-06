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

# Install Playwright browsers
RUN uv run playwright install chromium && \
    uv run playwright install-deps chromium

# Final stage - minimal runtime image
FROM python:3.12-slim-bookworm

WORKDIR /app

LABEL org.opencontainers.image.source=https://github.com/ds-sebastian/nc-dmv-monitor
LABEL org.opencontainers.image.description="NC DMV Appointment Monitor"

# Install runtime dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcb1 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application
COPY --from=builder /app/main.py /app/

# Copy Playwright browsers from builder
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /root/.cache
USER appuser

CMD ["python", "main.py"]

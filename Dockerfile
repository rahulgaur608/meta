FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    python3-dev \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 1000 is default for HF Spaces)
RUN useradd -m -u 1000 appuser
WORKDIR /app
RUN chown appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment variables for uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_CACHE_DIR="/app/.cache"
ENV PATH="/app/.venv/bin:$PATH"

# Copy only dependency files first to cache layers
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Install dependencies only (no project code yet)
RUN uv sync --no-install-project --no-dev

# Copy the rest of the project files
COPY --chown=appuser:appuser . .

# Final project synchronization with verbose logging
RUN uv sync --no-dev --no-editable --verbose

# HF Spaces uses port 7860
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"

# Run the server
CMD ["uv", "run", "server"]

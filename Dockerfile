# Use an official Python runtime as a parent image
FROM ghcr.io/astral-sh/uv:latest@sha256:c4f5de312ee66d46810635ffc5df34a1973ba753e7241ce3a08ef979ddd7bea5 AS uv

# Use a multi-stage build to keep the final image clean
FROM python:3.11-slim

# Copy the uv binary from the uv image
COPY --from=uv /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    python3-dev \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Add a non-root user
RUN useradd -m -u 1000 appuser

# Set environment variables for uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_CACHE_DIR="/app/.cache"
ENV PATH="/app/.venv/bin:$PATH"

# Copy only dependency files first to cache layers
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Install dependencies only (no-install-project)
RUN uv sync --no-install-project --no-dev

# Copy the rest of the project files
COPY --chown=appuser:appuser . .

# Final project synchronization using pip for better stability in flat layouts
RUN uv pip install --no-dev --no-editable .

# User ownership check
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# HF Spaces uses port 7860
EXPOSE 7860

# Command to run the application
CMD ["uv", "run", "server"]

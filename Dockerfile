FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy project files
COPY pyproject.toml uv.lock ./
COPY . .

# Install dependencies
RUN uv sync --frozen --no-dev

# Create non-root user for HF Spaces
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# HF Spaces uses port 7860
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"

# Run the server using the entrypoint defined in pyproject.toml
CMD ["uv", "run", "server"]

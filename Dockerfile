FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Create non-root user (UID 1000 is default for HF Spaces)
RUN useradd -m -u 1000 appuser
WORKDIR /app
RUN chown appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment variables for uv
ENV UV_COMPILE_BYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# Copy project files (ensuring correct ownership)
COPY --chown=appuser:appuser . .

# Install dependencies as appuser
RUN uv sync --frozen --no-dev

# HF Spaces uses port 7860
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"

# Run the server
CMD ["uv", "run", "server"]

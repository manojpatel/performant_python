FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Install dependencies
# --frozen: strict lock file usage
# --no-install-project: only dependencies, not the app itself (since we copy src later)
RUN uv sync --frozen --no-install-project

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

RUN opentelemetry-bootstrap -a install

# Copy application code
COPY src/ src/
COPY entrypoint.sh .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Environment variables defaults
ENV PYTHONUNBUFFERED=1
ENV ENABLE_TRACING=false

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]

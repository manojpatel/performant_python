FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed (e.g. for build tools)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
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

FROM python:3.12-slim

# LibreOffice for doc→docx conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ ./src/

# Run
ENV PORT=8080
EXPOSE 8080
CMD ["uv", "run", "uvicorn", "analyzer.main:app", "--host", "0.0.0.0", "--port", "8080"]

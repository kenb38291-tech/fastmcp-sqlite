# Stage 1: Build virtual environment with uv
FROM python:3.12-slim-bookworm AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install ultra-fast uv binary
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN uv venv /build/.venv && \
    uv pip install --no-cache --python /build/.venv/bin/python .

# Stage 2: Hardened Runtime Container
FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="fastmcp-sqlite" \
      org.opencontainers.image.description="Production-grade, token-optimized FastMCP SQLite Server" \
      org.opencontainers.image.source="https://github.com/kenb38291-tech/fastmcp-sqlite" \
      org.opencontainers.image.licenses="MIT" \
      io.modelcontextprotocol.server.name="io.github.kenb38291-tech/fastmcp-sqlite"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /data

# Hardened Non-Root User
RUN groupadd -g 10001 mcpuser && \
    useradd -u 10000 -g mcpuser -s /bin/sh -m mcpuser && \
    chown -R mcpuser:mcpuser /data

COPY --from=builder --chown=mcpuser:mcpuser /build/.venv /app/.venv

USER mcpuser

ENTRYPOINT ["fastmcp-sqlite"]
CMD []

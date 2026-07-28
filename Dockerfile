FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /bin/uv

# The base image already ships CPython 3.12; without this uv downloads a second one.
ENV UV_PYTHON_DOWNLOADS=0
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY assistant ./assistant
RUN uv sync --frozen --no-dev

# Baked at build time so the first question is not a silent model download; keep in step with .env.
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV FASTEMBED_CACHE_PATH=/opt/fastembed
# .venv/bin/python, not `uv run`: uv run re-syncs and would put the dev group in the shipped image.
RUN .venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('$EMBEDDING_MODEL')"


FROM python:3.12-slim-bookworm

WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY --from=builder /opt/fastembed /opt/fastembed
COPY assistant ./assistant

ENV PATH="/app/.venv/bin:$PATH" FASTEMBED_CACHE_PATH=/opt/fastembed
EXPOSE 8501
CMD ["streamlit", "run", "assistant/app.py", "--server.address=0.0.0.0", "--server.headless=true"]

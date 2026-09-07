FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.31 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["sh", "-c", ". .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

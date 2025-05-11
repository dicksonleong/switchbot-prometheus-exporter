FROM docker.io/python:3.13-slim-bookworm AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.7.3 /uv /bin/

# Comile bytecode for faster startup time
# Enable copy mode to support bind mount caching
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable --no-install-project

# Copy the code
COPY main.py /app/

FROM python:3.13-slim-bookworm
USER 1000:1000
COPY --from=builder --chown=1000:1000 /app /app
EXPOSE 8080
WORKDIR /app
ENTRYPOINT [".venv/bin/python", "main.py"]

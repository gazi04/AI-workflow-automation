# Shared base: the uv binary plus the env every stage needs.
# Copying the prebuilt binary beats `pip install uv` on every rebuild.
FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11.30 /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_SYNC=1

# Dependency builder. gcc lives here and only here, so no compiler ever reaches
# a final image. --no-install-project keeps this layer keyed on the lock files
# alone, so editing source never busts the dependency cache.
FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Same as above but including the dev group, for the `dev` target below.
FROM builder AS builder-dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Default target: runtime deps only, no compiler, no dev tooling.
FROM base AS runtime
COPY --from=builder /app/.venv /app/.venv
COPY . .
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Opt-in target that keeps pytest/mypy/ruff/pyright available inside the
# container. Build with `target: dev` when you want to run tooling there.
FROM base AS dev
COPY --from=builder-dev /app/.venv /app/.venv
COPY . .
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

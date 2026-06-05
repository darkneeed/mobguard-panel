FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY requirements-api.txt ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements-api.txt

COPY api ./api
COPY mobguard_core ./mobguard_core
COPY mobguard_platform ./mobguard_platform
COPY scripts ./scripts
COPY behavioral_analyzers.py ./behavioral_analyzers.py
COPY ipinfo_api.py ./ipinfo_api.py

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

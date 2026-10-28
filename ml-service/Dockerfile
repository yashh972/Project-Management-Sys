FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY ml-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ml-service/app ./app
COPY ml ./legacy-ml
COPY db/database.sqlite.sql ./db/database.sqlite.sql
COPY db/database.sqlite.sql ./legacy-ml/database.sqlite.sql

FROM base AS dev
COPY ml-service/requirements-dev.txt ./requirements-dev.txt
COPY ml-service/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY ml-service/tests ./tests
CMD ["python", "-m", "pytest", "-q"]

FROM base AS production

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

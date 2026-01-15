FROM python:3.11-slim

WORKDIR /app

# 1. Install system dependencies (needed for asyncpg/psycopg2)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Poetry
RUN pip install poetry

# 3. Copy Poetry Files
# We copy poetry.lock* optionally in case it doesn't exist yet
COPY pyproject.toml poetry.lock* ./

# 4. Install Dependencies
# --no-root: Don't install the project itself yet (we bind mount it)
# virtualenvs.create false: Install libs globally in the container (simpler for Docker)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# 5. Copy Application Code (exclude .venv, __pycache__, etc. via .dockerignore)
COPY . .

# 6. Default Command (Can be overridden by docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y sqlite3 curl && rm -rf /var/lib/apt/lists/*

# Install Poetry matching the project standard
ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -

# Configure Poetry to skip virtualenv creation inside containers
RUN poetry config virtualenvs.create false

# Copy dependency configuration files
COPY pyproject.toml poetry.lock ./

# Install all dependency groups (main, server, dev) to ensure test compatibility
RUN poetry install --no-interaction --no-ansi --no-root

# Copy the entire codebase layout
COPY . .

ENV PYTHONPATH=/app/src

FROM python:3.13-slim

WORKDIR /app

# Install system dependency required by psycopg2-binary
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Install uv and dependencies
COPY pyproject.toml .
RUN pip install uv && uv pip install --system .

# Copy source code
COPY . .

# Run the app
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
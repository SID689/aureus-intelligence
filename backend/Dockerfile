FROM python:3.11-slim

# gcc is required for some numpy/scipy/psycopg2 C extensions on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default command. docker-compose.yml overrides it per service for local
# development; this is what runs anywhere else.
#
# Shell form on purpose, so ${PORT} is expanded at container start. Hosts
# that assign a port (Render, Fly, Cloud Run) pass it in the environment,
# and the exec form would hand uvicorn the literal string "$PORT". The
# default keeps `docker run` on a laptop working unchanged.
#
# No --reload: that is a development flag, and the reloader runs a second
# process, which roughly doubles memory on a 512MB instance.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-keep-alive 120"]

# Agent Eye — Fly.io Dockerfile
# Python 3.11 (matches Railway runtime.txt — psycopg2-binary is well-tested here)

FROM python:3.11-slim

# Avoid Python writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system deps for OpenCV (needed if customer runs the python agent).
# Tiny base image keeps deploy fast.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better Docker layer caching)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy app code
COPY . .

# Fly.io injects PORT; default 8080
EXPOSE 8080

# Start uvicorn. Workers=1 because we're on a tiny free-tier VM
# and the app is stateless so horizontal scale is via more VMs, not more workers.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]

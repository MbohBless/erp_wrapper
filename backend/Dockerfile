FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
# --retries/--timeout make the build resilient to transient PyPI/network blips
# (the "No matching distribution … (from versions: none)" class of failure).
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --retries 8 --timeout 120 -r requirements.txt

COPY . .

EXPOSE 8000

# --proxy-headers makes uvicorn read X-Forwarded-For/Proto instead of logging
# the reverse proxy as the client. --forwarded-allow-ips=* is safe here because
# this port is never published: it is `expose`d on the compose network only, so
# Caddy is the sole thing that can reach it (see docker-compose.yml).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]

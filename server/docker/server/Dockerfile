FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server/docker/server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

COPY server /app/server

ENV PYTHONPATH=/app/server
WORKDIR /app/server/pssm_gremlin

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "pssm_gremlin:app"]

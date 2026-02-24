FROM python:3.12-slim

# propagate args from .env to docker compose
ARG RUNNER_UID
ARG RUNNER_GID

ARG RUNNER_USERNAME
ARG RUNNER_GROUP

ARG HOST
ARG PORT

RUN groupadd -o -r ${RUNNER_GROUP} -g ${RUNNER_GID} && groupadd docker  && \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME} && usermod -a -G docker ${RUNNER_USERNAME}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PSSM_GREMLIN_LOG_DIR=/var/log/pssm_gremlin

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl procps \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p "${PSSM_GREMLIN_LOG_DIR}"

WORKDIR /app

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

COPY --chown=${RUNNER_UID}:${RUNNER_GID} . /app/server


ENV PYTHONPATH=/app/server
WORKDIR /app/server/pssm_gremlin

USER ${RUNNER_UID}:${RUNNER_GID}

CMD ["gunicorn", "-w", "2", "-b", "${HOST}:${PORT}", "pssm_gremlin:app"]

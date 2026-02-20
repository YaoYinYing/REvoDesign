FROM python:3.10-slim

ARG RUNNER_UID
ARG RUNNER_GID

ARG RUNNER_USERNAME
ARG RUNNER_GROUP

ARG DOMAIN
ARG PORT

RUN groupadd -r ${RUNNER_GROUP} -g ${RUNNER_GID} && \
    useradd -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PSSM_GREMLIN_LOG_DIR=/var/log/pssm_gremlin

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl procps \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p "${PSSM_GREMLIN_LOG_DIR}"

WORKDIR /app

COPY --chown=${RUNNER_UID}:${RUNNER_GID} server/docker/server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

COPY --chown=${RUNNER_UID}:${RUNNER_GID} server /app/server


ENV PYTHONPATH=/app/server
WORKDIR /app/server/pssm_gremlin

USER ${RUNNER_UID}:${RUNNER_GID}

CMD ["gunicorn", "-w", "2", "-b", "${DOMAIN}:${PORT}", "pssm_gremlin:app"]

FROM python:3.12-slim

# propagate args from .env to docker compose
ARG RUNNER_UID
ARG RUNNER_GID

ARG RUNNER_USERNAME
ARG RUNNER_GROUP

ARG PORT

RUN groupadd -o -r ${RUNNER_GROUP} -g ${RUNNER_GID} && groupadd docker  && \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME} && usermod -a -G docker ${RUNNER_USERNAME}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PSSM_GREMLIN_LOG_DIR=/var/log/pssm_gremlin_server

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl procps \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p "${PSSM_GREMLIN_LOG_DIR}"

WORKDIR /app

COPY --chown=${RUNNER_UID}:${RUNNER_GID} . /app/server
RUN pip install --no-cache-dir "/app/server[resend]"


ENV PYTHONPATH=/app/server
# ponytail: WORKDIR must be /app/server, not /app/server/pssm_gremlin_server.
# When CWD is inside the package dir, Python's '' sys.path entry finds
# pssm_gremlin.py as a top-level module, shadowing the pssm_gremlin_server package.
WORKDIR /app/server

USER ${RUNNER_UID}:${RUNNER_GID}

CMD ["sh", "-c", "exec gunicorn --preload -w 2 -b 0.0.0.0:${PORT:-8080} pssm_gremlin_server.pssm_gremlin:app"]

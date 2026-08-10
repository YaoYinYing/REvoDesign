# syntax=docker/dockerfile:1.10
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
    PIP_ROOT_USER_ACTION=ignore \
    REVOCOMPUTE_LOG_DIR=/var/log/revocompute

# System deps.  Pre-seed timezone to keep tzdata from prompting.
RUN --mount=type=secret,id=revodesign_build_proxy,env=REVODESIGN_BUILD_PROXY,required=false \
    export HTTP_PROXY="${REVODESIGN_BUILD_PROXY:-}" HTTPS_PROXY="${REVODESIGN_BUILD_PROXY:-}" \
      http_proxy="${REVODESIGN_BUILD_PROXY:-}" https_proxy="${REVODESIGN_BUILD_PROXY:-}" && \
    ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl procps \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p "${REVOCOMPUTE_LOG_DIR}"

WORKDIR /app

COPY --chown=${RUNNER_UID}:${RUNNER_GID} . /app/server
RUN --mount=type=secret,id=revodesign_build_proxy,env=REVODESIGN_BUILD_PROXY,required=false \
    export HTTP_PROXY="${REVODESIGN_BUILD_PROXY:-}" HTTPS_PROXY="${REVODESIGN_BUILD_PROXY:-}" \
      http_proxy="${REVODESIGN_BUILD_PROXY:-}" https_proxy="${REVODESIGN_BUILD_PROXY:-}" && \
    pip install --no-cache-dir "/app/server[resend]"


ENV PYTHONPATH=/app/server
# ponytail: WORKDIR must be /app/server, not /app/server/revocompute.
# When CWD is inside the package dir, Python's '' sys.path entry finds
# app.py as a top-level module, shadowing the revocompute package.
WORKDIR /app/server

USER ${RUNNER_UID}:${RUNNER_GID}

CMD ["sh", "-c", "exec gunicorn --preload -w 2 -b 0.0.0.0:${PORT:-8080} revocompute.app:app"]

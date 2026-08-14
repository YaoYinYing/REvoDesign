# OpenDDE runner — all-atom biomolecular foundation model (co-folding, design).
#
# Uses `opendde pred` with MSA + template features enabled.  Needs network
# access for ColabFold MSA searching.  Checkpoints and search databases live
# at $OPENDDE_ROOT_DIR (/mnt/db/opendde), mounted at runtime.
# Python 3.11+ required. The CUDA-enabled PyTorch wheel supplies the runtime
# libraries, so a second CUDA base stack would only duplicate them.
FROM python:3.11-slim

ARG RUNNER_UID
ARG RUNNER_GID
ARG RUNNER_USERNAME
ARG RUNNER_GROUP

# Runtime search tools only; source-control/download/build tools are absent.
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
    hmmer \
    kalign \
    && rm -rf /var/lib/apt/lists/*

# Pin OpenDDE and let its GPU extra select the matching Torch/CUDA stack in the
# same retained layer. Installing Torch separately would retain the superseded
# wheel and CUDA packages when OpenDDE upgrades them.
RUN python3 -m pip install --no-cache-dir uv && \
    uv pip install --system --no-cache "opendde[gpu]==1.0.3"

# Non-root user.
RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

# Runner workspace.
RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute

COPY --chown=${RUNNER_UID}:${RUNNER_GID} \
    ./docker/runners/opendde/run.sh \
    /app/revocompute/

WORKDIR /app/revocompute/

ENV RUNNER_USERNAME=${RUNNER_USERNAME}
ENV OPENDDE_ROOT_DIR=/mnt/db/opendde
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""

ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

# Pythia-ddG runner — masked ΔΔG prediction from PDB structure.
# CPU-only, Python 3.12. Fetch the pinned source in a throwaway stage so Git
# and its system dependencies never enter the runtime image.
FROM alpine/git:2.47.2 AS pythia-source

ARG PYTHIA_REPO=https://github.com/YaoYinYing/Pythia.git
ARG PYTHIA_REF=9c3d4b29d0c9d73cfd33fc33da43ae316ef6224f
RUN git init /opt/pythia && git -C /opt/pythia remote add origin ${PYTHIA_REPO} && \
    git -C /opt/pythia fetch --depth 1 origin ${PYTHIA_REF} && \
    git -C /opt/pythia checkout --detach FETCH_HEAD && \
    rm -rf /opt/pythia/.git

FROM --platform=linux/amd64 python:3.12-slim

ARG RUNNER_UID
ARG RUNNER_GID
ARG RUNNER_USERNAME
ARG RUNNER_GROUP

# Non-root user.
RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

# PyTorch CPU + Pythia deps.
RUN python -m pip install --no-cache-dir uv && \
    uv pip install --system --no-cache --index-strategy unsafe-best-match torch \
      --extra-index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --system --no-cache \
    biopython \
    joblib \
    numpy \
    pandas \
    pytorch_lightning \
    scipy \
    torchmetrics \
    tqdm

# Pythia checkpoints are intentionally retained with the pinned source.
COPY --from=pythia-source --chown=${RUNNER_UID}:${RUNNER_GID} /opt/pythia /opt/pythia

# Runner workspace.
RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute && \
    ln -s /opt/pythia/pythia /app/revocompute/pythia && \
    ln -s /opt/pythia/pythia-c.pt /app/revocompute/pythia-c.pt && \
    ln -s /opt/pythia/pythia-p.pt /app/revocompute/pythia-p.pt

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/pythia_ddg/run.sh /app/revocompute/

WORKDIR /app/revocompute/

ENV RUNNER_USERNAME=${RUNNER_USERNAME}
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""

ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

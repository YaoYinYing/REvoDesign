# Pythia-ddG runner — masked ΔΔG prediction from PDB structure.
# CPU-only, Python 3.12.
FROM --platform=linux/amd64 python:3.12-slim

ARG RUNNER_UID
ARG RUNNER_GID
ARG RUNNER_USERNAME
ARG RUNNER_GROUP

# System deps: git for cloning.
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Non-root user.
RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

# PyTorch CPU + Pythia deps.
RUN pip install --no-cache-dir \
    biopython \
    joblib \
    numpy \
    pandas \
    pytorch_lightning \
    scipy \
    torchmetrics \
    tqdm && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Clone Pythia-ddG.
ARG PYTHIA_REPO=https://github.com/YaoYinYing/Pythia.git
ARG PYTHIA_REF=main
RUN git clone --depth 1 --branch ${PYTHIA_REF} ${PYTHIA_REPO} /opt/pythia && \
    chown -R ${RUNNER_UID}:${RUNNER_GID} /opt/pythia

# Runner workspace.
RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute && \
    ln -s /opt/pythia/pythia /app/revocompute/pythia && \
    ln -s /opt/pythia/pythia-c.pt /app/revocompute/pythia-c.pt && \
    ln -s /opt/pythia/pythia-p.pt /app/revocompute/pythia-p.pt

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/pythia_ddg/run.sh /app/revocompute/

WORKDIR /app/revocompute/

ENV RUNNER_USERNAME=${RUNNER_USERNAME}

ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

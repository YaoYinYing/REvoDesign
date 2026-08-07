# ponytail: build FROM the locally-cached GREMLIN runner (condaforge/mambaforge
# with Python 3.12 + conda) instead of pulling python:3.10-slim when Docker Hub
# is unreachable.  Revert to python:3.10-slim when Docker Hub is available.
FROM --platform=linux/amd64 revodesign-revocompute-runner:latest

ARG RUNNER_UID
ARG RUNNER_GID
ARG RUNNER_USERNAME
ARG RUNNER_GROUP

# Re-create the non-root user (UID/GID from host may differ from the base image's).
RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

# Install PyTorch CPU + Pythia deps into the base conda environment.
# Don't pin versions — Python 3.12 needs recent wheels; the old PYTHIA.yml pins
# were for Python 3.10 conda.  The Pythia model only needs these packages present.
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

# Set up runner workspace.
RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute

RUN ln -s /opt/pythia/pythia /app/revocompute/pythia && \
    ln -s /opt/pythia/pythia-c.pt /app/revocompute/pythia-c.pt && \
    ln -s /opt/pythia/pythia-p.pt /app/revocompute/pythia-p.pt

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/pythia_ddg/run.sh /app/revocompute/

WORKDIR /app/revocompute/

ENV RUNNER_USERNAME=${RUNNER_USERNAME}

ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

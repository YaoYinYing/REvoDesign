FROM --platform=linux/amd64 python:3.11-slim

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

# Pre-seed timezone + system deps (git for clones).
RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Non-root user.
RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

# Common deps: PyTorch CPU + ProteinMPNN deps.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir biopython numpy pandas tqdm

# Clone ProteinMPNN (used by HyperMPNN and as base for LigandMPNN scripts).
ARG MPNN_REPO=https://github.com/YaoYinYing/ProteinMPNN.git
ARG MPNN_REF=main
RUN git clone --depth 1 --branch ${MPNN_REF} ${MPNN_REPO} /opt/ProteinMPNN && \
    mkdir -p /app/revocompute/hypermpnn_weights

# Clone HyperMPNN for its retrained weights.
ARG HYPERMPNN_REPO=https://github.com/YaoYinYing/HyperMPNN.git
ARG HYPERMPNN_REF=main
RUN git clone --depth 1 --branch ${HYPERMPNN_REF} ${HYPERMPNN_REPO} /opt/HyperMPNN && \
    cp /opt/HyperMPNN/retrained_models/*.pt /app/revocompute/hypermpnn_weights/

# Clone LigandMPNN.
ARG LIGANDMPNN_REPO=https://github.com/dauparas/LigandMPNN.git
ARG LIGANDMPNN_REF=main
RUN git clone --depth 1 --branch ${LIGANDMPNN_REF} ${LIGANDMPNN_REPO} /opt/LigandMPNN && \
    pip install --no-cache-dir -r /opt/LigandMPNN/requirements.txt

# Download LigandMPNN model weights.
RUN cd /opt/LigandMPNN && bash get_model_params.sh "./model_params" || true

# Install ThermoMPNN-D as a package.
ARG THERMOREPO=https://github.com/YaoYinYing/ThermoMPNN-D.git
ARG THERMOREF=main
RUN pip install --no-cache-dir "git+${THERMOREPO}@${THERMOREF}"

# Runner workspace.
RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute

COPY --chown=${RUNNER_UID}:${RUNNER_GID} \
    ./docker/runners/mpnn/run.sh \
    /app/revocompute/

WORKDIR /app/revocompute/
ENV RUNNER_USERNAME=${RUNNER_USERNAME}
ENV MPNN_PATH=/opt/ProteinMPNN/vanilla_proteinmpnn
ENV LIGANDMPNN_PATH=/opt/LigandMPNN
ENV HYPERMPNN_WEIGHTS=/app/revocompute/hypermpnn_weights

ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

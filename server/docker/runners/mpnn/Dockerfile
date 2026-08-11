FROM --platform=linux/amd64 python:3.11-slim AS builder

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends git build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:${PATH}

ARG MPNN_REPO=https://github.com/YaoYinYing/ProteinMPNN.git
ARG MPNN_REF=8907e6671bfbfc92303b5f79c4b5e6ce47cdef57
RUN git init /opt/ProteinMPNN && git -C /opt/ProteinMPNN remote add origin ${MPNN_REPO} && \
    git -C /opt/ProteinMPNN fetch --depth 1 origin ${MPNN_REF} && \
    git -C /opt/ProteinMPNN checkout --detach FETCH_HEAD && rm -rf /opt/ProteinMPNN/.git

ARG HYPERMPNN_REPO=https://github.com/YaoYinYing/HyperMPNN.git
ARG HYPERMPNN_REF=1877ea181d23fe84fb33147748e1367e5a02b6a9
RUN git init /opt/HyperMPNN && git -C /opt/HyperMPNN remote add origin ${HYPERMPNN_REPO} && \
    git -C /opt/HyperMPNN fetch --depth 1 origin ${HYPERMPNN_REF} && \
    git -C /opt/HyperMPNN checkout --detach FETCH_HEAD && \
    mkdir -p /opt/hypermpnn_weights && cp /opt/HyperMPNN/retrained_models/*.pt /opt/hypermpnn_weights/ && \
    rm -rf /opt/HyperMPNN

ARG LIGANDMPNN_REPO=https://github.com/dauparas/LigandMPNN.git
ARG LIGANDMPNN_REF=26ec57ac976ade5379920dbd43c7f97a91cf82de
RUN git init /opt/LigandMPNN && git -C /opt/LigandMPNN remote add origin ${LIGANDMPNN_REPO} && \
    git -C /opt/LigandMPNN fetch --depth 1 origin ${LIGANDMPNN_REF} && \
    git -C /opt/LigandMPNN checkout --detach FETCH_HEAD && rm -rf /opt/LigandMPNN/.git

COPY docker/runners/mpnn/requirements.txt /tmp/requirements.txt
ARG THERMOREPO=https://github.com/YaoYinYing/ThermoMPNN-D.git
ARG THERMOREF=6ec15ae8d870fc70748e6d4f0c8c5555c076efd1
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
      --index-url https://download.pytorch.org/whl/cpu \
      --extra-index-url https://pypi.org/simple && \
    pip install --no-cache-dir --no-deps "git+${THERMOREPO}@${THERMOREF}"

FROM --platform=linux/amd64 python:3.11-slim

ARG RUNNER_UID
ARG RUNNER_GID
ARG RUNNER_USERNAME
ARG RUNNER_GROUP

RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/ProteinMPNN /opt/ProteinMPNN
COPY --from=builder /opt/LigandMPNN /opt/LigandMPNN
COPY --from=builder /opt/hypermpnn_weights /app/revocompute/hypermpnn_weights

RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute

COPY --chown=${RUNNER_UID}:${RUNNER_GID} docker/runners/mpnn/run.sh /app/revocompute/

WORKDIR /app/revocompute/
ENV PATH=/opt/venv/bin:${PATH}
ENV RUNNER_USERNAME=${RUNNER_USERNAME}
ENV MPNN_PATH=/opt/ProteinMPNN/vanilla_proteinmpnn
ENV LIGANDMPNN_PATH=/opt/LigandMPNN
ENV HYPERMPNN_WEIGHTS=/app/revocompute/hypermpnn_weights
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""

ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

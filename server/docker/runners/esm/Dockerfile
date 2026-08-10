# ESM runner — CUDA-enabled image for ESMFold / ESM-2 / ESM-1v / ESM-IF1.
# Build tools and Git stay in the builder; the runtime keeps only Python,
# CUDA libraries, the pinned source, and its installed environment.
FROM nvidia/cuda:11.3.1-cudnn8-runtime-ubuntu20.04 AS builder

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
      python3.9 python3.9-distutils python3.9-venv python3-pip git build-essential && \
    rm -rf /var/lib/apt/lists/* && \
    python3.9 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel

ENV PATH=/opt/venv/bin:${PATH}
RUN pip install --no-cache-dir torch==1.12.1+cu113 \
    --extra-index-url https://download.pytorch.org/whl/cu113 && \
    pip install --no-cache-dir \
      "numpy<2" \
      "pytorch-lightning==1.9.5" \
      "torchmetrics==0.11.4"

ARG ESM_REPO=https://github.com/YaoYinYing/esm2.git
ARG ESM_REF=efcdb2265b180238a30b99ba19cced447eba6b76
RUN git init /opt/esm2 && git -C /opt/esm2 remote add origin ${ESM_REPO} && \
    git -C /opt/esm2 fetch --depth 1 origin ${ESM_REF} && \
    git -C /opt/esm2 checkout --detach FETCH_HEAD && \
    pip install --no-cache-dir -e "/opt/esm2[esmfold]" && rm -rf /opt/esm2/.git

FROM nvidia/cuda:11.3.1-cudnn8-runtime-ubuntu20.04

ARG RUNNER_UID
ARG RUNNER_GID
ARG RUNNER_USERNAME
ARG RUNNER_GROUP

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends python3.9 && \
    rm -rf /var/lib/apt/lists/* && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1

RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/esm2 /opt/esm2

RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute

COPY --chown=${RUNNER_UID}:${RUNNER_GID} \
    docker/runners/esm/run.sh \
    docker/runners/esm/esmfold_inference.py \
    docker/runners/esm/esm1v_score.py \
    docker/runners/esm/esm_if1_design.py \
    /app/revocompute/

WORKDIR /app/revocompute/
ENV PATH=/opt/venv/bin:${PATH}
ENV RUNNER_USERNAME=${RUNNER_USERNAME}

ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

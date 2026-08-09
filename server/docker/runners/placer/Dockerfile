# PLACER: protein-ligand structure generation.  CUDA 12.1 + DGL 2.4.
FROM --platform=linux/amd64 nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends python3.10 python3.10-distutils python3-pip git wget && \
    rm -rf /var/lib/apt/lists/* && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    python3 -m pip install --no-cache-dir --upgrade pip

RUN python3 -m pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu121 && \
    python3 -m pip install --no-cache-dir dgl==2.4.0 -f https://data.dgl.ai/wheels/torch-2.3/cu121/repo.html && \
    python3 -m pip install --no-cache-dir e3nn openbabel networkx pandas opt_einsum

ARG PLACER_REPO=https://github.com/YaoYinYing/PLACER.git
ARG PLACER_REF=main
RUN git config --global http.postBuffer 524288000 && (git clone --depth 1 --branch ${PLACER_REF} ${PLACER_REPO} /opt/PLACER || git clone --depth 1 --branch ${PLACER_REF} ${PLACER_REPO} /opt/PLACER || git clone --depth 1 --branch ${PLACER_REF} ${PLACER_REPO} /opt/PLACER) && \
    pip install --no-cache-dir -e /opt/PLACER

RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/placer/run.sh /app/revocompute/

WORKDIR /app/revocompute/
ENV RUNNER_USERNAME=${RUNNER_USERNAME} PLACER_PATH=/opt/PLACER
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

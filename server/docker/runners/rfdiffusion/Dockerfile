# RFdiffusion: protein backbone diffusion model.  CUDA + DGL.
FROM --platform=linux/amd64 nvidia/cuda:11.6.2-cudnn8-runtime-ubuntu20.04

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends python3.9 python3.9-distutils python3-pip git wget && \
    rm -rf /var/lib/apt/lists/* && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1 && \
    python3 -m pip install --no-cache-dir --upgrade pip

RUN python3 -m pip install --no-cache-dir \
    torch==1.12.1+cu116 --extra-index-url https://download.pytorch.org/whl/cu116 && \
    python3 -m pip install --no-cache-dir \
    dgl==1.0.2+cu116 -f https://data.dgl.ai/wheels/cu116/repo.html

ARG RFDIFFUSION_REPO=https://github.com/RosettaCommons/RFdiffusion.git
ARG RFDIFFUSION_REF=main
RUN for i in 1 2 3; do git clone --depth 1 --branch ${RFDIFFUSION_REF} ${RFDIFFUSION_REPO} /opt/RFdiffusion && break; sleep 10; done && \
    cd /opt/RFdiffusion && pip install --no-cache-dir e3nn==0.3.3 hydra-core && \
    pip install --no-cache-dir -e /opt/RFdiffusion

RUN cd /opt/RFdiffusion && bash scripts/download_models.sh

RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/rfdiffusion/run.sh /app/revocompute/

WORKDIR /app/revocompute/
ENV RUNNER_USERNAME=${RUNNER_USERNAME} RFDIFFUSION_PATH=/opt/RFdiffusion
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

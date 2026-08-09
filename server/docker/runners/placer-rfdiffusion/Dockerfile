# PLACER + RFdiffusion shared runner — CUDA 12.1 + DGL 2.4 + e3nn.
# Both projects use the same toolchain (torch, DGL, SE(3) ops).  RFdiffusion's
# vendored SE3-Transformer (NVIDIA, 2021) is pure PyTorch — no compiled CUDA
# kernels — and is compatible with torch 2.x / DGL 2.x.
FROM --platform=linux/amd64 nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

# System deps.
RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends python3.10 python3.10-distutils python3-pip git wget && \
    rm -rf /var/lib/apt/lists/* && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    python3 -m pip install --no-cache-dir --upgrade pip

# Clone both repos (no pip).
ARG PLACER_REPO=https://github.com/YaoYinYing/PLACER.git
ARG PLACER_REF=main
RUN git config --global http.postBuffer 524288000 && (git clone --depth 1 --branch ${PLACER_REF} ${PLACER_REPO} /opt/PLACER || git clone --depth 1 --branch ${PLACER_REF} ${PLACER_REPO} /opt/PLACER || git clone --depth 1 --branch ${PLACER_REF} ${PLACER_REPO} /opt/PLACER)

ARG RFDIFFUSION_REPO=https://github.com/RosettaCommons/RFdiffusion.git
ARG RFDIFFUSION_REF=main
RUN git config --global http.postBuffer 524288000 && (git clone --depth 1 --branch ${RFDIFFUSION_REF} ${RFDIFFUSION_REPO} /opt/RFdiffusion || git clone --depth 1 --branch ${RFDIFFUSION_REF} ${RFDIFFUSION_REPO} /opt/RFdiffusion || git clone --depth 1 --branch ${RFDIFFUSION_REF} ${RFDIFFUSION_REPO} /opt/RFdiffusion) && \
    mkdir -p /opt/RFdiffusion/models

# All pip installs in one RUN.  CUDA 12.1 torch + DGL 2.4 cover both projects.
RUN python3 -m pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu121 && \
    python3 -m pip install --no-cache-dir dgl==2.4.0 -f https://data.dgl.ai/wheels/torch-2.3/cu121/repo.html && \
    python3 -m pip install --no-cache-dir e3nn openbabel networkx pandas opt_einsum hydra-core

# RFdiffusion's setup.py: install the rfdiffusion package itself.
RUN pip install --no-cache-dir -e /opt/RFdiffusion

# Non-root user.
RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

# Runner workspace.
RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute /opt/PLACER /opt/RFdiffusion
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/placer-rfdiffusion/run.sh /app/revocompute/

WORKDIR /app/revocompute/
ENV RUNNER_USERNAME=${RUNNER_USERNAME} \
    PLACER_PATH=/opt/PLACER \
    RFDIFFUSION_PATH=/opt/RFdiffusion
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

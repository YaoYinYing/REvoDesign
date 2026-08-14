# PLACER + RFdiffusion shared runner — CUDA 12.1 + DGL 2.4 + e3nn.
# Both projects use the same toolchain (torch, DGL, SE(3) ops).
#
# RFdiffusion vendors NVIDIA's SE3-Transformer (2021) at env/SE3Transformer/.
# It only uses two e3nn calls — o3.spherical_harmonics and o3.wigner_* —
# which are stable across e3nn versions.
#
# Neither RFdiffusion nor the vendored SE3 code need pip install.  We set
# PYTHONPATH so both packages are importable directly from their repo paths.
# This avoids RFdiffusion's broken install_requires (se3-transformer doesn't
# exist on PyPI).
FROM alpine/git:2.47.2 AS placer-source
ARG PLACER_REPO=https://github.com/YaoYinYing/PLACER.git
ARG PLACER_REF=7dc5563300e7143582d85636bdd413d4c7688e9a
RUN git init /opt/PLACER && git -C /opt/PLACER remote add origin ${PLACER_REPO} && \
    git -C /opt/PLACER fetch --depth 1 origin ${PLACER_REF} && git -C /opt/PLACER checkout --detach FETCH_HEAD && \
    rm -rf /opt/PLACER/.git

FROM alpine/git:2.47.2 AS rfdiffusion-source
ARG RFDIFFUSION_REPO=https://github.com/RosettaCommons/RFdiffusion.git
ARG RFDIFFUSION_REF=86507b6538f51fce57b5a72477165f03999ed7ae
RUN git init /opt/RFdiffusion && git -C /opt/RFdiffusion remote add origin ${RFDIFFUSION_REPO} && \
    git -C /opt/RFdiffusion fetch --depth 1 origin ${RFDIFFUSION_REF} && git -C /opt/RFdiffusion checkout --detach FETCH_HEAD && \
    rm -rf /opt/RFdiffusion/.git && mkdir -p /opt/RFdiffusion/models

FROM --platform=linux/amd64 nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

# System deps.
RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    echo 'Acquire::Queue-Mode "access"; Acquire::Retries "3";' > /etc/apt/apt.conf.d/99-speed.conf && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends python3.10 python3.10-distutils python3-pip python3-openbabel && \
    rm -rf /var/lib/apt/lists/* && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Copy both pinned source trees without retaining source-control tooling.
COPY --from=placer-source /opt/PLACER /opt/PLACER
COPY --from=rfdiffusion-source /opt/RFdiffusion /opt/RFdiffusion

# All pip deps in one RUN. PLACER's pinned environment is the version
# authority: Torch 2.3.1, DGL 2.4.0, and e3nn 0.5.4 on CUDA 12.1.
# The vendored SE3-Transformer requirements.txt lists wandb, pynvml, dllogger,
# decorator — all training-only, never imported at inference. RFdiffusion
# pins older e3nn 0.3.3, but its vendored inference code only uses
# o3.wigner_3j and o3.spherical_harmonics, whose call contract is retained by
# PLACER's e3nn 0.5.4.
RUN python3 -m pip install --no-cache-dir uv && \
    uv pip install --system --no-cache --index-strategy unsafe-best-match torch==2.3.1 \
      --extra-index-url https://download.pytorch.org/whl/cu121 && \
    uv pip install --system --no-cache dgl==2.4.0 --find-links https://data.dgl.ai/wheels/torch-2.3/cu121/repo.html && \
    uv pip install --system --no-cache \
      "e3nn @ https://github.com/e3nn/e3nn/archive/ef93f876c9985b3816aefb2982b3cf4325df6ba4.tar.gz" \
      networkx==3.4.2 pandas==2.2.3 \
      opt_einsum==3.4.0 hydra-core==1.3.2 pyrsistent==0.20.0

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
    RFDIFFUSION_PATH=/opt/RFdiffusion \
    PYTHONPATH=/opt/RFdiffusion:/opt/RFdiffusion/env/SE3Transformer:${PYTHONPATH}
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

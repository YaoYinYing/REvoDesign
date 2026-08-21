# ESMDynamic requires OpenFold's CUDA extension, so compile it in a CUDA 12.9
# development stage matching the PyTorch cu129 wheel.
FROM nvidia/cuda:12.9.1-cudnn-devel-ubuntu22.04 AS builder

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common git wget && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends python3.11 python3.11-venv && \
    rm -rf /var/lib/apt/lists/* && \
    python3.11 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir uv

ARG ESMDYNAMIC_REPO=https://github.com/YaoYinYing/esmdynamic.git
ARG ESMDYNAMIC_REF=b3c7f04f97c754f26e744d726df627e9e1e7ffdd
ARG OPENFOLD_REPO=https://github.com/sokrypton/openfold.git
ARG OPENFOLD_REF=5b3e9b800441a6e0543935e31bcf52937aabd189
ARG DLLOGGER_REPO=https://github.com/NVIDIA/dllogger.git
ARG DLLOGGER_REF=0478734ff7be75adde8d160e04872664d1c62e5f

RUN uv pip install --python /opt/venv/bin/python --no-cache \
      torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu129 && \
    uv pip install --python /opt/venv/bin/python --no-cache \
      biopython==1.85 einops==0.8.1 matplotlib==3.10.3 ml-collections==1.1.0 \
      modelcif==1.4 omegaconf==2.3.0 'plotly[express]==6.1.2' pytorch-lightning==2.5.2 scipy==1.16.0

RUN git init /opt/dllogger && git -C /opt/dllogger remote add origin ${DLLOGGER_REPO} && \
    git -C /opt/dllogger fetch --depth 1 origin ${DLLOGGER_REF} && git -C /opt/dllogger checkout --detach FETCH_HEAD && \
    uv pip install --python /opt/venv/bin/python --no-cache /opt/dllogger && rm -rf /opt/dllogger/.git && \
    git init /opt/openfold && git -C /opt/openfold remote add origin ${OPENFOLD_REPO} && \
    git -C /opt/openfold fetch --depth 1 origin ${OPENFOLD_REF} && git -C /opt/openfold checkout --detach FETCH_HEAD && \
    uv pip install --python /opt/venv/bin/python --no-cache --no-build-isolation /opt/openfold && \
    wget -q -O /opt/venv/lib/python3.11/site-packages/openfold/resources/stereo_chemical_props.txt \
      https://git.scicore.unibas.ch/schwede/openstructure/-/raw/7102c63615b64735c4941278d92b554ec94415f8/modules/mol/alg/src/stereo_chemical_props.txt && \
    rm -rf /opt/openfold/.git && \
    git init /opt/esmdynamic && git -C /opt/esmdynamic remote add origin ${ESMDYNAMIC_REPO} && \
    git -C /opt/esmdynamic fetch --depth 1 origin ${ESMDYNAMIC_REF} && git -C /opt/esmdynamic checkout --detach FETCH_HEAD && \
    uv pip install --python /opt/venv/bin/python --no-cache /opt/esmdynamic && rm -rf /opt/esmdynamic/.git

FROM nvidia/cuda:12.9.1-cudnn-runtime-ubuntu22.04

ARG RUNNER_UID
ARG RUNNER_GID
ARG RUNNER_USERNAME
ARG RUNNER_GROUP

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends python3.11 && \
    rm -rf /var/lib/apt/lists/* && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

COPY --from=builder /opt/venv /opt/venv
RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute
COPY --chown=${RUNNER_UID}:${RUNNER_GID} docker/runners/esmdynamic/run.sh docker/runners/common/task_context.sh docker/runners/common/task_context.py /app/revocompute/

WORKDIR /app/revocompute
ENV PATH=/opt/venv/bin:${PATH} TORCH_HOME=/mnt/db/weights/esmdynamic RUNNER_USERNAME=${RUNNER_USERNAME}
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

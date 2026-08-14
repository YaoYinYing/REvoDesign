# EasIFA2: enzyme active-site annotation from a structure, with optional reaction context.
# The upstream packed environment is used because its DGL/TorchDrug CUDA stack is not
# reproducibly expressible by the repository's broad, unpinned requirements.txt.
FROM python:3.11-slim AS builder

ARG EASIFA_REPO=https://github.com/wangxr0526/EasIFA2.0_Core.git
ARG EASIFA_REF=146ed9ca6ccbc7458bd2d343ec2de0ce149c9aad
ARG EASIFA_METADATA_REPO=xiaoruiwang/EasIFA2.0_Metadata
ARG EASIFA_METADATA_REF=f26aecd922a48d935315fe7d4f61381a388492af
ARG EASIFA_ENV_SHA256=da5751abd99297eaae813591a8b32a006d244d0d8ba376712223d83f24fe88f2

RUN echo 'Acquire::Queue-Mode "access"; Acquire::Retries "3";' > /etc/apt/apt.conf.d/99-speed.conf && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates g++ git libxext6 libxrender1 ninja-build && \
    rm -rf /var/lib/apt/lists/* && \
    python -m pip install --no-cache-dir uv && \
    uv pip install --system --no-cache "huggingface_hub[hf_xet]==0.34.4"

RUN git init -q /opt/EasIFA2 && git -C /opt/EasIFA2 remote add origin ${EASIFA_REPO} && \
    git -C /opt/EasIFA2 fetch --depth 1 origin ${EASIFA_REF} && \
    git -C /opt/EasIFA2 checkout --detach FETCH_HEAD && \
    rm -rf /opt/EasIFA2/.git

# The proxy in front of Hugging Face may close a long transfer between Xet
# chunks. The client cache is content-addressed, so retry until the complete,
# pinned object exists; then verify it before extraction.
RUN mkdir -p /tmp/easifa-metadata /opt/easifa-env && \
    for attempt in 1 2 3 4 5 6 7 8; do \
      hf download ${EASIFA_METADATA_REPO} easifa2_core_env.tar.gz \
        --revision ${EASIFA_METADATA_REF} --local-dir /tmp/easifa-metadata || true; \
      test -f /tmp/easifa-metadata/easifa2_core_env.tar.gz && break; \
    done && \
    echo "${EASIFA_ENV_SHA256}  /tmp/easifa-metadata/easifa2_core_env.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/easifa-metadata/easifa2_core_env.tar.gz -C /opt/easifa-env && \
    rm -rf /tmp/easifa-metadata && \
    /opt/easifa-env/bin/conda-unpack

RUN /opt/easifa-env/bin/python -m pip install --no-cache-dir uv && \
    uv pip install --python /opt/easifa-env/bin/python --no-cache --no-deps /opt/EasIFA2 && \
    /opt/easifa-env/bin/python -c "import easifa_core" && \
    test -x /opt/easifa-env/bin/easifa-predict

# TorchDrug lazily compiles this CPU-only sparse-tensor shim on its first
# forward pass. Build it once, install it as a normal extension module, and
# replace the lazy loader so production does not retain a compiler toolchain.
# The C++ runtime is linked statically: the builder's system libstdc++
# (GLIBCXX_3.4.32, bookworm glibc 2.36) must not leak into the image — SLURM
# compute nodes may run an older glibc, where a copied newer libstdc++.so.6
# fails to dlopen ("GLIBC_2.38 not found"). The conda env keeps its own,
# older-glibc-compatible runtime.
RUN mkdir -p /opt/easifa-torch-extensions/torch_ext_0 && \
    TORCH_EXTENSIONS_DIR=/opt/easifa-torch-extensions \
      /opt/easifa-env/bin/python -c 'from torch.utils import cpp_extension; cpp_extension.load("torch_ext", ["/opt/easifa-env/lib/python3.11/site-packages/torchdrug/utils/extension/torch_ext.cpp"], extra_cflags=["-Ofast", "-fopenmp", "-DAT_PARALLEL_OPENMP", "-DCUDA_OP", "-static-libstdc++", "-static-libgcc", "-Wl,-Bstatic", "-lgomp", "-Wl,-Bdynamic"], extra_cuda_cflags=["-O3"], build_directory="/opt/easifa-torch-extensions/torch_ext_0")' && \
    cp /opt/easifa-torch-extensions/torch_ext_0/torch_ext.so /opt/easifa-env/lib/python3.11/site-packages/torch_ext.so && \
    sed -i 's#torch_ext = load_extension("torch_ext", \[os.path.join(path, "torch_ext.cpp")\])#import torch_ext#' \
      /opt/easifa-env/lib/python3.11/site-packages/torchdrug/utils/torch.py && \
    grep -qx 'import torch_ext' /opt/easifa-env/lib/python3.11/site-packages/torchdrug/utils/torch.py && \
    /opt/easifa-env/bin/python -c 'import torch, torch_ext; from torchdrug.utils import torch as torch_utils; assert torch_utils.torch_ext is torch_ext'

FROM debian:bookworm-slim

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    echo 'Acquire::Queue-Mode "access"; Acquire::Retries "3";' > /etc/apt/apt.conf.d/99-speed.conf && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates libexpat1 libxext6 libxrender1 && \
    rm -rf /var/lib/apt/lists/* && \
    (groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true) && \
    ((id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && \
      usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
      useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME})

COPY --from=builder /opt/easifa-env /opt/easifa-env
COPY --from=builder /opt/EasIFA2 /opt/EasIFA2

RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/easifa/run.sh /app/revocompute/

WORKDIR /app/revocompute/
ENV PATH=/opt/easifa-env/bin:${PATH} \
    RUNNER_USERNAME=${RUNNER_USERNAME} \
    EASIFA_PATH=/opt/EasIFA2 \
    EASIFA_CHECKPOINT_DIR=/mnt/db/weights/easifa2 \
    TORCH_EXTENSIONS_DIR=/tmp/easifa-torch-extensions \
    MPLCONFIGDIR=/tmp/easifa-matplotlib \
    DGLBACKEND=pytorch
RUN ! command -v c++
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

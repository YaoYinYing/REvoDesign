# ESM runner — CUDA-enabled image for ESM-2 embedding, ESM-1v scoring,
# and ESM-IF1 design. ESMFold was dropped: its esmfold_3B_v1 checkpoint is
# built against the 2022 openfold whose setup.py no longer compiles on a
# supported toolchain, and the model is superseded by the dedicated
# structure runners (RFdiffusion/PLACER).
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04 AS builder

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
      software-properties-common git && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends python3.11 python3.11-venv && \
    rm -rf /var/lib/apt/lists/* && \
    python3.11 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel

ENV PATH=/opt/venv/bin:${PATH}
RUN pip install --no-cache-dir torch==2.2.0+cu121 \
    --extra-index-url https://download.pytorch.org/whl/cu121 && \
    pip install --no-cache-dir \
      "numpy<2" \
      "pandas==2.2.3" \
      "pytorch-lightning==1.9.5" \
      "scipy==1.12.0" \
      "torch-geometric==2.5.3" \
      "torchmetrics==0.11.4"

# ESM-IF1 (esm2.inverse_folding) imports scipy.spatial.transform and
# torch_geometric (via gvp_modules).  The fork's setup.py declares scipy but
# not torch-geometric; the image pins dependencies explicitly rather than
# trusting transitive resolution.  torch-geometric ships a pure-python wheel
# on PyPI (no matrix index needed; MessagePassing uses native torch ops).
# The smoke import covers the full inverse-folding import chain so a
# dependency gap fails at image build.
ARG ESM_REPO=https://github.com/YaoYinYing/esm2.git
ARG ESM_REF=efcdb2265b180238a30b99ba19cced447eba6b76
RUN git init /opt/esm2 && git -C /opt/esm2 remote add origin ${ESM_REPO} && \
    git -C /opt/esm2 fetch --depth 1 origin ${ESM_REF} && \
    git -C /opt/esm2 checkout --detach FETCH_HEAD && \
    pip install --no-cache-dir -e /opt/esm2 && \
    python -c "import esm2, esm2.inverse_folding, pandas" && \
    rm -rf /opt/esm2/.git

FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ARG RUNNER_UID
ARG RUNNER_GID
ARG RUNNER_USERNAME
ARG RUNNER_GROUP

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends python3.11 && \
    rm -rf /var/lib/apt/lists/* && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/esm2 /opt/esm2

RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute

COPY --chown=${RUNNER_UID}:${RUNNER_GID} \
    docker/runners/esm/run.sh \
    docker/runners/esm/esm1v_score.py \
    docker/runners/esm/esm_if1_design.py \
    docker/runners/esm/msa1b_score.py \
    /app/revocompute/

WORKDIR /app/revocompute/
ENV PATH=/opt/venv/bin:${PATH}
ENV RUNNER_USERNAME=${RUNNER_USERNAME}
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""

ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

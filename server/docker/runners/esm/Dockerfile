# ESM runner — CUDA-enabled image for ESMFold / ESM-2 / ESM-1v / ESM-IF1.
# Build tools and Git stay in the builder; the runtime keeps only Python,
# CUDA libraries, the pinned source, and its installed environment.
# openfold installs from GitHub (PyPI carries only a 0.0.1 stub); its
# setup.py needs nvcc, so the builder uses the -devel image. Runtime
# stays on -runtime. dm-tree/biopython/ml_collections/einops/modelcif/
# scipy are its unpinned runtime deps (the [esmfold] extra pins
# deepspeed==0.5.9, which does not support torch 2.2).
FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04 AS builder

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
      software-properties-common git ca-certificates build-essential && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends python3.12 python3.12-venv python3.12-dev && \
    rm -rf /var/lib/apt/lists/* && \
    python3.12 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel

ENV PATH=/opt/venv/bin:${PATH}
ARG OPENFOLD_REF=v2.2.0
RUN pip install --no-cache-dir torch==2.2.0+cu121 \
    --extra-index-url https://download.pytorch.org/whl/cu121 && \
    pip install --no-cache-dir \
      "numpy<2" \
      "pandas==2.2.3" \
      "pytorch-lightning==1.9.5" \
      "torchmetrics==0.11.4" \
      "dm-tree" \
      "biopython" \
      "ml_collections" \
      "einops" \
      "modelcif" \
      "scipy" && \
    pip install --no-cache-dir --no-build-isolation "openfold @ git+https://github.com/aqlaboratory/openfold.git@${OPENFOLD_REF}" && \
    python -c 'from openfold.np import residue_constants; from openfold.np.protein import Protein, to_pdb; from openfold.utils.feats import atom14_to_atom37; from openfold.data.data_transforms import make_atom14_masks; from openfold.utils.loss import compute_predicted_aligned_error, compute_tm; from openfold.model.structure_module import StructureModule; print("openfold imports OK")'

ARG ESM_REPO=https://github.com/YaoYinYing/esm2.git
ARG ESM_REF=efcdb2265b180238a30b99ba19cced447eba6b76
RUN git init /opt/esm2 && git -C /opt/esm2 remote add origin ${ESM_REPO} && \
    git -C /opt/esm2 fetch --depth 1 origin ${ESM_REF} && \
    git -C /opt/esm2 checkout --detach FETCH_HEAD && \
    pip install --no-cache-dir -e /opt/esm2 && \
    python -c "import esm2, pandas; from esm2.esmfold.v1 import esmfold; print('esm2 + esmfold imports OK')" && \
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
    apt-get install -y --no-install-recommends python3.12 && \
    rm -rf /var/lib/apt/lists/* && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

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
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""

ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

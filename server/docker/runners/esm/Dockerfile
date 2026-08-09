# ESM runner — CUDA-enabled image for ESMFold / ESM-2 / ESM-1v / ESM-IF1.
#
# Uses pip install from git URL — no conda, no clone.  The esm2 fork's
# [esmfold] extras pull in openfold, dllogger, and the full ESMFold stack.
# ESMFold needs Python <= 3.9 + CUDA + nvcc, so we build on CUDA 11.3.
FROM nvidia/cuda:11.3.1-cudnn8-runtime-ubuntu20.04

ARG RUNNER_UID
ARG RUNNER_GID
ARG RUNNER_USERNAME
ARG RUNNER_GROUP

# Pre-seed timezone so tzdata doesn't prompt interactively.
RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone

# System deps: python3.9, git (openfold dep), build-essential (nvcc).
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    python3.9 \
    python3.9-distutils \
    python3-pip \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1 \
    && python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# PyTorch with CUDA 11.3 (must match the base image).
RUN python3 -m pip install --no-cache-dir \
    torch==1.12.1+cu113 \
    --extra-index-url https://download.pytorch.org/whl/cu113

# esm2 fork with ESMFold extras (openfold, dllogger, biopython, etc.).
ARG ESM_REPO=https://github.com/YaoYinYing/esm2.git
ARG ESM_REF=main
RUN python3 -m pip install --no-cache-dir \
    "git+${ESM_REPO}@${ESM_REF}#egg=fair-esm2[esmfold]"

# Re-create the non-root user (UID/GID from host may differ from the base image's).
RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

# Set up runner workspace.
RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute

COPY --chown=${RUNNER_UID}:${RUNNER_GID} \
    ./docker/runners/esm/run.sh \
    ./docker/runners/esm/esmfold_inference.py \
    ./docker/runners/esm/esm1v_score.py \
    ./docker/runners/esm/esm_if1_design.py \
    /app/revocompute/

WORKDIR /app/revocompute/

ENV RUNNER_USERNAME=${RUNNER_USERNAME}

ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

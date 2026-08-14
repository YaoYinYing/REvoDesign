# BioEmu: generative protein structure sampling from sequence.
FROM --platform=linux/amd64 python:3.11-slim

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends kalign && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

# BioEmu 1.4.1 is the package published from upstream's v1.4.0 release tag.
# The unconstrained CUDA extra currently selects a CUDA 13 Torch build, which
# cannot initialize against production's CUDA 12.8-capable NVIDIA driver. Pin
# one supported Torch generation first; constrain BioEmu's JAX extra to a
# CUDA-12-compatible release so its resolver cannot replace Torch with cu130.
COPY docker/runners/bioemu/constraints.txt /tmp/bioemu-constraints.txt
RUN python -m pip install --no-cache-dir uv && \
    uv pip install --system --no-cache --index-strategy unsafe-best-match "torch==2.7.1" \
      --extra-index-url https://download.pytorch.org/whl/cu128
RUN uv pip install --system --no-cache --constraint /tmp/bioemu-constraints.txt \
      "jax[cuda12]==0.5.3" "bioemu[cuda]==1.4.1" && \
    rm -f /tmp/bioemu-constraints.txt

RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/bioemu/run.sh /app/revocompute/

WORKDIR /app/revocompute/
ENV RUNNER_USERNAME=${RUNNER_USERNAME}
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

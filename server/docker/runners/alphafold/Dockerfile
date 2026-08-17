# AlphaFold2 — official google-deepmind/alphafold, JAX + CUDA 12 wheels.
# GPU compute comes from jaxlib's bundled CUDA 12 wheels (matching the
# official image recipe); CPU TF 2.16 handles the data pipeline.
FROM alpine/git:2.47.2 AS alphafold-source
ARG ALPHAFOLD_REPO=https://github.com/google-deepmind/alphafold.git
ARG ALPHAFOLD_REF=c77e5d2a8961d1a353632c462914ff0a32a950f6
RUN git init /opt/alphafold && git -C /opt/alphafold remote add origin ${ALPHAFOLD_REPO} && \
    git -C /opt/alphafold fetch --depth 1 origin ${ALPHAFOLD_REF} && git -C /opt/alphafold checkout --detach FETCH_HEAD && \
    rm -rf /opt/alphafold/.git

FROM --platform=linux/amd64 python:3.11-slim

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

# hh-suite (hhblits/hhsearch) from source + hmmer (jackhmmer) + kalign.
# v3.3.0 predates gcc 12: a3m_compress.h needs <cstdint> on bookworm.
RUN apt-get update && \
    apt-get install -y --no-install-recommends git cmake g++ make kalign hmmer wget ca-certificates && \
    git clone --branch v3.3.0 --single-branch https://github.com/soedinglab/hh-suite.git /tmp/hh-suite && \
    sed -i '1s/^/#include <cstdint>\n/' /tmp/hh-suite/src/a3m_compress.h && \
    mkdir -p /tmp/hh-suite/build && cd /tmp/hh-suite/build && cmake -DCMAKE_INSTALL_PREFIX=/opt/hhsuite .. && \
    make -j"$(nproc)" && make install && cd / && rm -rf /tmp/hh-suite && \
    rm -rf /var/lib/apt/lists/*

COPY --from=alphafold-source /opt/alphafold /opt/alphafold
WORKDIR /opt/alphafold

# stereo_chemical_props.txt (official build step, pinned upstream blob).
RUN wget -q -P /opt/alphafold/alphafold/common/ \
      https://git.scicore.unibas.ch/schwede/openstructure/-/raw/7102c63615b64735c4941278d92b554ec94415f8/modules/mol/alg/src/stereo_chemical_props.txt

# Official pinned requirements (dm-haiku==0.0.12, tensorflow-cpu==2.16.1,
# openmm[cuda12]==8.2.0 + pdbfixer for Amber relaxation, ...), then JAX
# overridden to the last 0.4.x release: jaxlib <=0.4.28 CUDA wheels segfault
# with host drivers >=570 (this host runs 570.124.06), fixed in 0.4.31+.
# jax[cuda12] on PyPI bundles its own CUDA libs.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /opt/alphafold/requirements.txt && \
    pip install --no-cache-dir "jax[cuda12]==0.4.38"

# Non-root user and runner workspace.
RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}
RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute /opt/alphafold
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/alphafold/run.sh ./docker/runners/common/task_context.sh ./docker/runners/common/task_context.py /app/revocompute/

WORKDIR /app/revocompute/
ENV RUNNER_USERNAME=${RUNNER_USERNAME} \
    ALPHAFOLD_PATH=/opt/alphafold \
    PATH="/opt/hhsuite/bin:${PATH}"
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

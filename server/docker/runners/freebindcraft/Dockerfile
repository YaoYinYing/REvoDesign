# FreeBindCraft binder design with JAX, OpenMM, FASPR, and sc-rs.
FROM python:3.11-slim

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP
ARG FREEBINDCRAFT_REPO=https://github.com/cytokineking/FreeBindCraft.git
ARG FREEBINDCRAFT_REF=8b8d4c4627da06f084f46b7007450048fe3ca22f
ARG COLABDESIGN_REPO=https://github.com/sokrypton/ColabDesign.git
ARG COLABDESIGN_REF=e31a56fe1d9b4de25c8697f3a28b75892941cc72

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends build-essential git ocl-icd-libopencl1 && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /etc/OpenCL/vendors && \
    echo "libnvidia-opencl.so.1" > /etc/OpenCL/vendors/nvidia.icd

RUN python -m pip install --no-cache-dir uv && \
    uv pip install --system --no-cache \
      "jax[cuda12]==0.6.0" \
      "colabdesign @ git+${COLABDESIGN_REPO}@${COLABDESIGN_REF}" \
      openmm pdbfixer freesasa "matplotlib<3.7" "numpy<2"

RUN git init /opt/bindcraft && git -C /opt/bindcraft remote add origin ${FREEBINDCRAFT_REPO} && \
    git -C /opt/bindcraft fetch --depth 1 origin ${FREEBINDCRAFT_REF} && \
    git -C /opt/bindcraft checkout --detach FETCH_HEAD && rm -rf /opt/bindcraft/.git && \
    chmod +x /opt/bindcraft/functions/dssp /opt/bindcraft/functions/sc /opt/bindcraft/functions/FASPR

RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}
RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute /opt/bindcraft
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/freebindcraft/run.sh ./docker/runners/common/task_context.sh ./docker/runners/common/task_context.py /app/revocompute/

USER ${RUNNER_UID}:${RUNNER_GID}
WORKDIR /app/revocompute
ENV BINDCRAFT_HOME=/opt/bindcraft OPENMM_PLATFORM_ORDER=OpenCL,CUDA MPLCONFIGDIR=/tmp/matplotlib
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

# EasIFA: enzyme active-site annotation.  GPU, TorchDrug + RDKit.
FROM --platform=linux/amd64 python:3.10-slim

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends git wget build-essential libxrender1 && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

ARG EASIFA_REPO=https://github.com/YaoYinYing/EasIFA.git
ARG EASIFA_REF=fb65cfe083c8a247ceae0174a59c8e4811fc8c1b
RUN git init /opt/EasIFA && git -C /opt/EasIFA remote add origin ${EASIFA_REPO} && \
    git -C /opt/EasIFA fetch --depth 1 origin ${EASIFA_REF} && git -C /opt/EasIFA checkout --detach FETCH_HEAD && \
    rm -rf /opt/EasIFA/.git

# All pip installs in one RUN so pip resolves torch + downstream deps together.
# torchdrug pulls torch; installing it in the same layer as the cu121 torch
# prevents pip from replacing the CUDA build with a CPU one from PyPI.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu121 && \
    pip install --no-cache-dir rdkit fair-esm==2.0.0 && \
    pip install --no-cache-dir torchdrug==0.2.1

RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/easifa/run.sh /app/revocompute/

WORKDIR /app/revocompute/
ENV RUNNER_USERNAME=${RUNNER_USERNAME} EASIFA_PATH=/opt/EasIFA
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

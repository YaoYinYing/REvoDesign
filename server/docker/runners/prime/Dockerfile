# Pro-Prime: 690M protein LM for zero-shot mutant effect + OGT prediction.
# GPU recommended for inference (transformers + torch).
FROM --platform=linux/amd64 python:3.10-slim

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone

RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu121 && \
    pip install --no-cache-dir transformers pandas biopython tqdm scipy

RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/prime/run.sh /app/revocompute/

WORKDIR /app/revocompute/
ENV RUNNER_USERNAME=${RUNNER_USERNAME}
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

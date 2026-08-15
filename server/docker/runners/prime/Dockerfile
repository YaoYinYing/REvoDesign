# Pro-Prime: 690M protein LM for zero-shot mutant effect + OGT prediction.
# GPU recommended for inference (transformers + torch).
FROM --platform=linux/amd64 python:3.10-slim

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    echo "Etc/UTC" > /etc/timezone

RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

RUN python -m pip install --no-cache-dir uv && \
    uv pip install --system --no-cache --index-strategy unsafe-best-match torch==2.3.1 \
      --extra-index-url https://download.pytorch.org/whl/cu121 && \
    uv pip install --system --no-cache \
      transformers==4.36.2 \
      pandas==2.2.3 \
      biopython==1.83 \
      tqdm==4.66.5 \
      scipy==1.12.0

RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/prime/run.sh ./docker/runners/common/task_context.sh ./docker/runners/common/task_context.py /app/revocompute/

# Vendored model code for the pinned Prime snapshots (see vendor/README.md).
# The model-dir code is never executed with trust_remote_code; it must be
# vendored here at build time.
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/prime/vendor/ /opt/prime_model_code/

WORKDIR /app/revocompute/
ENV RUNNER_USERNAME=${RUNNER_USERNAME} \
    PRIME_MODEL_DIR=/mnt/db/weights/prime/ProPrime_650M_OGT_Prediction-91490f95c707 \
    PRIME_DMS_MODEL_DIR=/mnt/db/weights/prime/Prime_690M-7b75010748d2
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

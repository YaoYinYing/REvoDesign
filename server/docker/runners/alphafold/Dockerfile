# ColabFold 1.6.2 / AlphaFold2 with CUDA 12, following the supported
# LocalColabFold workflow while reusing the upstream reproducible image.
FROM ghcr.io/sokrypton/colabfold:1.6.2-cuda12

ARG RUNNER_UID ARG RUNNER_GID ARG RUNNER_USERNAME ARG RUNNER_GROUP

RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    (id -u ${RUNNER_USERNAME} >/dev/null 2>&1 && usermod -u ${RUNNER_UID} -g ${RUNNER_GID} ${RUNNER_USERNAME}) || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}
RUN mkdir -p /app/revocompute && chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/alphafold/run.sh ./docker/runners/common/task_context.sh ./docker/runners/common/task_context.py /app/revocompute/

USER ${RUNNER_UID}:${RUNNER_GID}
WORKDIR /app/revocompute
ENV MPLBACKEND=Agg MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

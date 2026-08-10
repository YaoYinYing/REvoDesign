# syntax=docker/dockerfile:1.10
# set ubuntu as backend OS (force x86_64 for compatibility with GREMLIN stack)
FROM --platform=linux/amd64 condaforge/mambaforge

ARG RUNNER_UID
ARG RUNNER_GID

ARG RUNNER_USERNAME
ARG RUNNER_GROUP



# ponytail: groupadd -f to tolerate pre-existing groups (e.g. staff on macOS).
# Fall back to existing group when the gid is already taken.
RUN groupadd -f -r ${RUNNER_GROUP} -g ${RUNNER_GID} 2>/dev/null || true && \
    groupadd -f docker 2>/dev/null || true && \
    id -u ${RUNNER_USERNAME} >/dev/null 2>&1 || \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME} && \
    usermod -a -G docker ${RUNNER_USERNAME} 2>/dev/null || true

# Use bash to support string substitution.
SHELL ["/bin/bash", "-c"]

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/pssm_gremlin/GREMLIN.yml /tmp/
RUN --mount=type=secret,id=revodesign_build_proxy,env=REVODESIGN_BUILD_PROXY,required=false \
    export HTTP_PROXY="${REVODESIGN_BUILD_PROXY:-}" HTTPS_PROXY="${REVODESIGN_BUILD_PROXY:-}" \
      http_proxy="${REVODESIGN_BUILD_PROXY:-}" https_proxy="${REVODESIGN_BUILD_PROXY:-}" && \
    conda env create -f /tmp/GREMLIN.yml \
      && conda clean --all --force-pkgs-dirs --yes \
      && rm -f /tmp/GREMLIN.yml

RUN mkdir -p /app/revocompute
RUN chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/pssm_gremlin/scripts/ /app/revocompute/scripts/
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/pssm_gremlin/run.sh /app/revocompute/

WORKDIR /app/revocompute/

# Persist the build arg so the entrypoint can resolve ${RUNNER_USERNAME} at runtime.
ENV RUNNER_USERNAME=${RUNNER_USERNAME}

# ponytail: no ldconfig or runuser here — task_runtime passes --user at
# container start, so we already are ${RUNNER_USERNAME}.  ldconfig is a
# build-time concern and would fail without root anyway.
ENTRYPOINT ["bash", "/app/revocompute/run.sh"]

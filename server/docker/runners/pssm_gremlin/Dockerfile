# set ubuntu as backend OS (force x86_64 for compatibility with GREMLIN stack)
FROM --platform=linux/amd64 condaforge/mambaforge

ARG RUNNER_UID
ARG RUNNER_GID

ARG RUNNER_USERNAME
ARG RUNNER_GROUP



RUN groupadd -o -r ${RUNNER_GROUP} -g ${RUNNER_GID} && groupadd docker  && \
    useradd -o -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME} && usermod -a -G docker ${RUNNER_USERNAME}

# Use bash to support string substitution.
SHELL ["/bin/bash", "-c"]

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/pssm_gremlin/GREMLIN.yml /tmp/
RUN conda env create -f /tmp/GREMLIN.yml \
      && conda clean --all --force-pkgs-dirs --yes \
      && rm -f /tmp/GREMLIN.yml

RUN mkdir -p /app/revocompute
RUN chown -R ${RUNNER_UID}:${RUNNER_GID} /app/revocompute

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/pssm_gremlin/scripts/ /app/revocompute/scripts/
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/pssm_gremlin/run.sh /app/revocompute/

WORKDIR /app/revocompute/

# Persist the build arg so the entrypoint can resolve ${RUNNER_USERNAME} at runtime.
ENV RUNNER_USERNAME=${RUNNER_USERNAME}

RUN echo $'#!/bin/bash\n\
ldconfig\n\
exec runuser -u ${RUNNER_USERNAME} -- bash /app/revocompute/run.sh "$@"' > /app/run_runner.sh \
  && chmod +x /app/run_runner.sh

ENTRYPOINT ["/app/run_runner.sh"]

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

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./env/GREMLIN.yml /tmp/
RUN conda env create -f /tmp/GREMLIN.yml \
      && conda clean --all --force-pkgs-dirs --yes \
      && rm -f /tmp/GREMLIN.yml

RUN mkdir -p /app/pssm_gremlin
RUN chown -R ${RUNNER_UID}:${RUNNER_GID} /app/pssm_gremlin

COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./scripts/ /app/pssm_gremlin/scripts/
COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./REvoDesign_PSSM_GREMLIN.sh /app/pssm_gremlin/

WORKDIR /app/pssm_gremlin/

# Persist the build arg so the entrypoint can resolve ${RUNNER_USERNAME} at runtime.
ENV RUNNER_USERNAME=${RUNNER_USERNAME}

RUN echo $'#!/bin/bash\n\
ldconfig\n\
exec runuser -u ${RUNNER_USERNAME} -- bash /app/pssm_gremlin/REvoDesign_PSSM_GREMLIN.sh "$@"' > /app/run_pssm.sh \
  && chmod +x /app/run_pssm.sh

ENTRYPOINT ["/app/run_pssm.sh"]

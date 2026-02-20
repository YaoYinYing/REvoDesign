# set ubuntu as backend OS (force x86_64 for compatibility with GREMLIN stack)
FROM --platform=linux/amd64 condaforge/mambaforge

ARG RUNNER_UID
ARG RUNNER_GID

ARG RUNNER_USERNAME
ARG RUNNER_GROUP

RUN groupadd -r ${RUNNER_GROUP} -g ${RUNNER_GID} && \
    useradd -r -g ${RUNNER_GROUP} -u ${RUNNER_UID} ${RUNNER_USERNAME}

# Use bash to support string substitution.
SHELL ["/bin/bash", "-c"]

COPY --chown=${RUNNER_UID}:${RUNNER_GID} server/env/GREMLIN.yml /tmp/
RUN conda env create -f /tmp/GREMLIN.yml \
      && conda clean --all --force-pkgs-dirs --yes \
      && rm -f /tmp/GREMLIN.yml

RUN mkdir -p /app/pssm_gremlin
RUN chown -R ${RUNNER_UID}:${RUNNER_GID} /app/pssm_gremlin

COPY --chown=${RUNNER_UID}:${RUNNER_GID} server/scripts/ /app/pssm_gremlin/scripts/
COPY --chown=${RUNNER_UID}:${RUNNER_GID} server/REvoDesign_PSSM_GREMLIN.sh /app/pssm_gremlin/

# Add SETUID bit to the ldconfig binary so that non-root users can run it.
RUN chmod u+s /sbin/ldconfig.real

WORKDIR /app/pssm_gremlin/

RUN echo $'#!/bin/bash\n\
ldconfig\n\
bash /app/pssm_gremlin/REvoDesign_PSSM_GREMLIN.sh "$@"' > /app/run_pssm.sh \
  && chmod +x /app/run_pssm.sh

RUN chown ${RUNNER_UID}:${RUNNER_GID} /app/run_pssm.sh

USER ${RUNNER_UID}:${RUNNER_GID}

ENTRYPOINT ["/app/run_pssm.sh"]

# set ubuntu as backend OS
FROM condaforge/mambaforge

# Use bash to support string substitution.
SHELL ["/bin/bash", "-c"]

COPY ./env/GREMLIN.yml /tmp/
RUN conda env create -n GREMLIN -f /tmp/GREMLIN.yml \
      && conda activate GREMLIN \
      && conda clean --all --force-pkgs-dirs --yes \
      && rm -f /tmp/GREMLIN.yml

RUN mkdir -p /app/pssm_gremlin
COPY ./scripts/ /app/pssm_gremlin/scripts/
COPY ./REvoDesign_PSSM_GREMLIN.sh /app/pssm_gremlin/

# Add SETUID bit to the ldconfig binary so that non-root users can run it.
RUN chmod u+s /sbin/ldconfig.real

WORKDIR /app/pssm_gremlin/

RUN echo $'#!/bin/bash\n\
ldconfig\n\
bash /app/pssm_gremlin/REvoDesign_PSSM_GREMLIN.sh "$@"' > /app/run_pssm.sh \
  && chmod +x /app/run_pssm.sh
ENTRYPOINT ["/app/run_pssm.sh"]
# set ubuntu as backend OS
FROM ubuntu:22.04

# Use bash to support string substitution.
SHELL ["/bin/bash", "-c"]

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN DEBIAN_FRONTEND=noninteractive  apt-get update -y  \
    && apt-get install -y ca-certificates \
    && apt-get install -y wget tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get clean

# Install Miniconda package manager.
RUN wget -q -P /tmp \
  https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && bash /tmp/Miniconda3-latest-Linux-x86_64.sh -b -p /opt/conda \
    && rm /tmp/Miniconda3-latest-Linux-x86_64.sh

# Install conda packages.
ENV PATH="/opt/conda/bin:$PATH"
ENV LD_LIBRARY_PATH="/opt/conda/lib:$LD_LIBRARY_PATH"

COPY ./env/GREMLIN.yml /tmp/
RUN conda env create -f /tmp/GREMLIN.yml \
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
# set ubuntu as backend OS
FROM condaforge/mambaforge
ARG PYTHON_VERSION
ENV FAKE_PACKAGE=RED

# Use bash to support string substitution.
SHELL ["/bin/bash", "-c"]

# copying
RUN mkdir -p /tmp/${FAKE_PACKAGE}/${FAKE_PACKAGE}/UI
COPY pyproject.toml /tmp/${FAKE_PACKAGE}
COPY Makefile /tmp/${FAKE_PACKAGE}

# basic tools
RUN apt-get update \
    && apt-get install -y build-essential make sudo xvfb fluxbox curl \
    && cd /tmp/${FAKE_PACKAGE} \
    && make prepare-test \
    && make setup-display \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


RUN sed -i "s/REvoDesign/${FAKE_PACKAGE}/g" /tmp/${FAKE_PACKAGE}/pyproject.toml \
    && conda create --name REvoDesign python=${PYTHON_VERSION} -y \
    && source activate REvoDesign \
    && conda install -c conda-forge pymol-open-source -y \
    && cd /tmp/${FAKE_PACKAGE} \
    && touch  /tmp/${FAKE_PACKAGE}/README.md \
    && make install \
    && make prepare-test \
    && python -m pip cache purge \
    && conda clean --all --force-pkgs-dirs --yes \
    && rm -fr /tmp/${FAKE_PACKAGE}

CMD ["/bin/bash"]
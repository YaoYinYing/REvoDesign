# Setup Environment of Development

Typing hints are supported in this environment.

1. Ensure you have Conda installed.
2. Create the basic environment. `conda create -n REvoDesignReproduce python=3.11 -y`
3. Activate the environment. `conda activate REvoDesignReproduce`
4. Install Conda dependencies. `conda install -y -c conda-forge numpy==1.26.4 pmw==2.0.1 libcxx==19.1.3 libcurl==8.10.1 libclang-cpp15==15.0.7 libclang13==19.1.2 libgfortran==5.0.0 libgfortran5==13.2.0  libllvm15==15.0.7 libllvm19==19.1.2 llvm-openmp==19.1.2 openssl pyqt==5.15.9 qt-main==5.15.8 sip==6.8.6 xz freetype==2.12.1 glew==2.1.0 glib==2.82.2 glib-tools==2.82.2 libglib==2.82.2 libjpeg-turbo==3.0.0 libpng==1.6.44 libnetcdf==4.9.2  glm==0.9.9.8 libxml2==2.12.7 pip`
5. Install PyMOL from the source. `pip install git+https://github.com/schrodinger/pymol-open-source.git@v3.1.0`
    For special case: `MACOSX_DEPLOYMENT_TARGET=10.13 pip install git+https://github.com/schrodinger/pymol-open-source.git@v3.1.0`

6. Install the rest of packages using `pip install pyqt5==5.15.11 pyqt5-qt5==5.15.15 pyqt5-sip==12.15.0 --force-reinstall` (**twice** if pymol failed on launch) to continue the installation. 

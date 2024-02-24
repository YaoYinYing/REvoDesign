![logo](https://raw.githubusercontent.com/YaoYinYing/artworks/main/DALL%C2%B7E%202024-01-22%2018.09.07%20-%20A%20sleek%20logo%20design%20with%20a%20human%20pilot%20dressed%20in%20yellow-pink%20uniform%20and%20a%20robot%20co-pilot%20in%20blue%2C%20both%20exhibiting%20friendly%20smiles.%20Abstract%20style.%20T.png)
[![Unit Tests](https://github.com/YaoYinYing/REvoDesign/actions/workflows/unit_tests.yml/badge.svg)](https://github.com/YaoYinYing/REvoDesign/actions/workflows/unit_tests.yml)
[![Docker Image](https://github.com/YaoYinYing/REvoDesign/actions/workflows/docker-image.yml/badge.svg)](https://github.com/YaoYinYing/REvoDesign/actions/workflows/docker-image.yml)
[![Docker Image for Unittests](https://github.com/YaoYinYing/REvoDesign/actions/workflows/docker-image-test.yml/badge.svg)](https://github.com/YaoYinYing/REvoDesign/actions/workflows/docker-image-test.yml)
![python-version](https://img.shields.io/badge/python-3.9_%7C_3.10_%7C_3.11-green?logo=python)
[![codecov](https://codecov.io/gh/YaoYinYing/REvoDesign/graph/badge.svg?token=2qSJ7cgk1b)](https://codecov.io/gh/YaoYinYing/REvoDesign)
[![CircleCI](https://dl.circleci.com/status-badge/img/circleci/97VjoN5in7mMaQdymWj7Qk/EVmMjwc2AXdvw6kpYNfFPj/tree/main.svg?style=svg&circle-token=5f78acfbe0dd8e334384b23515857bd4996ca7a1)](https://dl.circleci.com/status-badge/redirect/circleci/97VjoN5in7mMaQdymWj7Qk/EVmMjwc2AXdvw6kpYNfFPj/tree/main)


## Introduction

Welcome to **REvoDesign** - a PyMOL plugin that makes enzyme redesign tasks easier for everyone. **REvoDesign** aims at facilitating enzyme redesign using a combination of structural and phylogenetic information, serving as a co-pilot for protein designers and leveraging the wealth of human knowledge in enzyme design.

### About the Plugin

Enzyme redesign is a complex task that requires a deep understanding of protein structures, substrate binding sites, and evolutionary relationships. **REvoDesign** Toolkit is designed to streamline this process by offering a range of tools and functionalities to assist protein designers in their endeavors.

### Key Features

In brief, the **REvoDesign** PyMOL plugin provides a set of essential tools to help protein designers with the following tasks:

1. **Surface Residue Analysis**: Identify surface residues exposed as solvent-accessible surface area (SASA) and design pocket identification based on substrates and/or cofactors, with customizable cutoffs.

2. **Mutant Loading**: Load available designable mutants through a PSSM-like table in CSV format, allowing for customizable rejections and preferences.

3. **Human Knowledge Supervision**: Perform human knowledge-supervised mutant selection within the PyMOL interface, utilizing structural views.

4. **Scale Reduction**: Reduce the scale of your design, making it suitable for low-throughput wet-lab validation by leveraging sequence clustering.

5. **Visualization**: Visualize mutant tables in PyMOL, whether they have been scored or not.

6. **Co-Evolution Analysis**: Search for possible inter-residue co-evolved residue pairs for effective mutants using the GREMLIN Markov random field profile.

**REvoDesign** is your indispensable companion in the intricate journey of enzyme redesign. Whether you are a seasoned protein designer or just beginning your exploration, **REvoDesign** Toolkit is here to simplify your workflow and enhance your enzyme engineering endeavors.

Please refer to the [documentation(WIP)](link_to_documentation) for detailed instructions on how to use the toolkit and make the most of its features.

## Installation

With the recent updates, the installation process for **REvoDesign** Toolkit has been dramatically changed. Please follow the steps below:

1. **Install the PyMOL Graphic Installer**:

   Before installing the main program, you should install its installer towards the PyMOL menu like other PyMOL plugins. Follow these steps:

   - Open PyMOL.
   - Go to the "Plugin Manager" and choose "Install New Plugin."
   - Select "Install from Local File."
   - Choose the entrypoint file located at the root directory of the repository:

   ```
   <repo-url-or-filepath>/REvoDesign.PyMOL.py
   ```

   This will create an graphic installer for installing the core package of **REvoDesign**. Once the package is installed, the entrypoint file will allow you to access it from the PyMOL menu.

   ![installer](https://github.com/YaoYinYing/REvoDesign/assets/33014714/b44fc4df-e1a7-4ded-9f9b-bba2c1303bb7)


2. **Install the Main Program**:

   To install the main program, which is upgradable from internet access, you have two sources:

   a. If you prefer to install from the remote repository, check `Repository` and click `Install`:

   ![From remote repo](https://github.com/YaoYinYing/REvoDesign/assets/33014714/75d50ebd-cb92-4ad5-b761-40fce374a79e)


   This action will call the exact Python interpreter that used by current PyMOL instance and install REvoDesign as a package.

   b. If you have no access to the remote url because of the policy from network provider, you may install it from a cloned local repository or unzipped source code by running the following command:

   ![From a local src](https://github.com/YaoYinYing/REvoDesign/assets/33014714/5d35c6cc-d057-46ff-a31b-f3e056172116)
   

   c. To install a specific commit/branch, check `Version` or `Commit` for more historical releases:
   ![From remote repo, commit c66f29356907102ffdf797486f299a9608558e34](https://github.com/YaoYinYing/REvoDesign/assets/33014714/a950091c-09c5-4266-bef4-4df5c93e0923)
   

   d. To install with extra features, use `Extras` to pick a desire one, or install full version by selecting `full`:

   ![install with extras](https://github.com/YaoYinYing/REvoDesign/assets/33014714/06655184-6c0d-4291-9371-23d6a7ed2ce5)

   **Extras table**

   | extras tag |   packages   |                        references                      |   explanations  |
   | :--------: | :----------: | :----------------------------------------------------- | :-------------: |
   |    `jax`   | `colabdesign`| https://github.com/sokrypton/ColabDesign.git@v1.1.1    |     with JAX    |
   |    `tf`    |  `DLPacker`  | https://github.com/YaoYinYing/DLPacker@pip-installable | with TensorFlow |
   |   `torch`  |   `PIPPack`  | https://github.com/YaoYinYing/PIPPack@pip-installable  |  with PyTorch   |
   |   `full`   |   all above  |                        all above                       | with all above  |
   | `unittest` |   `absl-py`  |                                                        | for unit tests  |
   
   
   **WARNING: ColabDesign uses Jax, which requires Python >= 3.9**
   
   Please make sure that you are using modern PyMOL version from [pymol-open-source](https://github.com/schrodinger/pymol-open-source) channel, instead of obsolete PyMOL bundle (* < v2.5.7*, shipped with **Python 3.7**) from [offical website](https://pymol.org/) or [schrodinger's conda channel](https://anaconda.org/schrodinger/pymol-bundle).

   ALSO, for MacOS users work with **Apple Silicon** and PyMOL bundle >2.5.7, `jaxlib` builded with `AVX` will not work under `Rosetta-2`. 
   Please consider using native build of `pymol-open-source` or building `jaxlib` from source.

   **Doc**: [Building jaxlib from source](https://jax.readthedocs.io/en/latest/developer.html#building-jaxlib-from-source)
   
   **Issue**: [CPU Support / Necessary AVX Instructions](https://github.com/google/jax/discussions/11436#discussioncomment-3121063)


3. **Getting started**:
   - In order to get started, you need to load/fetch a structure(`fetch 1SUO`, for example) into your PyMOL session.
   - Click `Menu` -> `REvoDesign` -> `Import PyMOL Session` to let **REvoDesign** find a designable molecule.
   - Have fun!


Happy enzyme redesigning with **REvoDesign**! If you encounter any issues during installation or usage, please consult the documentation or seek assistance from **REvoDesign** toolkit's support resources.

---
[![CircleCI](https://dl.circleci.com/insights-snapshot/circleci/97VjoN5in7mMaQdymWj7Qk/EVmMjwc2AXdvw6kpYNfFPj/main/test/badge.svg?window=30d&circle-token=465c8a4e66021ab11dd31f920a60a452b09a4cb8)](https://app.circleci.com/insights/circleci/97VjoN5in7mMaQdymWj7Qk/EVmMjwc2AXdvw6kpYNfFPj/workflows/test/overview?branch=main&reporting-window=last-30-days&insights-snapshot=true)

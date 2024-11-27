# REvoDesign

![portrait](https://raw.githubusercontent.com/YaoYinYing/artworks/main/DALL%C2%B7E%202024-01-22%2018.09.07%20-%20A%20sleek%20logo%20design%20with%20a%20human%20pilot%20dressed%20in%20yellow-pink%20uniform%20and%20a%20robot%20co-pilot%20in%20blue%2C%20both%20exhibiting%20friendly%20smiles.%20Abstract%20style.%20T.png)

---

## Platforms supported

![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-blue?logo=microsoft&color=blue&logoColor=blue)
![MacOS](https://img.shields.io/badge/MacOS-Sonoma-silver?logo=apple)
![Ubuntu](https://img.shields.io/badge/Ubuntu-20.04%20%7C%2022.04-orange?logo=ubuntu)
![architecture](https://img.shields.io/badge/Architecture-win--64%20%7C%20linux--64%20%7C%20osx--64%20%7C%20osx--arm64-6A5FBB)
![python-version](https://img.shields.io/badge/Python-3.9_%7C_3.10_%7C_3.11_%7C_3.12-3776AB?logo=python&logoColor=yellow)
[![pymol-bundle](https://tinyurl.com/pymol-bundle)](https://pymol.org/2/)
[![pymol-bundle-v3](https://tinyurl.com/pymol-bundle-v3)](https://pymol.org/)
[![pymol-open-source](https://tinyurl.com/pymol-open-source)](https://anaconda.org/conda-forge/pymol-open-source)
![pyqt](https://img.shields.io/badge/PyQt-5-41CD52?logo=qt)
[![image](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
---

## CI Status

[![Unit Test on tagging](https://github.com/YaoYinYing/REvoDesign/actions/workflows/unit_tests_tag.yml/badge.svg)](https://github.com/YaoYinYing/REvoDesign/actions/workflows/unit_tests_tag.yml)
[![Docker Image](https://github.com/YaoYinYing/REvoDesign/actions/workflows/docker-image.yml/badge.svg)](https://github.com/YaoYinYing/REvoDesign/actions/workflows/docker-image.yml)
[![CircleCI](https://dl.circleci.com/status-badge/img/gh/YaoYinYing/REvoDesign/tree/main.svg?style=svg&circle-token=CCIPRJ_HUET1GZsh4QvG9zsGJmd4n_37fb6a6c718247b0e7b4cf65e007a815279af3bd)](https://dl.circleci.com/status-badge/redirect/gh/YaoYinYing/REvoDesign/tree/main)

## Docker images

[![Docker Image Size](https://img.shields.io/docker/image-size/yaoyinying/revodesign-pssm-gremlin?style=social&logo=docker&label=server%20image%20size)](https://hub.docker.com/r/yaoyinying/revodesign-pssm-gremlin)

## Code checkings

[![pylint](https://github-image-cache.yaoyy.moe/badge_dir_with_uniq_name/REvoDesign/pylint/pylint_scan.svg)](https://github.com/Silleellie/pylint-github-action)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/3583a7e4923d4116931fcbab21492f21)](https://app.codacy.com?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![codecov](https://codecov.io/gh/YaoYinYing/REvoDesign/graph/badge.svg?token=2qSJ7cgk1b)](https://codecov.io/gh/YaoYinYing/REvoDesign)
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FYaoYinYing%2FREvoDesign.svg?type=shield&issueType=license)](https://app.fossa.com/projects/git%2Bgithub.com%2FYaoYinYing%2FREvoDesign?ref=badge_shield&issueType=license)
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FYaoYinYing%2FREvoDesign.svg?type=shield&issueType=security)](https://app.fossa.com/projects/git%2Bgithub.com%2FYaoYinYing%2FREvoDesign?ref=badge_shield&issueType=security)

## Introduction

Welcome to **REvoDesign** - a PyMOL plugin that makes enzyme redesign tasks easier for everyone. **REvoDesign** aims at facilitating enzyme redesign using a combination of structural and phylogenetic information, serving as a co-pilot for protein designers and leveraging the wealth of human knowledge in enzyme design.

### About the Plugin

Enzyme redesign is a complex task that requires a deep understanding of protein structures, substrate binding sites, and evolutionary relationships. **REvoDesign** Toolkit is designed to streamline this process by offering a range of tools and functionalities to assist protein designers in their endeavors.

### Basic Architecture Design

![software design](https://github-image-cache.yaoyy.moe/2024/04/9593eb8fc02494a9d2327e82eb52de0e.jpg)

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

## Dependencies wait list
> [!NOTE]
> These are the dependencies that are not yet implemented but will be added in the toolkit.
### Designers
- [ ] [SaProt](https://github.com/westlake-repl/SaProt)
- [ ] [Prime](https://github.com/ai4protein/Pro-Prime)
- [ ] [ProtSSN](https://github.com/tyang816/ProtSSN)
- [ ] [Native Pythia-ddG](https://github.com/Wublab/Pythia)
- [ ] [CarbonDesign](https://github.com/zhanghaicang/carbonmatrix_public)
- [ ] [ProtMamba](https://github.com/Bitbol-Lab/ProtMamba-ssm)
- [ ] [LigandMPNN](https://github.com/dauparas/LigandMPNN)
- [ ] [UniKP](https://github.com/Luo-SynBioLab/UniKP)
- [ ] [ByProt](https://github.com/BytedProtein/ByProt)

### Sidechain Solvers
- [ ] [AttnPacker](https://github.com/MattMcPartlon/AttnPacker)
- [ ] [opus_rota4](https://github.com/OPUS-MaLab/opus_rota4)
- [ ] [GeoPacker](https://github.com/PKUliujl/GeoPacker)

## Installation

With the recent updates, the installation process for **REvoDesign** Toolkit has been dramatically changed. Please follow the steps below:

1. **Install the PyMOL Graphic Installer**:

   Before installing the main program, you should install its installer towards the PyMOL menu like other PyMOL plugins. Follow these steps:

   - Open PyMOL.
   - Go to the "Plugin Manager" and choose "Install New Plugin."
   - Select "Install from PyMOLWiki or any URL."
   - Paste the following URL:
     ```text
      https://gist.githubusercontent.com/YaoYinYing/c1e8bfe0fc0b9c60bf49ea04a550a044/raw/REvoDesign_PyMOL.py
     ```
   - Click 'Fetch'
   [Install from URL](https://github-image-cache.yaoyy.moe/2024/11/690dbbf0929fd782c351cda4a2b36ec3.png)
   - When the Plugin Manager prompts you whether to proceed, click 'Yes' to install the plugin.
   [Proceed Installation](https://github-image-cache.yaoyy.moe/2024/11/5b8f155089ebb7632a99da814f0664fb.png)
   - Now setup the location to the plugin:
   [Setup Location](https://github-image-cache.yaoyy.moe/2024/11/42c676caf025a7a31ba7e72c4ea6b2ba.png) 
   - Click 'OK' to complete the installation.


   This will create an graphic installer for installing the core package of **REvoDesign**. Once the package is installed, this manager will allow you to access it from the PyMOL menu.

   ![installer](https://github-image-cache.yaoyy.moe/2024/04/6fd3d7838e0f92d88ab9fab99eeba250.png)


2. **Install the Main Program**:

   This installer, called `REvoDesign Package Manager`, is designed to manage all setup stuffs of **REvoDesign**.

   It contains the following features:
   - Installation from various sources:
     - Repository: Install from the remote repository.
     - Local clone/directory: Install from a local source code or a cloned repository.
     - Local file: Install from a released file with extension `.zip` or `tar.gz`.
   - Installation options:
     - Upgrade: Upgrade to the current release version of REvoDesign.
     - Verbose: Display detailed information about the installation process.
     - Version: Install a specific version of REvoDesign. This is a remote repository-only feature.
     - Commit: Install a specific commit of REvoDesign. This is a remote repository-only feature.
   - Network control:
     - Proxy: Set the proxy server for the installation process.
       - Supported protocols: `http`, `https`, `socks5`, `socks5h`.
     - Mirror: Set the pypi mirror for the installation process.
   - Extras:
     - None: Install the basic version of REvoDesign.
     - Customized: Install the customized version of REvoDesign. This will expand the right panel with additional options for one to choose from.
     - Everything: Install all the extras except `test`.
   - Cache: Set the cache directory for the REvoDesign.
     - Unchecked: Use the default cache directory.
     - Checked: Use a custom cache directory.
   - Self upgrade menu(activated by right clicks):
     - Upgrade this manager: fetch the latest revision of the installer.
     - Upgrade UI: fetch the latest revision of UI file.

![Installer](https://github-image-cache.yaoyy.moe/2024/11/8444a0aa16131c9feef8e3741b8f0d7a.png) 


   To install the main program, one have multiple ways:

   a. If one prefers to install from the remote repository, check `Repository` and click `Install`:

   b. If one has no access to the remote url because of the policy from network provider, one may install it from a cloned local repository or unzipped source code by choosing `Local clone`:

   ![local clone](https://github-image-cache.yaoyy.moe/2024/11/0f955519fe222c6188444f9265c36d5c.png)

   c. If one has a released zip/tarball, choosing the `Local file` option would make sense:

   ![local file, tarball](https://github-image-cache.yaoyy.moe/2024/11/ecd25285b7b53c5fa243cc12a601feb9.png)

   To install a specific commit/branch, check `Version` or `Commit` for more historical releases:

   ![remote commit 296044e0e7b8b7d30985a266e3341e89b66c61a6](https://github-image-cache.yaoyy.moe/2024/11/ffef3cf1d25098329fc2a58bc1d4cae0.png)
   
   This will fetch the repository and checkout the specified commit to install.

   d. To install with extra features, use `Customized` to pick, or install full version by selecting `Everything`:

   ![install with extras](https://github-image-cache.yaoyy.moe/2024/11/aa5b50c6a603b20bcad614910bbbc440.png)

   Only the selected packages will be installed.

   f. To uninstall, use the `Remove` button. Picked extras packages will be prompt to remove as well, and if user agrees, they will be removed after the main packages.

   g. Proxies and mirrors. The simplest way to create a socks5 proxy is to use `ssh` against a VPS server that has uncensored access to the Internet:

   ```bash
   ssh -D 7899 -C  root@<my.awesome.vps.ip> -p<ssh-port>
   ```
   
   This will create a socks5 proxy listening on `localhost:7899`.

   ![socks5 with mirror](https://github-image-cache.yaoyy.moe/2024/11/8c7849a70ea512f3b2166110a07a45ab.png)

   The installer can take trials on proxy-support bootstrap, by using pypi mirror site to eusure `pysocks` installed, then install the main package using the proxy one just input.

   h. Self upgrade. This installer is self-upgradeable. One can check its latest version by right-click any non-editing area of the installer and click `Upgrade this manager`. It will check the latest version and download it to the temp folder. Then a temperal diff file will be created to compare the current version with the latest one.

   ![Self upgrade prompt](https://github-image-cache.yaoyy.moe/2024/11/85e6e45ae880674a5081459d80687453.png)

   ![Diff self upgrade](https://github-image-cache.yaoyy.moe/2024/11/1d593a02db655f10b3083bbe84d9cb40.png)

   After the user confirms the upgrade, the script will overwrite the original file with the new one.

   **Extras table**

   | extras tag and packages |                        references                      |   explanations  |
   | :---------------------: | :----------------------------------------------------- | :-------------: |
   |   `ColabDesign`   | https://github.com/sokrypton/ColabDesign.git@v1.1.1    |     with JAX    |
   |     `DLPacker`    | https://github.com/YaoYinYing/DLPacker@pip-installable | with TensorFlow |
   |     `PIPPack`     | https://github.com/YaoYinYing/PIPPack@pip-installable  |  with PyTorch   |
   

> [!WARNING]
> ColabDesign uses Jax, which requires **Python >= 3.9**

> [!IMPORTANT]
> Please make sure that modern PyMOL version is fetched from [pymol-open-source](https://github.com/schrodinger/pymol-open-source) channel, instead of obsolete PyMOL bundle (* < v2.5.7*, shipped with **Python 3.7**) from [offical website](https://pymol.org/) or [schrodinger's conda channel](https://anaconda.org/schrodinger/pymol-bundle).

> [!IMPORTANT]
> ALSO, for MacOS users work with **Apple Silicon** and PyMOL bundle >2.5.7, `jaxlib` builded with `AVX` will not work under `Rosetta-2`. 
> Please consider using native build of `pymol-open-source` or building `jaxlib` from source.

**Doc**: [Building jaxlib from source](https://jax.readthedocs.io/en/latest/developer.html#building-jaxlib-from-source)

**Issue**: [CPU Support / Necessary AVX Instructions](https://github.com/google/jax/discussions/11436#discussioncomment-3121063)

1. **Getting started**:
   - In order to get started, you need to load/fetch a structure(`fetch 1SUO`, for example) into your PyMOL session.
   - Click `Menu` -> `REvoDesign` -> `Import PyMOL Session` to let **REvoDesign** find a designable molecule. Here is a keyboard shortcut: `Ctrl+N`.
   - Have fun!


Happy enzyme redesigning with **REvoDesign**! If you encounter any issues during installation or usage, please consult the documentation or seek assistance from **REvoDesign** toolkit's support resources.

---
[![CircleCI](https://dl.circleci.com/insights-snapshot/circleci/97VjoN5in7mMaQdymWj7Qk/EVmMjwc2AXdvw6kpYNfFPj/main/test/badge.svg?window=30d&circle-token=465c8a4e66021ab11dd31f920a60a452b09a4cb8)](https://app.circleci.com/insights/circleci/97VjoN5in7mMaQdymWj7Qk/EVmMjwc2AXdvw6kpYNfFPj/workflows/test/overview?branch=main&reporting-window=last-30-days&insights-snapshot=true) [![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FYaoYinYing%2FREvoDesign.svg?type=large&issueType=license)](https://app.fossa.com/projects/git%2Bgithub.com%2FYaoYinYing%2FREvoDesign?ref=badge_large&issueType=license)

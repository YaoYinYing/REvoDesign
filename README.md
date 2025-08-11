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
[![CircleCI](https://dl.circleci.com/status-badge/img/circleci/5R2YJrFV1L31sGti9Prtr2/Rzn5wDdkWvsvNweRbMD9Fa/tree/main.svg?style=svg&circle-token=CCIPRJ_L85MsaTT4udg9SpnKdXZsq_473d46b1be75d792f1d691b22b219cebfd4a4726)](https://dl.circleci.com/status-badge/redirect/circleci/5R2YJrFV1L31sGti9Prtr2/Rzn5wDdkWvsvNweRbMD9Fa/tree/main)

## Docker images

[![Docker Image Size](https://img.shields.io/docker/image-size/yaoyinying/revodesign-pssm-gremlin?style=social&logo=docker&label=server%20image%20size)](https://hub.docker.com/r/yaoyinying/revodesign-pssm-gremlin)

## Code checkings

[![pylint](https://github-image-cache.yaoyy.moe/badge_dir_with_uniq_name/REvoDesign/pylint/pylint_scan.svg)](https://github.com/Silleellie/pylint-github-action)
[![fuck-u-code score](https://github-image-cache.yaoyy.moe/badge_dir_with_uniq_name/REvoDesign/fuck-u-code/fuck-u-code_scan.svg)](https://github.com/YaoYinYing/fuck-u-code-github-action)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/3583a7e4923d4116931fcbab21492f21)](https://app.codacy.com?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![codecov](https://codecov.io/gh/YaoYinYing/REvoDesign/graph/badge.svg?token=2qSJ7cgk1b)](https://codecov.io/gh/YaoYinYing/REvoDesign)
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FYaoYinYing%2FREvoDesign.svg?type=shield&issueType=license)](https://app.fossa.com/projects/git%2Bgithub.com%2FYaoYinYing%2FREvoDesign?ref=badge_shield&issueType=license)
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FYaoYinYing%2FREvoDesign.svg?type=shield&issueType=security)](https://app.fossa.com/projects/git%2Bgithub.com%2FYaoYinYing%2FREvoDesign?ref=badge_shield&issueType=security)

---

## Introduction

Welcome to **REvoDesign** - a PyMOL plugin that makes enzyme redesign tasks easier for everyone. **REvoDesign** aims at facilitating enzyme redesign using a combination of structural and phylogenetic information, serving as a co-pilot for protein designers and leveraging the wealth of human knowledge in enzyme design.

### About the Plugin

Enzyme redesign is a complex task that requires a deep understanding of protein structures, substrate binding sites, and evolutionary relationships. **REvoDesign** Toolkit is designed to streamline this process by offering a range of tools and functionalities to assist protein designers in their endeavors.

---

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

---

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

---

## Installation

**REvoDesign** offers a user-friendly installation process using a graphical user interface (GUI).

### Step 1: Install the REvoDesign Package Manager

Before installing the main program, you need to install the REvoDesign Package Manager as a PyMOL plugin.

1. Open PyMOL.
2. Navigate to **Plugin > Plugin Manager** and select **Install New Plugin**.
3. Choose **Install from PyMOLWiki or any URL**.
4. Paste the following URL:
   ```text
   https://gist.githubusercontent.com/YaoYinYing/c1e8bfe0fc0b9c60bf49ea04a550a044/raw/REvoDesign_PyMOL.py
   ```
5. Click **Fetch**.

   ![Install from URL](https://github-image-cache.yaoyy.moe/2024/11/a68d9f8394a6b9dcf952deef264838b5.png)

6. Confirm the installation when prompted.

   ![Proceed Installation](https://github-image-cache.yaoyy.moe/2024/11/971af4a4f7b38ff6d4cee260fc6662d8.png)

7. Set the installation location (use the default if unsure) and click **OK**.

   ![Setup Location](https://github-image-cache.yaoyy.moe/2024/11/8cbdecd6c45c801957a52b65f1eb7c02.png)

Once installed, the REvoDesign Package Manager will appear in the PyMOL menu.

   ![REvoDesign Package Manager](https://github-image-cache.yaoyy.moe/2024/04/6fd3d7838e0f92d88ab9fab99eeba250.png)

---

### Step 2: Install the Main Program

The REvoDesign Package Manager simplifies the installation of the core **REvoDesign** program. It supports various installation methods and configurations:

#### Features:
- **Installation Sources:**
  - **Repository:** Install directly from the remote repository.
  - **Local clone/directory:** Install from a local source code or cloned repository.
  - **Local file:** Install from a `.zip` or `.tar.gz` archive.
- **Options:**
  - **Upgrade:** Update to the latest release version.
  - **Verbose:** Show detailed installation logs.
  - **Version/Commit:** Install a specific version or commit from the repository.
- **Network Control:**
  - **Proxy Support:** Configure HTTP, HTTPS, SOCKS5, or SOCKS5h proxies.
  - **Mirror:** Use a PyPI mirror for installations.
- **Extras:**
  - **Basic:** Default installation.
  - **Customized:** Select additional features.
  - **Everything:** Install all extras (excluding test packages).
- **Cache:** Choose a custom cache directory or use the default.
- **Self-Upgrades:** Upgrade the package manager and UI directly.

---

#### Installation Methods

1. **Remote Repository:**
   Select **Repository** and click **Install**.

2. **Local Clone:**
   Use **Local clone** to install from a local repository or unzipped source code.

   ![Local Clone](https://github-image-cache.yaoyy.moe/2024/11/0f955519fe222c6188444f9265c36d5c.png)

3. **Local File:**
   Select **Local file** to install from a `.zip` or `.tar.gz` file.

   ![Local File](https://github-image-cache.yaoyy.moe/2024/11/ecd25285b7b53c5fa243cc12a601feb9.png)

4. **Specific Version/Commit:**
   Check **Version** or **Commit** to install a specific release.

   ![Version/Commit](https://github-image-cache.yaoyy.moe/2024/11/ffef3cf1d25098329fc2a58bc1d4cae0.png)

5. **Customized/Extras:**
   Use **Customized** to select specific features or **Everything** for a full installation.

   ![Install with Extras](https://github-image-cache.yaoyy.moe/2024/11/aa5b50c6a603b20bcad614910bbbc440.png)

---

#### Uninstallation

Use the **Remove** button in the manager to uninstall. You can also remove selected extras.

---

#### Network Settings

Set up proxies and mirrors to bypass network restrictions. For example, create a SOCKS5 proxy using SSH:

```bash
ssh -D 7899 -C root@<your.vps.ip> -p<ssh-port>
```

Configure the proxy in the manager:

   ![Proxy Configuration](https://github-image-cache.yaoyy.moe/2024/11/8c7849a70ea512f3b2166110a07a45ab.png)

---

#### Self-Upgrades

Right-click any non-editing area of the manager and select **Upgrade this manager** to fetch the latest version.

   ![Self Upgrade](https://github-image-cache.yaoyy.moe/2024/11/85e6e45ae880674a5081459d80687453.png)

After confirming, the script will replace the existing manager with the updated version.

   ![Upgrade Confirmation](https://github-image-cache.yaoyy.moe/2024/11/4ddb145c98ac3fc472c2d9e4ffc23489.png)

---

You are now ready to use **REvoDesign** for your enzyme redesign projects!

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

## API Reference

See `docs/api/INDEX.md` for a browsable API reference with examples.

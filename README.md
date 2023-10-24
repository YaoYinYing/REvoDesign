## Introduction

Welcome to the initial release of the **PyMOL Enzyme Redesign Toolkit** - a powerful plugin aimed at facilitating enzyme redesign using a combination of structural and phylogenetic information. This toolkit serves as a co-pilot for protein designers, leveraging the wealth of human knowledge in enzyme design.

### About the Plugin

Enzyme redesign is a complex task that requires a deep understanding of protein structures, substrate binding sites, and evolutionary relationships. The PyMOL Enzyme Redesign Toolkit is designed to streamline this process by offering a range of tools and functionalities to assist protein designers in their endeavors.

### Key Features

In this first release, the plugin provides a set of essential tools to help protein designers with the following tasks:

1. **Surface Residue Analysis**: Identify surface residues exposed as solvent-accessible surface area (SASA) and design pocket identification based on substrates and/or cofactors, with customizable cutoffs.

2. **Mutant Loading**: Load available designable mutants through a PSSM-like table in CSV format, allowing for customizable rejections and preferences.

3. **Human Knowledge Supervision**: Perform human knowledge-supervised mutant selection within the PyMOL interface, utilizing structural views.

4. **Scale Reduction**: Reduce the scale of your design, making it suitable for low-throughput wet-lab validation by leveraging sequence clustering.

5. **Visualization**: Visualize mutant tables in PyMOL, whether they have been scored or not.

6. **Co-Evolution Analysis**: Search for possible inter-residue co-evolved residue pairs for effective mutants using the GREMLIN Markov random field profile.

This toolkit is your indispensable companion in the intricate journey of enzyme redesign. Whether you are a seasoned protein designer or just beginning your exploration, the PyMOL Enzyme Redesign Toolkit is here to simplify your workflow and enhance your enzyme engineering endeavors.

Please refer to the [documentation](link_to_documentation) for detailed instructions on how to use the toolkit and make the most of its features.

## Installation

With the recent updates, the installation process for the PyMOL Enzyme Redesign Toolkit has been dramatically changed. Please follow the steps below:

1. **Install the PyMOL Entrypoint**:

   Before installing the main program, you should install its entrypoint towards the PyMOL menu like other PyMOL plugins. Follow these steps:

   - Open PyMOL.
   - Go to the "Plugin Manager" and choose "Install New Plugin."
   - Select "Install from Local File."
   - Choose the entrypoint file located at the root directory of the repository:

   ```
   <repo-url-or-filepath>/REvoDesign.PyMOL.py
   ```

   This will create an function for installing the core package of REvoDesign. Once the package is installed, the entrypoint will allow you to access it from the PyMOL menu.

   

2. **Install the Main Program**:

   To install the main program from PyMOL commandline prompt, which is upgradable from internet access, you have two sources:

   a. If you prefer to install from the remote repository, use this command:

   ```python
   # From remote repo
   install_REvoDesign_via_pip
   ```

   b. If you have no access to the remote url because of the policy from network provider, you may install it from a cloned local repository or unzipped source code by running the following command:

   ```python
   # From a local repo
   install_REvoDesign_via_pip file:///local/path/to/repository/of/REvoDesign
   ```

   c. To install a specific commit/branch, use source@<commit/branch>:
   ```python
   # From remote repo, commit id ffe0219978da929bd1d183ca764c4c5d9da0bf96
   install_REvoDesign_via_pip https://github.com/YaoYinYing/REvoDesign@ffe0219
   ```

   Note that during the installation process, the window will freeze for a while.


Happy enzyme redesigning with REvoDesign! If you encounter any issues during installation or usage, please consult the documentation or seek assistance from the toolkit's support resources.
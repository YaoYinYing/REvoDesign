## Introduction

Welcome to the repo of the **REvoDesign** - a powerful plugin aimed at facilitating enzyme redesign using a combination of structural and phylogenetic information. This toolkit serves as a co-pilot for protein designers, leveraging the wealth of human knowledge in enzyme design.

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

## Prerequisites

Before you can start using the PyMOL Enzyme Redesign Toolkit, ensure that you have the necessary prerequisite packages installed. You can easily install these packages using the `system` function in the PyMOL console or from the command line prompt. Please follow these steps:

1. **Open PyMOL**: Launch PyMOL and ensure that you have access to the PyMOL console.

2. **Run the following commands** in the PyMOL console or your command line prompt:

```python
system pip install absl-py
system pip install joblib
system pip install matplotlib
system pip install pandas
system pip install scikit-learn
system pip install biopython
system pip install numpy
system pip install scipy
```

3. **Press Enter**: After pasting the above commands, press Enter to execute them.

4. **Wait for Installation**: During the installation process, PyMOL's window may freeze for a while. The duration of this freeze will depend on your bandwidth and connectivity to the PyPI site or its mirrors.

5. **Verification**: To verify that the packages have been successfully installed, you can check for any error messages in the console. If there are no errors, the installation should be complete.

Once you have successfully installed these prerequisite packages, you'll be ready to use the PyMOL Enzyme Redesign Toolkit to its full potential. If you encounter any issues during the installation process or while using the toolkit, please refer to the documentation or seek assistance from the toolkit's support resources.

Happy enzyme redesigning with REvoDesign!

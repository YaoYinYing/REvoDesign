### shortcuts (PyMOL commands)

Exports:

- shortcut_pssm2csv
- shortcut_real_sc
- shortcut_color_by_plddt
- shortcut_find_interface
- shortcut_color_by_mutation
- shortcut_dump_sidechains
- visualize_conformer_sdf
- getbox, get_pca_box, showbox, rmhet, movebox, showaxes, enlargebox

Examples (PyMOL command line):

- find interface by 4Å:
  - `find_interface protein_ranked_*, 4`
- dump sidechains for a group:
  - `dump_sidechains my_group, enabled_only=1, save_dir=png/sidechain_dump/`
- generate SMILES conformer and visualize in new window:
  - Python:

    ```python
    from REvoDesign.shortcuts.tools.ligand_converters import shortcut_smiles_conformer_single
    shortcut_smiles_conformer_single("MOR", "O=C....", 100, "./ligands/", "New Window")
    ```

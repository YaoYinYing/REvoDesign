'''
Shortcut function wrappers for PyMOL.

Here’s a concise summary of the wrapping structure for converting a **normal function** into a **menu dialog**:

---

### Wrapping Structure Summary

1. **Define the Function**:
   - Ensure the target function accepts keyword arguments (`**kwargs`) corresponding to the inputs collected from the dialog.

   Example:
   ```python
   def target_function(arg1: str, arg2: int):
       """
       Performs a task with the given arguments.

       Args:
           arg1 (str): A string argument.
           arg2 (int): An integer argument.
       """
       # Perform the task
   ```

2. **Create a Wrapped Version with `@dialog_wrapper`**:
   - Use the `@dialog_wrapper` decorator to define dialog metadata and input fields (`AskedValue` objects).
   - Include all static input options in the `options` argument.
   - Add logic to handle dynamic inputs if necessary.

   Example:
   ```python
   @dialog_wrapper(
       title="Task Dialog",
       banner="Provide the required parameters for the task.",
       options=(
           AskedValue(
               "arg1",
               "default_value",
               typing=str,
               reason="A description for arg1."
           ),
           AskedValue(
               "arg2",
               10,
               typing=int,
               reason="A description for arg2.",
               choices=range(1, 101),
           ),
       )
   )
   def wrapped_target_function(**kwargs):
       """
       Wraps the target_function to run with dialog inputs.

       Args:
           **kwargs: Collected parameters from the dialog.
       """
       with timing("Task Execution"):
           print(kwargs)
           run_worker_thread_with_progress(
               target_function,
               **kwargs,
               progress_bar=ConfigBus().ui.progressBar
           )
   ```

3. **Define a Menu Function**:
   - Call the wrapped function and append dynamic inputs if needed (e.g., file paths, user selections).
   - Provide additional logic for dynamically generated inputs.

   Example:
   ```python
   def menu_target_function():
       """
       Launches the dialog for the task with optional dynamic inputs.
       """
       dynamic_value = {
           "value": AskedValue(
               "dynamic_arg",
               "",
               typing=str,
               reason="A dynamically generated input.",
               file=True,  # Enables file browsing for this field
           ),
           "index": 0,  # Place it at the top of the table
       }
       wrapped_target_function(dynamic_values=[dynamic_value])
   ```

4. **Add File Dialog Support**:
   - For `AskedValue` fields with `file=True`, ensure the `ValueDialog` includes a "Browse" button to open a file dialog.

   Example:
   - The "Action" column dynamically displays the "Browse" button for file inputs.

---

### Benefits of the Structure

1. **Reusability**: The `@dialog_wrapper` decorator centralizes dialog logic.
2. **Dynamic Behavior**: Supports both static and dynamic inputs with customizable positions.
3. **Standardized Execution**: Ensures all wrapped functions include timing and threading for consistency.
4. **User-Friendly**: File browsing and dynamic options enhance usability.

'''


import json
import os
from typing import Literal

from pymol import cmd

from REvoDesign import issues

from ..driver.ui_driver import ConfigBus
from ..tools.customized_widgets import AskedValue, dialog_wrapper
from ..tools.pymol_utils import get_all_groups
from ..tools.utils import run_worker_thread_with_progress, timing
from .shortcuts import (color_by_plddt, dump_sidechains, pssm2csv, real_sc, smiles_conformer_batch,
                        smiles_conformer_single, visualize_conformer_sdf)


@dialog_wrapper(
    title="Dump Sidechains",
    banner="Dump all sidechain conformers of selected groups.",
    options=(
        AskedValue(
            "enabled_only",
            False,
            typing=bool,
            reason="Dump only enabled models."
        ),
        AskedValue(
            "save_dir",
            "png/sidechains",
            reason="Directory to save the sidechains."
        ),
        AskedValue(
            "height",
            1280,
            typing=int,
            reason="Height of the image."
        ),
        AskedValue(
            "width",
            1280,
            typing=int,
            reason="Width of the image."
        ),
        AskedValue(
            "dpi",
            150,
            typing=int,
            reason="DPI of the image.",
            choices=(150, 300, 600, 1200),
        ),
        AskedValue(
            "ray",
            True,
            typing=bool,
            reason="Use ray tracing."
        ),
        AskedValue(
            "hide_mesh",
            True,
            typing=bool,
            reason="Hide mesh."
        ),
        AskedValue(
            "neighborhood",
            3,
            typing=int,
            reason="Select with neighborhood area.",
            choices=range(1, 25),
        ),
        AskedValue(
            "recenter",
            False,
            typing=bool,
            reason="Recenter sidechains. Disable to make the background unmoved.",
        ),
        AskedValue(
            "reorient",
            True,
            typing=bool,
            reason="Re-orients the residue. "
            "Disable to prevent automatic orientation, useful when user wants to dump the residue they just focused on.",
        ),
    )
)
def wrapped_menu_dump_sidechains(**kwargs):
    """
    Runs the sidechain dumping process with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    with timing("Dumping sidechains"):
        print(kwargs)
        run_worker_thread_with_progress(
            dump_sidechains,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )


def menu_dump_sidechains(dump_all=False):
    """
    Prepares and launches the sidechain dumping menu.

    Args:
        dump_all (bool): If True, preselects all groups for sidechain dumping.
    """
    dynamic_value = {
        "value": AskedValue(
            "sele",
            val=get_all_groups() if dump_all else None,
            typing=list,
            reason="Select the models to dump sidechains.",
            choices=get_all_groups(),
        ),
        "index": 0,  # Specify the position in the options list
    }

    wrapped_menu_dump_sidechains(dynamic_values=[dynamic_value])


@dialog_wrapper(
    title="Color by pLDDT",
    banner="Color Predicted Protein structures by pLDDT values recorded in the B-factor column of the PDB file. "
           "Optionally, align to a target model and chain for comparison.",
    options=(
        AskedValue(
            "selection",
            "all",
            typing=str,
            reason="The PyMOL selection of objects or residues to color."
        ),
        AskedValue(
            "align_target",
            0,
            typing=int,
            reason="The rank order of the target in the selections (1-based). Set 0 to skip alignment."
        ),
        AskedValue(
            "chain_to_align",
            "A",
            typing=str,
            reason="The chain ID to align the selection to."
        ),
    )
)
def wrapped_color_by_plddt(**kwargs):
    """
    Runs the color_by_plddt function with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    with timing("Coloring by pLDDT"):
        print(kwargs)
        run_worker_thread_with_progress(
            color_by_plddt,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )


def menu_color_by_plddt():
    """
    Launches the wrapped dialog for coloring by pLDDT values.

    Dynamic values, if any, can be appended here before invoking the wrapped function.
    """
    wrapped_color_by_plddt()


@dialog_wrapper(
    title="PSSM to CSV",
    banner="Convert a PSSM raw file to a CSV format for downstream processing.",
    options=(
        AskedValue(
            "pssm",
            "",
            typing=str,
            reason="Path to the PSSM raw file to be converted.",
            source='File',  # Mark this as a file input
            required=True,
        ),
    )
)
def wrapped_pssm2csv(**kwargs):
    """
    Runs the PSSM to CSV conversion process with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    with timing("PSSM to CSV Conversion"):
        print(kwargs)
        run_worker_thread_with_progress(
            pssm2csv,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )


def menu_pssm2csv():
    """
    Launches the dialog for PSSM to CSV conversion.
    """
    wrapped_pssm2csv()


@dialog_wrapper(
    title="Set Sidechain Representation",
    banner="Set the molecular representation focusing on the sidechain or alpha carbon.",
    options=(
        AskedValue(
            "selection",
            "(all)",
            typing=str,
            reason="Atom selection to apply the representation to. Default is '(all)'."
        ),
        AskedValue(
            "representation",
            "lines",
            typing=str,
            reason="Representation style ('lines', 'sticks', 'spheres', 'dots').",
            choices=("lines", "sticks", "spheres", "dots"),
        ),
        AskedValue(
            "hydrogen",
            False,
            typing=bool,
            reason="Include hydrogens in the representation if True. Default is False."
        ),
    )
)
def wrapped_real_sc(**kwargs):
    """
    Runs the real_sc function with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    with timing("Set Sidechain Representation"):
        print(kwargs)
        run_worker_thread_with_progress(
            real_sc,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )


def menu_real_sc():
    """
    Launches the dialog for setting sidechain representation.
    """
    wrapped_real_sc()


@dialog_wrapper(
    title="Get SMILES Conformer",
    banner="Generate 3D conformers for a SMILES string using RDKit.",
    options=(
        AskedValue(
            "ligand_name",
            "",
            typing=str,
            reason="Name for the ligand. This will be used as the filename prefix.",
            required=True,
        ),
        AskedValue(
            "smiles",
            "",
            typing=str,
            reason="SMILES string to generate conformers for.",
            required=True,
        ),
        AskedValue(
            "num_conformer",
            100,
            typing=int,
            choices=range(50, 300)
        ),
        AskedValue(
            "save_dir",
            "./ligands/",
            typing=str,
            reason="Directory to save the conformers.",
            source='Directory',  # Mark this as a directory input
        ),
        AskedValue(
            "show_conformer",
            'New Window',
            typing=str,
            reason="Show the conformer in PyMOL if True. Default is New Window to launch a new window.",
            choices=('None', 'Current Window', 'New Window')
        ),
    )
)
def wrapped_smiles_conformer_single(**kwargs):
    """
    Runs the smiles_conformer_single function with parameters collected from the dialog.
    """
    # take out the show_conformer option and handle it separately
    show_conformer: Literal['None', 'Current Window', 'New Window'] = kwargs.pop("show_conformer")
    with timing("Get SMILES Conformer"):
        print(kwargs)
        run_worker_thread_with_progress(
            smiles_conformer_single,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )
    if show_conformer == 'None':
        return

    sdf_path = os.path.join(kwargs["save_dir"], f"{kwargs['ligand_name']}.sdf")

    if not os.path.isfile(sdf_path):
        raise issues.NoResultsError(f"No output results found for {kwargs['ligand_name']}. Expected file: {sdf_path}")

    visualize_conformer_sdf(sdf_path, show_conformer)


def menu_smiles_conformer_single():
    """
    Launches the dialog for generating 3D conformers for a SMILES string.
    """
    wrapped_smiles_conformer_single()

@dialog_wrapper(
    title="Get SMILES Conformers (Many)",
    banner="Generate 3D conformers for multiple SMILES strings using RDKit.",
    options=(
        AskedValue(
            "smiles",
            "",
            typing=str,
            reason="Path to SMILES json file to generate conformers for. Each line should be a separate SMILES string.",
            required=True,
            source='JsonInput'
        ),
        AskedValue(
            "num_conformer",
            100,
            typing=int,
        ),
        AskedValue(
            "save_dir",
            "./ligands/",
            typing=str,
            reason="Directory to save the conformers.",
            source='Directory',  # Mark this as a directory input
        ),
        AskedValue(
            "n_jobs",
            1,
            typing=int,
            choices=range(1, 16)
        ),
        AskedValue(
            "show_conformer",
            'None',
            typing=str,
            reason="Show the conformer in PyMOL if True. Default is New Window to launch a new window.",
            choices=('None', 'Current Window', 'New Window')
        ),
    )
)
def wrapped_smiles_conformer_batch(**kwargs):
    """
    Runs the smiles_conformer_batch function with parameters collected from the dialog.
    """
    # take out the show_conformer option and handle it separately
    show_conformer: Literal['None', 'Current Window', 'New Window'] = kwargs.pop("show_conformer")

    smiles=kwargs.pop("smiles")
    kwargs["smi"] = json.load(open(smiles, 'r'))
    with timing("Get SMILES Conformers (Many)"):
        print(kwargs)
        run_worker_thread_with_progress(
            smiles_conformer_batch,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )
    if show_conformer == 'None':
        return

    for k in kwargs["smi"]:
        sdf_path = os.path.join(kwargs["save_dir"], f"{k}.sdf")
        visualize_conformer_sdf(sdf_path, show_conformer)


def menu_smiles_conformer_batch():
    """
    Launches the dialog for generating 3D conformers for multiple SMILES strings.
    """
    wrapped_smiles_conformer_batch()
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
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from pymol import cmd
from pymol.Qt import QtCore, QtWidgets  # type: ignore
from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign import issues

from ..driver.group_register import CallableGroupValues
from ..driver.ui_driver import ConfigBus
from ..tools.customized_widgets import AskedValue, dialog_wrapper
from ..tools.pymol_utils import get_all_groups
from ..tools.utils import run_worker_thread_with_progress, timing
from .shortcuts import (color_by_plddt, dump_sidechains, pssm2csv, real_sc,
                        smiles_conformer_batch, smiles_conformer_single,
                        visualize_conformer_sdf)


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

    smiles = kwargs.pop("smiles")
    kwargs["smi"] = json.load(open(smiles))
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


@dialog_wrapper(
    title="Design with Profile",
    banner="Run mutant design with profile",
    options=(
        AskedValue(
            "profile",
            '',
            str,
            'Profile path for design',
            required=True,
            source='File'
        ),
        AskedValue(
            'profile_type',
            'PSSM',
            str,
            'Profile type',
            required=True,
            choices=CallableGroupValues.list_all_profile_parsers
        ),
        AskedValue(
            'keep_missing',
            True,
            bool,
            'Keep X in the sequence',
        ),
        AskedValue(
            'residue_range',
            '50-60,100-120',
            str,
            'Residue range to be shown, plotted and designed.'
            'Note that IndexOutOfRangeError will be raised if the range is not valid (on residue index where aa is `X`).',
            required=False,
            source='File'
        ),
        AskedValue(
            'view_highlight',
            'orient',
            str,
            'Whether to reorient the view to highlight the selected residues.',
            choices=('None', 'center', 'zoom', 'orient',)),
        AskedValue(
            'view_highlight_nbr',
            6,
            int,
            'Area to rezoom around',
            choices=range(0, 20),
            required=False
        )
    )
)
def wrapped_pssm_design(**kwargs):
    from RosettaPy.common.mutation import Mutation

    from ..bootstrap.set_config import ConfigConverter
    from ..common.Mutant import Mutant
    from ..common.MutantTree import MutantTree
    from ..common.MutantVisualizer import MutantVisualizer
    from ..phylogenetics.REvoDesigner import REvoDesigner
    from ..sidechain_solver.SidechainSolver import SidechainSolver
    from ..tools.customized_widgets import QbuttonMatrix
    from ..tools.mutant_tools import (existed_mutant_tree, expand_range,
                                      read_customized_indice)
    from ..tools.pymol_utils import (get_molecule_sequence,
                                     make_temperal_input_pdb)
    from ..tools.utils import (cmap_reverser, get_color,
                               run_worker_thread_with_progress)

    print(kwargs)

    bus = ConfigBus()
    ui = bus.ui

    molecule: str = bus.get_value('ui.header_panel.input.molecule', reject_none=True)
    chain_id: str = bus.get_value('ui.header_panel.input.chain_id', reject_none=True)

    reversed_mutant_effect = bus.get_value("ui.header_panel.cmap.reverse_score")
    cmap = cmap_reverser(
        cmap=bus.get_value("ui.header_panel.cmap.default"),
        reverse=reversed_mutant_effect,
    )

    if sequences := bus.get_value('designable_sequences', reject_none=True):
        designable_sequences = RosettaPyProteinSequence.from_dict(ConfigConverter.convert(sequences))
    elif sequences := get_molecule_sequence(molecule, chain_id, keep_missing=kwargs.get('keep_missing', True)):
        designable_sequences = RosettaPyProteinSequence.from_dict({chain_id: sequences})
    elif pdb := make_temperal_input_pdb(molecule, chain_id, reload=False):
        designable_sequences = RosettaPyProteinSequence.from_pdb(pdb)
    else:
        raise issues.NoInputError("Failed to get sequence from Config, Session or PDB file!")

    print(designable_sequences)
    sequence = designable_sequences.get_sequence_by_chain(chain_id)
    if not kwargs.get('keep_missing'):
        sequence = sequence.replace("-", "")
    print(sequence)

    # Get residue range, if none, use full length
    custom_indices_str: str = kwargs.get('residue_range')
    if not custom_indices_str:
        custom_indices_str = f'1-{len(sequence)}'
        print(f'Using default residue range: {custom_indices_str}')

    custom_indices_str = read_customized_indice(custom_indices_from_input=custom_indices_str.strip())

    # Parse profile with MutantVisualizer's profile reading
    profile_parser = MutantVisualizer(molecule=molecule, chain_id=chain_id)
    profile_parser.designable_sequences = designable_sequences
    profile_parser.sequence = sequence

    if not os.path.isfile(kwargs["profile"]):
        raise issues.NoInputError(f"Not Found: {kwargs['profile']=}")

    df = profile_parser.parse_profile(profile_fp=kwargs["profile"], profile_format=kwargs["profile_type"])

    if df is None or df.empty:
        raise issues.NoResultsError(
            f"Error occurs while parsing profile {kwargs['profile']} with format {kwargs['profile_type']}"
        )

    profile_alphabet = "".join(df.T.columns.to_list())
    print(df.head())

    col_name = df.columns.tolist()
    col_name.insert(0, 0)
    df = df.reindex(columns=col_name)
    df[df.columns[0]] = 0

    # Call REvoDesigner to setup and plot
    designer = REvoDesigner(kwargs['profile'])
    designer.molecule = molecule
    designer.chain_id = chain_id
    designer.sequence = sequence
    designer.cmap = cmap
    designer.profile_alphabet = profile_alphabet
    designer.pwd = os.getcwd()
    designer.design_case = 'default'
    designer.designable_sequences = designable_sequences

    designer.mutate_runner = SidechainSolver().refresh().mutate_runner
    designer.reject_aa = ''

    max_abs = np.max((np.abs(df.values.min()), df.values.max()))

    cutoff = [
        (bus.get_value("ui.mutate.min_score", float)),
        (bus.get_value("ui.mutate.max_score", float)),
    ]

    try:
        (
            mutation_json_fp,
            mutation_png_fp,
        ) = designer.plot_custom_indices_segments(
            df_ori=df,
            custom_indices_str=custom_indices_str,
            cutoff=cutoff,
            preferred_substitutions='',
        )

    except KeyError as e:
        raise issues.InvalidInputError(
            f'A Key Error occurred due to invalid residue range({kwargs["residue_range"]} --> {custom_indices_str}): \n{e}'
        ) from e

    custom_indices = expand_range(shortened_str=custom_indices_str, seperator=",", connector="-")
    if custom_indices == []:
        custom_indices = [resi for resi in range(1, len(sequence) + 1)]
    df_button_matrix = df.iloc[:, custom_indices]

    visualizer = MutantVisualizer(molecule=molecule, chain_id=chain_id)
    visualizer.designable_sequences = designable_sequences
    visualizer.cmap = cmap
    visualizer.min_score = -max_abs
    visualizer.max_score = max_abs

    designed_tree = existed_mutant_tree(sequences=designable_sequences, enabled_only=0)

    @dataclass
    class ProfilePair:
        df: pd.DataFrame

    def mutate_with_gridbuttons(row, col, matrix: QbuttonMatrix, ignore_wt=False):
        resn: str = matrix.alphabet_row[row]
        resi: int = int(matrix.alphabet_col[col + 1])
        wt_res = sequence[resi - 1]

        wt_score = df.loc[wt_res, str(resi - 1)]
        mut_score = df.loc[resn, str(resi - 1)]

        print(f"Mutating {resn}, {resi}, ignore_wt={ignore_wt}")

        sidechain_solver = run_worker_thread_with_progress(
            SidechainSolver().refresh,
            progress_bar=bus.ui.progressBar
        )
        if not sidechain_solver:
            raise issues.InternalError("Sidechain solver failed")

        visualizer.mutate_runner = sidechain_solver.mutate_runner

        group_id = f'mt_manual_{wt_res}{resi}_{wt_score}'
        mutant = Mutant([Mutation(chain_id=chain_id, position=resi, wt_res=wt_res, mut_res=resn)],
                        wt_protein_sequence=designable_sequences)
        mutant.mutant_score = mut_score
        visualizer.group_name = group_id
        if mutant not in designed_tree.all_mutant_objects:
            score = mutant.mutant_score

            color = get_color(cmap, score, -max_abs, max_abs)
            print(
                f" Visualizing {mutant.short_mutant_id} ({mutant.raw_mutant_id}) : {color} with {visualizer.mutate_runner.__class__.__name__}"
            )
            run_worker_thread_with_progress(
                visualizer.create_mutagenesis_objects,
                mutant_obj=mutant,
                color=color,
                in_place=True,
                progress_bar=bus.ui.progressBar
            )

            designed_tree.add_mutant_to_branch(branch=group_id, mutant=mutant.full_mutant_id, mutant_obj=mutant)
        else:
            print(f'{mutant} already exists in the tree')

        vhm = kwargs['view_highlight']
        if vhm == 'center':
            vhm_ = cmd.center
        elif vhm == 'zoom':
            vhm_ = cmd.zoom
        elif vhm == 'orient':
            vhm_ = cmd.orient
        else:
            return

        if kwargs['view_highlight_nbr'] > 0:
            vhm_(f'byres {mutant.full_mutant_id} around {kwargs["view_highlight_nbr"]}', animate=1)

    # Prepare the data for the button matrix
    df_pair = ProfilePair(df=df_button_matrix)
    print(df_pair)
    button_matrix = QbuttonMatrix(df_pair)
    button_matrix.sequence = sequence
    button_matrix.init_ui()
    button_matrix.report_axes_signal.connect(
        lambda row, col: mutate_with_gridbuttons(
            row,
            col,
            button_matrix,
            False,
        )
    )

    # Create a new dialog window for the button matrix
    window = QtWidgets.QWidget()  # This creates a standalone window.
    window.setWindowTitle("Mutant Profile Matrix")

    # Add a scroll area for the button matrix
    scroll_area = QtWidgets.QScrollArea()
    scroll_area.setWidget(button_matrix)
    scroll_area.setWidgetResizable(True)

    # Add horizontal scrollbar if columns exceed 150
    num_cols = button_matrix.pair.df.shape[1]  # Assuming the matrix's DataFrame determines the columns
    if num_cols > 150:
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    else:
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    layout = QtWidgets.QVBoxLayout()
    layout.addWidget(scroll_area)
    window.setLayout(layout)

    # Set size constraints for the window
    screen_width = QtWidgets.QApplication.primaryScreen().size().width()
    max_width = min(screen_width, 150 * button_matrix.button_size)
    window.setMaximumWidth(max_width)
    window.setMinimumWidth(800)  # Ensure the window isn't too narrow.

    # Center the window on the screen
    geometry = window.frameGeometry()
    geometry.moveCenter(QtWidgets.QApplication.primaryScreen().availableGeometry().center())
    window.move(geometry.topLeft())

    # Ensure the window is properly destroyed
    def cleanup_window():
        if hasattr(ui, 'open_windows') and window in ui.open_windows:
            ui.open_windows.remove(window)
        print("Window destroyed and cleaned up.")

    window.destroyed.connect(cleanup_window)

    # Show the window
    window.show()

    # Keep a reference so the dialog doesn't get garbage-collected prematurely
    if not hasattr(ui, 'open_windows'):
        ui.open_windows = []
    ui.open_windows.append(window)


def menu_pssm_design():
    return wrapped_pssm_design()

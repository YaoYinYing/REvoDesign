'''
This module contains the menu shortcuts for REvoDesign.
'''
# To create a dialog form, one must implement a wrapper function that
# decorated by `dialog_wrapper` and import it here


from REvoDesign.shortcuts.wrappers.designs import (wrapped_profile_pick_design,
                                                   wrapped_pssm2csv)
from REvoDesign.shortcuts.wrappers.esm2 import wrapped_esm1v
from REvoDesign.shortcuts.wrappers.exports import (
    wrapped_dump_fasta_from_struct, wrapped_menu_dump_sidechains)
from REvoDesign.shortcuts.wrappers.ligand_converters import (
    wrapped_smiles_conformer_batch, wrapped_smiles_conformer_single,
    wrapper_sdf2rosetta_params)
from REvoDesign.shortcuts.wrappers.mutation_effect_predictors import \
    wrapped_thermompnn
from REvoDesign.shortcuts.wrappers.represents import (
    wrapped_color_by_mutation, wrapped_color_by_plddt, wrapped_real_sc)
from REvoDesign.shortcuts.wrappers.rfdiffusion_tasks import (
    wrapped_general_rfdiffusion_task, wrapped_visualize_substrate_potentials)
from REvoDesign.shortcuts.wrappers.rosetta_tasks import (
    wrapped_fast_relax, wrapped_pross, wrapped_relax_w_ca_constraints,
    wrapped_rosettaligand)
from REvoDesign.shortcuts.wrappers.structure import wrapped_resi_renumber
from REvoDesign.shortcuts.wrappers.utils import wrapped_logger_level_setter
from REvoDesign.shortcuts.wrappers.vina_tools import (wrapped_alter_box,
                                                      wrapped_get_pca_box,
                                                      wrapped_getbox,
                                                      wrapped_rmhet)
from REvoDesign.tools.customized_widgets import AskedValue
from REvoDesign.tools.pymol_utils import get_all_groups


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
            multiple_choices=True
        ),
        "index": 0,
    }
    wrapped_menu_dump_sidechains([dynamic_value])


# One-liner bindings
menu_color_by_plddt = wrapped_color_by_plddt
menu_pssm2csv = wrapped_pssm2csv
menu_real_sc = wrapped_real_sc
menu_color_by_mutation = wrapped_color_by_mutation
menu_smiles_conformer_single = wrapped_smiles_conformer_single
menu_smiles_conformer_batch = wrapped_smiles_conformer_batch
menu_profile_pick_design = wrapped_profile_pick_design
menu_resi_renumber = wrapped_resi_renumber
menu_dump_fasta_from_struct = wrapped_dump_fasta_from_struct
menu_sdf2rosetta_params = wrapper_sdf2rosetta_params
menu_rosettaligand = wrapped_rosettaligand
menu_pross = wrapped_pross
menu_fast_relax = wrapped_fast_relax
menu_relax_w_ca_constraints = wrapped_relax_w_ca_constraints
menu_thermompnn = wrapped_thermompnn
menu_esm1v = wrapped_esm1v
menu_alterbox = wrapped_alter_box
menu_get_pca_box = wrapped_get_pca_box
menu_getbox = wrapped_getbox
menu_rmhet = wrapped_rmhet
menu_general_rfdiffusion_task = wrapped_general_rfdiffusion_task
menu_visualize_substrate_potentials = wrapped_visualize_substrate_potentials
menu_logger_level_setter = wrapped_logger_level_setter

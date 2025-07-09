'''
Shortcut functions of ligand file converting
'''


import json
import os
import sys
from typing import Literal

from RosettaPy.app.utils.smiles2param import SmallMoleculeParamsGenerator
from RosettaPy.utils.task import RosettaCmdTask, execute

from REvoDesign import ROOT_LOGGER, issues
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.shortcuts.function_utils import (smiles_conformer_batch,
                                        smiles_conformer_single,
                                        visualize_conformer_sdf)
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import timing

logging = ROOT_LOGGER.getChild(__name__)


def shortcut_smiles_conformer_single(
        ligand_name: str,
        smiles: str,
        num_conformer: int = 100,
        save_dir: str = './ligands/',
        show_conformer: Literal['None', 'Current Window', 'New Window'] = 'New Window'):
    """
    Runs the smiles_conformer_single function with parameters collected from the dialog.
    """
    # take out the show_conformer option and handle it separately
    with timing("Get SMILES Conformer"):
        run_worker_thread_with_progress(
            smiles_conformer_single,
            ligand_name=ligand_name,
            smiles=smiles,
            num_conformer=num_conformer,
            save_dir=save_dir,
            progress_bar=ConfigBus().ui.progressBar
        )
    if show_conformer == 'None':
        return

    sdf_path = os.path.join(save_dir, f"{ligand_name}.sdf")

    if not os.path.isfile(sdf_path):
        raise issues.NoResultsError(f"No output results found for {ligand_name}. Expected file: {sdf_path}")

    visualize_conformer_sdf(sdf_path, show_conformer)


def shortcut_smiles_conformer_batch(
        smiles: str,
        num_conformer: int = 100,
        save_dir: str = './ligands/',
        show_conformer: Literal['None', 'Current Window', 'New Window'] = 'None',
        n_jobs: int = 1,
):
    """
    Runs the smiles_conformer_batch function with parameters collected from the dialog.
    """

    smi = json.load(open(smiles))
    with timing("Get SMILES Conformers (Many)"):
        run_worker_thread_with_progress(
            smiles_conformer_batch,
            smi=smi,
            num_conformer=num_conformer,
            save_dir=save_dir,
            n_jobs=n_jobs,
            progress_bar=ConfigBus().ui.progressBar
        )
    if show_conformer == 'None':
        return

    for k in smi:
        sdf_path = os.path.join(save_dir, f"{k}.sdf")
        visualize_conformer_sdf(sdf_path, show_conformer)


def shortcut_sdf2rosetta_params(
        ligand_name: str,
        sdf_path: str,
        charge: int = 0,
        save_dir: str = './ligands_sdf/',
):
    '''
    Runs the sdf2rosetta_params function with parameters collected from the dialog.

    Args:

        '''
    converter = SmallMoleculeParamsGenerator(save_dir=save_dir)
    if not os.path.isfile(sdf_path):
        raise issues.InvalidInputError(f"No found ligand: {ligand_name}. Expected file: {sdf_path}")

    return execute(
        RosettaCmdTask(
            cmd=[
                sys.executable,
                os.path.join(converter._rosetta_python_script_dir, "molfile_to_params.py"),
                f"{sdf_path}",
                "-n",
                ligand_name,
                "--conformers-in-one-file",
                f"--recharge={str(charge)}",
                "-c",
                "--clobber",
            ],
            base_dir=save_dir,
            task_label=ligand_name,
        )
    )

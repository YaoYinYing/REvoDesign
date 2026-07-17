# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Utils for shortcuts
"""

import atexit
import os
import shutil

# Used for launching a user-requested PyMOL preview with an argv list.
import subprocess  # nosec B404
from typing import Literal

from pymol import cmd
from RosettaPy.app.utils.smiles2param import SmallMoleculeParamsGenerator

from REvoDesign import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)
_PREVIEW_PROCESSES: set[subprocess.Popen[bytes]] = set()


def _prune_finished_preview_processes() -> None:
    for process in tuple(_PREVIEW_PROCESSES):
        if process.poll() is not None:
            _PREVIEW_PROCESSES.discard(process)


def cleanup_conformer_preview_processes(timeout: float = 2.0) -> None:
    """Terminate PyMOL preview processes launched by this module."""
    for process in tuple(_PREVIEW_PROCESSES):
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=timeout)
        except Exception as exc:
            logging.debug("Could not stop PyMOL preview process %s: %s", process, exc)
        finally:
            _PREVIEW_PROCESSES.discard(process)


atexit.register(cleanup_conformer_preview_processes)


def _resolve_pymol_executable() -> str:
    pymol_executable = shutil.which("pymol")
    if pymol_executable is None:
        raise RuntimeError("Unable to launch PyMOL preview: 'pymol' executable was not found on PATH.")
    return pymol_executable


def visualize_conformer_sdf(sdf_file_path: str, show_conformer: Literal["New Window", "Current Window"]):
    """
    Visualize a ligand conformer file (SDF) in a new PyMOL window.

    Args:
        sdf_file_path (str): Path to the SDF file containing the conformers.
    """
    if show_conformer == "Current Window":
        # cmd.reinitialize()
        cmd.load(sdf_file_path)
        return

    # Get the absolute path of the directory containing the SDF file
    tmpdir = os.path.abspath(os.path.dirname(sdf_file_path))
    # Get the base name of the SDF file
    sdf_bn = os.path.basename(sdf_file_path)
    # Remove the file extension to get the file name
    sdf_bn_wo_ext, _ = os.path.splitext(sdf_bn)
    # Path for the temporary PML file
    pml_file_path = os.path.join(tmpdir, f"{sdf_bn_wo_ext}_load_to_preview.pml")

    # Create the PML file with visualization commands
    with open(pml_file_path, "w") as pmlh:
        # Command to load the SDF file
        pmlh.write(f"load {os.path.abspath(sdf_file_path)}\n")
        # Zoom and orient the view
        pmlh.write("zoom\norient\n")
        # Disable internal feedback in PyMOL
        pmlh.write("set internal_feedback, 0\n")
        # Set the viewport size
        pmlh.write("viewport 800, 600\n")
        # Set the background color to white
        pmlh.write("bg_color white\n")

    # Explicitly call a new PyMOL instance in the background
    pymol_command = [_resolve_pymol_executable(), "-xi", pml_file_path]
    # Launches a user-requested PyMOL preview with an argv list and a resolved executable.
    _prune_finished_preview_processes()
    process = subprocess.Popen(  # nosec B603
        pymol_command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _PREVIEW_PROCESSES.add(process)

    logging.info("PyMOL launched in the background with %s.", sdf_file_path)


def smiles_conformer_batch(smi: dict[str, str], num_conformer: int, save_dir: str, n_jobs: int = 1):
    """
    Generates 3D conformers for a SMILES string using RDKit.

    Args:
        smi (Dict[str, str]): Dictionary containing the name of the molecule as
            the key and the SMILES string as the value.
        num_conformer (int): Number of conformers to generate for each molecule.
        save_dir (str): Directory to save the generated conformer files.
        n_jobs (int, optional): Number of parallel jobs to run. Defaults to 1.
    """
    print(f"Converting {len(smi)} molecules to 3D conformers({num_conformer})...")
    # Initialize the SmallMoleculeParamsGenerator and convert the specified molecules
    converter = SmallMoleculeParamsGenerator(save_dir=save_dir, num_conformer=num_conformer)
    converter.convert(ligands=smi, n_jobs=n_jobs)


def smiles_conformer_single(
    ligand_name: str,
    smiles: str,
    num_conformer: int,
    save_dir: str,
):
    """
    Generates 3D conformers for a single SMILES string using RDKit.

    Args:
        ligand_name (str): Name of the ligand.
        smiles (str): SMILES string of the ligand.
        num_conformer (int): Number of conformers to generate.
        save_dir (str): Directory to save the generated conformer file.
    """
    return smiles_conformer_batch(smi={ligand_name: smiles}, num_conformer=num_conformer, save_dir=save_dir)

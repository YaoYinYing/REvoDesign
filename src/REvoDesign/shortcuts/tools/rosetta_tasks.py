'''
Shortcut functions on Rosetta-related tasks
'''

import os

from typing import List, Optional, Tuple, Union


from RosettaPy import (Rosetta, RosettaEnergyUnitAnalyser,
                       RosettaScriptsVariableGroup)
from RosettaPy.app.fastrelax import FastRelax
from RosettaPy.app.pross import PROSS
from RosettaPy.app.rosettaligand import RosettaLigand

from RosettaPy.node import node_picker


from REvoDesign import ROOT_LOGGER
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.shortcuts.utils import read_rosetta_node_config,

from REvoDesign.tools.utils import timing

logging = ROOT_LOGGER.getChild(__name__)

def shortcut_rosettaligand(
        pdb: str,
        ligands: List[str],
        nstruct: int = 10,
        save_dir: str = "tests/outputs",
        job_id: str = "rosettaligand",
        cst: Optional[str] = None,
        box_size: int = 30,
        move_distance: float = 0.5,
        gridwidth: int = 45,
        chain_id_for_dock="B",
        start_from_xyz: Optional[Tuple[float, float, float]] = None,
):
    '''
    Runs the rosettaligand function with parameters collected from the dialog.

    Args:
        pdb (str): Path to the input PDB file.
        ligands (List[str]): List of ligand SMILES strings.
        nstruct (int, optional): Number of structures to generate. Defaults to 10.
        save_dir (str, optional): Directory to save the output files. Defaults to "tests/outputs".
        job_id (str, optional): Job ID for the output files. Defaults to "rosettaligand".
        cst (Optional[str], optional): Path to the constraint file. Defaults to None.
        box_size (int, optional): Size of the box for docking. Defaults to 30.
        move_distance (float, optional): Distance to move the ligand during docking. Defaults to 0.5.
        gridwidth (int, optional): Width of the grid for docking. Defaults to 45.
        chain_id_for_dock (str, optional): Chain ID for docking. Defaults to "B".
        start_from_xyz (Optional[Tuple[float, float, float]], optional): Coordinates to start from. Defaults to None.

    '''
    bus = ConfigBus()

    node_config = read_rosetta_node_config()

    app = RosettaLigand(
        pdb=pdb,
        ligands=ligands,
        save_dir=save_dir,
        job_id=job_id,
        cst=cst,
        box_size=box_size,
        move_distance=move_distance,
        gridwidth=gridwidth,
        chain_id_for_dock=chain_id_for_dock,
        start_from_xyz=start_from_xyz,
        node=node_picker(
            node_type=bus.get_value('rosetta.node_hint', str, reject_none=True),  # type: ignore
            nproc=bus.get_value('ui.header_panel.nproc', int, reject_none=True),
            **node_config
        )
    )

    best_pdb = app.dock(nstruct=nstruct)

    logging.info(f"RosettaLigand docking finished. Best pdb: {best_pdb}")


def shortcut_pross(
        pdb: str,
        pssm: str,
        res_to_fix: str,
        res_to_restrict: str,
        nstruct_refine: int = 4,
        save_dir: str = "design/pross",
        job_id: str = "pross_design",
):
    '''
    Runs the pross function with parameters collected from the dialog.

    Args:
        pdb (str): Path to the input PDB file.
        pssm (str): Path to the PSSM file.
        res_to_fix (str): Residues to fix.
        res_to_restrict (str): Residues to restrict.
        nstruct_refine (int, optional): Number of structures to refine. Defaults to 4.
        save_dir (str, optional): Directory to save the output files. Defaults to "design/pross".
        job_id (str, optional): Job ID for the output files. Defaults to "pross_design".

    '''
    bus = ConfigBus()

    node_config = read_rosetta_node_config()

    pross = PROSS(
        pdb=pdb,
        pssm=pssm,
        res_to_fix=res_to_fix,
        res_to_restrict=res_to_restrict,
        save_dir=save_dir,
        job_id=job_id,
        node=node_picker(
            node_type=bus.get_value('rosetta.node_hint', str, reject_none=True),  # type: ignore
            nproc=bus.get_value('ui.header_panel.nproc', int, reject_none=True),
            **node_config
        )
    )
    best_refined = pross.refine(nstruct_refine)

    filters, filterscan_dir = pross.filterscan(best_refined)
    best_pdb_path = pross.design(filters=filters, refined_pdb=best_refined, filterscan_dir=filterscan_dir)

    logging.info(f"PROSS design finished. Best pdb: {best_pdb_path}")


def shortcut_fast_relax(
        pdb: str,
        relax_script: str,
        nstruct: int = 4,
        dualspace: bool = False,
        default_repeats: int = 3,
        job_id: str = 'fastrelax',
        save_dir: str = 'relaxed',
        relax_opts: Optional[List[Union[str, RosettaScriptsVariableGroup]]] = None,


):
    bus = ConfigBus()

    node_config = read_rosetta_node_config()

    class FastRelaxOpts(FastRelax):
        def run(self, nstruct: int = 8, default_repeats: int = 15,
                relax_opts: Optional[List[Union[str, RosettaScriptsVariableGroup]]] = None) -> RosettaEnergyUnitAnalyser:
            """
            Runs the fast relaxation process using the specified parameters.

            Args:
                nstruct (int, optional): The number of structures to generate. Defaults to 8.
                default_repeats (int, optional): The default number of repeats for relaxation. Defaults to 15.

            Returns:
                RosettaEnergyUnitAnalyser: An object for analyzing the energy units of the generated structures.
            """
            if relax_opts is None:
                relax_opts = []
            # Configure and run Rosetta for fast relaxation
            rosetta = Rosetta(
                bin="relax",
                opts=[
                    "-in:file:s",
                    os.path.abspath(self.pdb),
                    "-relax:script",
                    self.relax_script,
                    "-relax:default_repeats",
                    str(default_repeats),
                    "-out:prefix",
                    f"{self.instance}_fastrelax_",
                    "-out:file:scorefile",
                    f"{self.instance}_fastrelax.sc",
                    "-score:weights",
                    "ref2015_cart" if self.dualspace else "ref2015",
                    "-relax:dualspace",
                    "true" if self.dualspace else "false",
                ] + relax_opts,
                save_all_together=True,
                output_dir=os.path.join(self.save_dir, self.job_id),
                job_id=f"fastrelax_{self.instance}_{os.path.basename(self.relax_script)}",
                run_node=self.node,
                verbose=True
            )

            with timing("FastRelax"):
                rosetta.run(nstruct=nstruct)

            analyser = RosettaEnergyUnitAnalyser(rosetta.output_scorefile_dir)
            best_hit = analyser.best_decoy
            pdb_path = os.path.join(rosetta.output_pdb_dir, f'{best_hit["decoy"]}.pdb')

            print("Analysis of the best decoy:")
            print("-" * 79)
            print(analyser.df.sort_values(by=analyser.score_term))

            print("-" * 79)

            print(f'Best Hit on this FastRelax run: {best_hit["decoy"]} - {best_hit["score"]}: {pdb_path}')
            return analyser

    fast_relax = FastRelaxOpts(
        pdb=pdb,
        relax_script=relax_script,
        dualspace=dualspace,
        job_id=job_id,
        save_dir=save_dir,
        node=node_picker(
            node_type=bus.get_value('rosetta.node_hint', str, reject_none=True),  # type: ignore
            nproc=bus.get_value('ui.header_panel.nproc', int, reject_none=True),
            **node_config)
    )

    analyser = fast_relax.run(
        nstruct=nstruct,
        default_repeats=default_repeats,
        relax_opts=relax_opts,
    )

    best_relaxed_decoy = analyser.best_decoy

    logging.info(f"FastRelax finished. Best decoy: {best_relaxed_decoy}")


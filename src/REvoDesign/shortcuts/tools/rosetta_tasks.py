'''
Shortcut functions on Rosetta-related tasks
'''

import os
from typing import Any, List, Mapping, Optional, Sequence, Tuple, Union

from pymol import cmd
from RosettaPy import (Rosetta, RosettaEnergyUnitAnalyser,
                       RosettaScriptsVariableGroup)
from RosettaPy.app.abc import RosettaAppBase
from RosettaPy.app.fastrelax import FastRelax as FastRelax_Original
from RosettaPy.app.pross import PROSS as PROSS_Original
from RosettaPy.app.rosettaligand import RosettaLigand as RosettaLigandOriginal
from RosettaPy.node import NodeHintT

from REvoDesign import ROOT_LOGGER
from REvoDesign.citations import CitableModuleAbstract
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.sidechain.mutate_runner.RosettaMutateRelax import \
    MutateRelax_worker
from REvoDesign.tools.rosetta_utils import (copy_rosetta_citation,
                                            read_rosetta_node_config)
from REvoDesign.tools.utils import get_cited, timing

logging = ROOT_LOGGER.getChild(__name__)


class RosettaLigand(RosettaLigandOriginal, CitableModuleAbstract):

    __bibtex__: dict[str, Union[str, tuple]] = copy_rosetta_citation({
        "RosettaLigand": """
@article{https://doi.org/10.1002/prot.21086,
author = {Meiler, Jens and Baker, David},
title = {ROSETTALIGAND: Protein–small molecule docking with full side-chain flexibility},
journal = {Proteins: Structure, Function, and Bioinformatics},
volume = {65},
number = {3},
pages = {538-548},
keywords = {docking, protein–ligand docking, binding energy, Monte Carlo minimization, ROSETTA},
doi = {https://doi.org/10.1002/prot.21086},
url = {https://onlinelibrary.wiley.com/doi/abs/10.1002/prot.21086},
eprint = {https://onlinelibrary.wiley.com/doi/pdf/10.1002/prot.21086},
abstract = {Abstract Protein–small molecule docking algorithms provide a means to model the structure of protein–small molecule complexes in structural detail and play an important role in drug development. In recent years the necessity of simulating protein side-chain flexibility for an accurate prediction of the protein–small molecule interfaces has become apparent, and an increasing number of docking algorithms probe different approaches to include protein flexibility. Here we describe a new method for docking small molecules into protein binding sites employing a Monte Carlo minimization procedure in which the rigid body position and orientation of the small molecule and the protein side-chain conformations are optimized simultaneously. The energy function comprises van der Waals (VDW) interactions, an implicit solvation model, an explicit orientation hydrogen bonding potential, and an electrostatics model. In an evaluation of the scoring function the computed energy correlated with experimental small molecule binding energy with a correlation coefficient of 0.63 across a diverse set of 229 protein– small molecule complexes. The docking method produced lowest energy models with a root mean square deviation (RMSD) smaller than 2 Å in 71 out of 100 protein–small molecule crystal structure complexes (self-docking). In cross-docking calculations in which both protein side-chain and small molecule internal degrees of freedom were varied the lowest energy predictions had RMSDs less than 2 Å in 14 of 20 test cases. Proteins 2006. © 2006 Wiley-Liss, Inc.},
year = {2006}
}
    """,
        'RosettaLigand XML': r"""
@Inbook{Lemmon2012,
author="Lemmon, Gordon
and Meiler, Jens",
editor="Baron, Riccardo",
title="Rosetta Ligand Docking with Flexible XML Protocols",
bookTitle="Computational Drug Discovery and Design",
year="2012",
publisher="Springer New York",
address="New York, NY",
pages="143--155",
abstract="RosettaLigand is premiere software for predicting how a protein and a small molecule interact. Benchmark studies demonstrate that 70{\%} of the top scoring RosettaLigand predicted interfaces are within 2{\AA} RMSD from the crystal structure [1]. The latest release of Rosetta ligand software includes many new features, such as (1) docking of multiple ligands simultaneously, (2) representing ligands as fragments for greater flexibility, (3) redesign of the interface during docking, and (4) an XML script based interface that gives the user full control of the ligand docking protocol.",
isbn="978-1-61779-465-0",
doi="10.1007/978-1-61779-465-0_10",
url="https://doi.org/10.1007/978-1-61779-465-0_10"
}


"""
    })


class PROSS(PROSS_Original, CitableModuleAbstract):
    __bibtex__ = copy_rosetta_citation({
        'PROSS2': """@article{10.1093/bioinformatics/btaa1071,
author = {Weinstein, Jonathan Jacob and Goldenzweig, Adi and Hoch, ShlomoYakir and Fleishman, Sarel Jacob},
title = {PROSS 2: a new server for the design of stable and highly expressed protein variants},
journal = {Bioinformatics},
volume = {37},
number = {1},
pages = {123-125},
year = {2020},
month = {12},
abstract = {Many natural and designed proteins are only marginally stable limiting their usefulness in research and applications. Recently, we described an automated structure and sequence-based design method, called PROSS, for optimizing protein stability and heterologous expression levels that has since been validated on dozens of proteins. Here, we introduce improvements to the method, workflow and presentation, including more accurate sequence analysis, error handling and automated analysis of the quality of the sequence alignment that is used in design calculations.PROSS2 is freely available for academic use at https://pross.weizmann.ac.il. },
issn = {1367-4803},
doi = {10.1093/bioinformatics/btaa1071},
url = {https://doi.org/10.1093/bioinformatics/btaa1071},
eprint = {https://academic.oup.com/bioinformatics/article-pdf/37/1/123/50321722/btaa1071.pdf},
}

""",
        "PROSS": """
@article{10.1016/j.molcel.2016.06.012, author = {Goldenzweig, A. and Goldsmith, M. and Hill, S. E. and Gertman, O. and Laurino, P. and Ashani, Y. and Dym, O. and Unger, T. and Albeck, S. and Prilusky, J. and Lieberman, R. L. and Aharoni, A. and Silman, I. and Sussman, J. L. and Tawfik, D. S. and Fleishman, S. J.}, title = {Automated structure- and sequence-based design of proteins for high bacterial expression and stability}, journal = {Molecular Cell}, year = {2016}, volume = {63}, issue = {2}, pages = {337-346}, doi = {10.1016/j.molcel.2016.06.012} }"""
    })


class FastRelax(FastRelax_Original, CitableModuleAbstract):

    __bibtex__ = MutateRelax_worker.__bibtex__

    @get_cited
    def run(self, nstruct: int = 8, default_repeats: int = 15,
            opts: Optional[Sequence[Union[str, RosettaScriptsVariableGroup]]] = None) -> RosettaEnergyUnitAnalyser:
        """
        Runs the fast relaxation process using the specified parameters.

        Args:
            nstruct (int, optional): The number of structures to generate. Defaults to 8.
            default_repeats (int, optional): The default number of repeats for relaxation. Defaults to 15.

        Returns:
            RosettaEnergyUnitAnalyser: An object for analyzing the energy units of the generated structures.
        """
        if opts is None:
            opts = []
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
            ] + list(opts),
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
        node_hint=ConfigBus().get_value('rosetta.node_hint', str, reject_none=True),  # type: ignore
        node_config=node_config
    )

    best_pdb = app.dock(nstruct=nstruct)
    app.cite()

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

    pross = PROSS(
        pdb=pdb,
        pssm=pssm,
        res_to_fix=res_to_fix,
        res_to_restrict=res_to_restrict,
        save_dir=save_dir,
        job_id=job_id,
        node_hint=ConfigBus().get_value('rosetta.node_hint', str, reject_none=True),  # type: ignore
        node_config=read_rosetta_node_config()
    )
    best_refined = pross.refine(nstruct_refine)

    filters, filterscan_dir = pross.filterscan(best_refined)
    best_pdb_path = pross.design(filters=filters, refined_pdb=best_refined, filterscan_dir=filterscan_dir)

    logging.info(f"PROSS design finished. Best pdb: {best_pdb_path}")

    pross.cite()


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

    fast_relax = FastRelax(
        pdb=pdb,
        relax_script=relax_script,
        dualspace=dualspace,
        job_id=job_id,
        save_dir=save_dir,
        node_hint=ConfigBus().get_value('rosetta.node_hint', str, reject_none=True),  # type: ignore
        node_config=read_rosetta_node_config()
    )

    analyser = fast_relax.run(
        nstruct=nstruct,
        default_repeats=default_repeats,
        opts=relax_opts,
    )

    best_relaxed_decoy = analyser.best_decoy

    logging.info(f"FastRelax finished. Best decoy: {best_relaxed_decoy}")


class RelaxWithCaConstraints(RosettaAppBase, CitableModuleAbstract):

    __bibtex__ = MutateRelax_worker.__bibtex__

    def __init__(
            self,
            pdb: str,
            job_id: str = "relax_w_ca_constraints",
            save_dir: str = "tests/outputs",
            user_opts: Optional[List[str]] = None,
            node_hint: NodeHintT = "native",
            node_config: Optional[Mapping[str, Any]] = None,
            nstructs_per_round: int = 1,
            ncycles: int = 10,
            relax_opts: Optional[List[Union[str, RosettaScriptsVariableGroup]]] = None,
            **kwargs):
        super().__init__(job_id, save_dir, user_opts, node_hint, node_config, **kwargs)

        self.pdb = pdb
        self.nstructs_per_round = nstructs_per_round
        self.ncycles = ncycles

        self.relax_opts = relax_opts or []

    def run_a_round(self, round_id: int, newpdb: str) -> str:
        rosetta = Rosetta(
            'relax',
            opts=[
                '-relax:constrain_relax_to_start_coords',
                '-relax:coord_constrain_sidechains',
                '-relax:ramp_constraints', 'false',
                '-ignore_zero_occupancy', 'false',
                '-ex1',
                '-ex2',
                '-use_input_sc',
                '-no_nstruct_label', 'true',
                '-suffix', f'_R{round_id}',
                '-flip_HNQ',
                '-no_optH', 'false',
                '-in:file:s', os.path.abspath(newpdb)
            ] + self.relax_opts,
            save_all_together=True, output_dir=os.path.join(self.save_dir, self.job_id),
            job_id=f'{self.job_id}_round_{round_id}',
            run_node=self.node,
            verbose=True
        )
        with timing(f'relaxing with Ca Constrains (round #{round_id})'):
            rosetta.run(nstruct=self.nstructs_per_round)

        analyser = RosettaEnergyUnitAnalyser(rosetta.output_scorefile_dir)

        best_hit = analyser.best_decoy
        pdb_path = os.path.join(rosetta.output_pdb_dir, f'{best_hit["decoy"]}.pdb')

        print("Analysis of the best decoy:")
        print("-" * 79)
        print(analyser.df.sort_values(by=analyser.score_term))

        print("-" * 79)

        print(f'Best Hit on this Relax run: {best_hit["decoy"]} - {best_hit["score"]}: {pdb_path}')
        return pdb_path

    @get_cited
    def run(self, load_to_preview: bool = False):

        new_pdb_path = self.pdb
        if load_to_preview:
            # state starts from 1
            cmd.load(new_pdb_path, self.job_id, 1)
        for round_id in range(self.ncycles):
            new_pdb_path = self.run_a_round(round_id, new_pdb_path)
            if load_to_preview:
                cmd.load(new_pdb_path, self.job_id, round_id + 2)
        return new_pdb_path


def shortcut_relax_w_ca_constraints(
        pdb: str,
        nstructs_per_round: int = 1,
        ncycles: int = 10,
        save_dir: str = "tests/outputs",
        job_id: str = "relax_w_ca_constraints",
        relax_opts: Optional[List[Union[str, RosettaScriptsVariableGroup]]] = None,
        load_to_preview=False,
):

    app = RelaxWithCaConstraints(
        pdb=pdb,
        nstructs_per_round=nstructs_per_round,
        ncycles=ncycles,
        save_dir=save_dir,
        job_id=job_id,
        relax_opts=relax_opts,
        node_hint=ConfigBus().get_value('rosetta.node_hint', str, reject_none=True),  # type: ignore
        node_config=read_rosetta_node_config()
    )

    final_pdb = app.run(load_to_preview)

    logging.info(f"RelaxWithCaConstraints finished. Final pdb: {final_pdb}")

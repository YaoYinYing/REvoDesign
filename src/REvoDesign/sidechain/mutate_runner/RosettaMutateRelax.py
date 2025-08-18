'''
Wrapper for DLPacker
'''
import gc
import os
from typing import List

from REvoDesign import ConfigBus
from RosettaPy import Rosetta, RosettaScriptsVariableGroup

from RosettaPy.app.mutate_relax import ScoreClusters,script_dir
from RosettaPy.node import NodeHintT, node_picker

from REvoDesign.basic import MutateRunnerAbstract
from REvoDesign.common.mutant import Mutant
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.tools.rosetta_utils import is_run_node_available, read_rosetta_node_config
from REvoDesign.tools.utils import timing

logging = ROOT_LOGGER.getChild(__name__)

class MutateRelax(ScoreClusters):

    def score(self, branch: str, variants: List[Mutant]) -> Rosetta: # type: ignore
        """
        Scores the provided variants within a specific branch.

        Parameters:
        branch (str): Identifier of the branch.
        variants (List[str]): List of variants to be scored.

        Returns:
        RosettaEnergyUnitAnalyser: An object containing the analysis of the scoring results.
        """
        score_dir = self.save_dir
        pdb_bn=os.path.basename(self.pdb)
        os.makedirs(score_dir, exist_ok=True)

        rosetta = Rosetta(
            bin="rosetta_scripts",
            flags=[os.path.join(script_dir, "deps/mutate_relax/flags/cluster_scoring.flags")],
            opts=[
                "-in:file:s",
                os.path.abspath(self.pdb),
                "-parser:protocol",
                f"{script_dir}/deps/mutate_relax/xml/mutant_validation_temp.xml",
            ],
            output_dir=score_dir,
            save_all_together=True,
            job_id=branch,
            run_node=self.node,
        )
    
        variant_names=[v.format_as("${wt_res}${position}${mut_res}") for v in variants]

        branch_tasks = [
            {
                "rsv": RosettaScriptsVariableGroup.from_dict(
                    {
                        "muttask": self.muttask(variant_name, self.chain_id),
                        "mutmover": self.mutmover(variant_name, self.chain_id),
                        "mutprotocol": self.mutprotocol(variant_name),
                    }
                ),
                "-out:file:scorefile": f"{variant_name}.sc",
                "-out:prefix": f'{variant.full_mutant_id}.',
            }
            for variant_name,variant in zip(variant_names,variants)
        ]
        with timing("Mutate Relax"):
            rosetta.run(inputs=branch_tasks)

        # rename pdb files and move to output directory
        logging.info("Renaming pdb files")
        for m in variants:
            os.rename(
                os.path.join(rosetta.output_pdb_dir, f"{m.full_mutant_id}.{pdb_bn}"),
                os.path.join(self.save_dir, f"{m.short_mutant_id}.pdb"),
            )

        return rosetta
    def run(self, mutants: List[Mutant]): # type: ignore
        return self.score(branch='mutate_relax', variants=mutants)


class MutateRelax_worker(MutateRunnerAbstract):
    name: str = "Rosetta-MutateRelax"
    installed: bool =True

    def __init__(self, pdb_file: str, **kwargs):
        super().__init__(pdb_file)
        self.pdb_file = pdb_file
        self.temp_dir = self.new_cache_dir

        

        self.pdb_bn=os.path.basename(pdb_file)

        bus=ConfigBus()
        self.node_hint: NodeHintT = bus.get_value(
                    "rosetta.node_hint", default_value="native")  # type: ignore


        self.installed = is_run_node_available(self.node_hint)
        self.mutate_relax_instance= MutateRelax(
            pdb_file, 
            chain_id=bus.get_value("ui.header_panel.input.chain_id"),
            save_dir=self.new_cache_dir,
            job_id='mutate_relax',
            node=node_picker(node_type=self.node_hint, **read_rosetta_node_config()))

    def run_mutate(
        self,
        mutant: Mutant,
    ):
        self.mutate_relax_instance.node=node_picker(node_type=self.node_hint, **read_rosetta_node_config())
        ret:Rosetta=self.mutate_relax_instance.run([mutant])
        return os.path.join(self.temp_dir, f'{mutant.short_mutant_id}.pdb')

    def run_mutate_parallel(
        self,
        mutants: List[Mutant],
        nproc: int = 2,
    ) -> List[str]:
        # always refresh the node config before running
        self.mutate_relax_instance.node=node_picker(node_type=self.node_hint, **read_rosetta_node_config())
        ret:Rosetta=self.mutate_relax_instance.run(mutants)
        return [os.path.join(self.temp_dir, f'{mutant.short_mutant_id}.pdb') for mutant in mutants]
    
    __bibtex__ = {
        'Rosetta': """@article{10.1038/s41592-020-0848-2, author = {Leman, J. K. and Weitzner, B. D. and Lewis, S. M. and Adolf‐Bryfogle, J. and Alam, N. and Alford, R. F. and Aprahamian, M. L. and Baker, D. and Barlow, K. A. and Barth, P. and Basanta, B. and Bender, B. J. and Blacklock, K. and Bonet, J. and Boyken, S. E. and Bradley, P. and Bystroff, C. and Conway, P. and Cooper, S. and Correia, B. E. and Coventry, B. and Das, R. and Jong, R. M. d. and DiMaio, F. and Dsilva, L. and Dunbrack, R. L. and Ford, A. S. and Frenz, B. and Fu, D. and Geniesse, C. and Goldschmidt, L. and Gowthaman, R. and Gray, J. J. and Gront, D. and Guffy, S. L. and Horowitz, S. and Huang, P. and Huber, T. and Jacobs, T. M. and Jeliazkov, J. R. and Johnson, D. K. and Kappel, K. and Karanicolas, J. and Khakzad, H. and Khar, K. R. and Khare, S. D. and Khatib, F. and Khramushin, A. and King, C. and Kleffner, R. and Koepnick, B. and Kortemme, T. and Kuenze, G. and Kuhlman, B. and Kuroda, D. and Labonte, J. W. and Lai, J. and Lapidoth, G. and Leaver‐Fay, A. and Lindert, S. and Linsky, T. W. and London, N. and Lubin, J. H. and Lyskov, S. and Maguire, J. B. and Malmström, L. and Marcos, E. and Marcu, O. and Marze, N. and Meiler, J. and Moretti, R. and Mulligan, V. K. and Nerli, S. and Norn, C. and Ó’Conchúir, S. and Ollikainen, N. and Ovchinnikov, S. and Pacella, M. S. and Pan, X. and Park, H. and Pavlovicz, R. E. and Pethe, M. A. and Pierce, B. G. and Pilla, K. B. and Raveh, B. and Renfrew, P. D. and Burman, S. S. R. and Rubenstein, A. B. and Sauer, M. F. and Scheck, A. and Schief, W. R. and Schueler‐Furman, O. and Sedan, Y. and Sevy, A. M. and Sgourakis, N. G. and Shi, L. and Siegel, J. B. and Silva, D. and Smith, S. T. and Song, Y. and Stein, A. and Szegedy, M. and Teets, F. D. and Thyme, S. B. and Wang, R. Y. and Watkins, A. M. and Zimmerman, L. and Bonneau, R.}, title = {Macromolecular modeling and design in rosetta: recent methods and frameworks}, journal = {Nature Methods}, year = {2020}, volume = {17}, issue = {7}, pages = {665-680}, doi = {10.1038/s41592-020-0848-2} }""",
        'Rosetta3': """
@incollection{LEAVERFAY2011545,
title = {Chapter nineteen - Rosetta3: An Object-Oriented Software Suite for the Simulation and Design of Macromolecules},
editor = {Michael L. Johnson and Ludwig Brand},
series = {Methods in Enzymology},
publisher = {Academic Press},
volume = {487},
pages = {545-574},
year = {2011},
booktitle = {Computer Methods, Part C},
issn = {0076-6879},
doi = {https://doi.org/10.1016/B978-0-12-381270-4.00019-6},
url = {https://www.sciencedirect.com/science/article/pii/B9780123812704000196},
author = {Andrew Leaver-Fay and Michael Tyka and Steven M. Lewis and Oliver F. Lange and James Thompson and Ron Jacak and Kristian W. Kaufman and P. Douglas Renfrew and Colin A. Smith and Will Sheffler and Ian W. Davis and Seth Cooper and Adrien Treuille and Daniel J. Mandell and Florian Richter and Yih-En Andrew Ban and Sarel J. Fleishman and Jacob E. Corn and David E. Kim and Sergey Lyskov and Monica Berrondo and Stuart Mentzer and Zoran Popović and James J. Havranek and John Karanicolas and Rhiju Das and Jens Meiler and Tanja Kortemme and Jeffrey J. Gray and Brian Kuhlman and David Baker and Philip Bradley},
abstract = {We have recently completed a full rearchitecturing of the Rosetta molecular modeling program, generalizing and expanding its existing functionality. The new architecture enables the rapid prototyping of novel protocols by providing easy-to-use interfaces to powerful tools for molecular modeling. The source code of this rearchitecturing has been released as Rosetta3 and is freely available for academic use. At the time of its release, it contained 470,000 lines of code. Counting currently unpublished protocols at the time of this writing, the source includes 1,285,000 lines. Its rapid growth is a testament to its ease of use. This chapter describes the requirements for our new architecture, justifies the design decisions, sketches out central classes, and highlights a few of the common tasks that the new software can perform.}
}""",
    'RosettaScripts': """
@article{10.1371/journal.pone.0020161,
    doi = {10.1371/journal.pone.0020161},
    author = {Fleishman, Sarel J. AND Leaver-Fay, Andrew AND Corn, Jacob E. AND Strauch, Eva-Maria AND Khare, Sagar D. AND Koga, Nobuyasu AND Ashworth, Justin AND Murphy, Paul AND Richter, Florian AND Lemmon, Gordon AND Meiler, Jens AND Baker, David},
    journal = {PLOS ONE},
    publisher = {Public Library of Science},
    title = {RosettaScripts: A Scripting Language Interface to the Rosetta Macromolecular Modeling Suite},
    year = {2011},
    month = {06},
    volume = {6},
    url = {https://doi.org/10.1371/journal.pone.0020161},
    pages = {1-10},
    abstract = {Macromolecular modeling and design are increasingly useful in basic research, biotechnology, and teaching. However, the absence of a user-friendly modeling framework that provides access to a wide range of modeling capabilities is hampering the wider adoption of computational methods by non-experts. RosettaScripts is an XML-like language for specifying modeling tasks in the Rosetta framework. RosettaScripts provides access to protocol-level functionalities, such as rigid-body docking and sequence redesign, and allows fast testing and deployment of complex protocols without need for modifying or recompiling the underlying C++ code. We illustrate these capabilities with RosettaScripts protocols for the stabilization of proteins, the generation of computationally constrained libraries for experimental selection of higher-affinity binding proteins, loop remodeling, small-molecule ligand docking, design of ligand-binding proteins, and specificity redesign in DNA-binding proteins.},
    number = {6},

}""",
    'Rosetta All-Atom Energy Function': """
@article{10.1021/acs.jctc.7b00125, author = {Alford, R. F. and Leaver‐Fay, A. and Jeliazkov, J. R. and O’Meara, M. J. and DiMaio, F. and Park, H. and Shapovalov, M. V. and Renfrew, P. D. and Mulligan, V. K. and Kappel, K. and Labonte, J. W. and Pacella, M. S. and Bonneau, R. and Bradley, P. and Dunbrack, R. L. and Das, R. and Baker, D. and Kuhlman, B. and Kortemme, T. and Gray, J. J.}, title = {The rosetta all-atom energy function for macromolecular modeling and design}, journal = {Journal of Chemical Theory and Computation}, year = {2017}, volume = {13}, issue = {6}, pages = {3031-3048}, doi = {10.1021/acs.jctc.7b00125} }"""
    }
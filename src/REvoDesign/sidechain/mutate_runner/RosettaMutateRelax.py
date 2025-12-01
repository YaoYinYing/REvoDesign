'''
Wrapper for MutateRelax Sidechain Builder

TODO:
known issue:
    - when running with xtal structure, missing residues are not counted
'''
import os

from RosettaPy import Rosetta, RosettaScriptsVariableGroup
from RosettaPy.app.mutate_relax import ScoreClusters, script_dir
from RosettaPy.node import NodeHintT

from REvoDesign import ConfigBus
from REvoDesign.basic import MutateRunnerAbstract
from REvoDesign.common.mutant import Mutant
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.tools.rosetta_utils import (IS_ROSETTA_RUNNABLE,
                                            copy_rosetta_citation,
                                            is_run_node_available,
                                            read_rosetta_config,
                                            read_rosetta_node_config)
from REvoDesign.tools.utils import timing

logging = ROOT_LOGGER.getChild(__name__)


class MutateRelax(ScoreClusters):
    '''
    A wrapper around RosettaPy's ScoreClusters class to sample the sidechains
    '''

    def score(  # type: ignore
            self,
            branch: str,
            variants: list[Mutant],
            opts: list[str | RosettaScriptsVariableGroup] | None = None
    ) -> Rosetta:
        """
        Scores the provided variants within a specific branch.

        Parameters:
        branch (str): Identifier of the branch.
        variants (List[Mutant]): List of variants to be scored.

        Returns:
        Rosetta: An object containing the analysis of the scoring results.
        """
        # Set up the scoring result save directory
        if not opts:
            opts = []
        score_dir = self.save_dir
        pdb_bn = os.path.basename(self.pdb)
        os.makedirs(score_dir, exist_ok=True)

        # Initialize Rosetta object with scoring configuration
        rosetta = Rosetta(
            bin="rosetta_scripts",
            flags=[os.path.join(script_dir, "deps/mutate_relax/flags/cluster_scoring.flags")],
            opts=[
                "-in:file:s",
                os.path.abspath(self.pdb),
                "-parser:protocol",
                f"{script_dir}/deps/mutate_relax/xml/mutant_validation_temp.xml",
            ] + opts,
            output_dir=score_dir,
            save_all_together=True,
            job_id=branch,
            run_node=self.node,
            enable_progressbar=False,  # explicitly disable progressbar, as we use joblib to run tasks in parallel
        )

        # Format variant names for task configuration
        variant_names = [v.format_as("${wt_res}${position}${mut_res}") for v in variants]

        # Build scoring task configuration for each variant
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
            for variant_name, variant in zip(variant_names, variants)
        ]

        # Execute scoring tasks and record execution time
        with timing("Mutate Relax"):
            rosetta.run(inputs=branch_tasks)

        # Rename generated pdb files and move to output directory
        logging.info("Renaming pdb files")
        for m in variants:
            os.rename(
                os.path.join(rosetta.output_pdb_dir, f"{m.full_mutant_id}.{pdb_bn}"),
                os.path.join(self.save_dir, f"{m.short_mutant_id}.pdb"),
            )

        return rosetta

    def run(self, mutants: list[Mutant], opts: list[str | RosettaScriptsVariableGroup] | None = None):  # type: ignore
        """
        Execute the mutant scoring process

        This function calls the score method to evaluate the given list of mutants using the 'mutate_relax'
        branch strategy

        Parameters:
            mutants (List[Mutant]): List of mutants to be scored

        Returns:
            Scoring results, the specific type depends on the implementation of the score method
        """
        return self.score(branch='mutate_relax', variants=mutants, opts=opts)


class MutateRelax_worker(MutateRunnerAbstract):
    """
    MutateRelax_worker class for executing Rosetta's MutateRelax operations, supporting single
    or parallel protein mutation and structure optimization.

    Attributes:
        name (str): Worker name, identified as "Rosetta-MutateRelax".
        installed (bool): Indicates whether the node is available.
    """

    name: str = "Rosetta-MutateRelax"
    installed: bool = IS_ROSETTA_RUNNABLE

    def __init__(self, pdb_file: str, **kwargs):
        """
        Initialize MutateRelax_worker instance.

        Parameters:
            pdb_file (str): Path to the input PDB file.
            **kwargs: Additional optional parameters passed to the parent class initialization method.

        Attributes:
            pdb_file (str): Path to the input PDB file.
            temp_dir (str): Temporary cache directory path.
            pdb_bn (str): Base name of the PDB file (without path).
            node_hint (NodeHintT): Node hint information retrieved from the configuration bus.
            installed (bool): Check if the run node is available.
            mutate_relax_instance (MutateRelax): MutateRelax instance used to actually perform mutation
            and optimization operations.
        """
        super().__init__(pdb_file)
        self.pdb_file = pdb_file
        self.temp_dir = self.new_cache_dir

        # Get the base name of the PDB file
        self.pdb_bn = os.path.basename(pdb_file)

        # Read node hint information from configuration bus
        bus = ConfigBus()
        self.node_hint: NodeHintT = bus.get_value(
            "rosetta.node_hint", default_value="native")  # type: ignore

        # Check if the run node is available
        self.installed = is_run_node_available(self.node_hint)

        self.rosetta_general_opts: list[str] = read_rosetta_config()

        # Initialize MutateRelax instance
        self.mutate_relax_instance = MutateRelax(
            pdb_file,
            chain_id=bus.get_value("ui.header_panel.input.chain_id"),
            save_dir=self.new_cache_dir,
            job_id='mutate_relax',
            node_hint=self.node_hint,
            node_config=read_rosetta_node_config())

    def run_mutate(
        self,
        mutant: Mutant,
    ):
        """
        Execute MutateRelax operation on a single mutant.

        Parameters:
            mutant (Mutant): The mutant object to be processed.

        Returns:
            str: Path to the output PDB file.
        """
        # Refresh node configuration before each run
        self.mutate_relax_instance.node = self.node_hint, read_rosetta_node_config()
        self.mutate_relax_instance.run([mutant], opts=list(self.rosetta_general_opts))
        return os.path.join(self.temp_dir, f'{mutant.short_mutant_id}.pdb')

    def run_mutate_parallel(
        self,
        mutants: list[Mutant],
        nproc: int = 2,
    ) -> list[str]:
        """
        Process multiple mutants' MutateRelax operations in parallel.

        Parameters:
            mutants (List[Mutant]): List of mutant objects.
            nproc (int): Number of parallel processes, default is 2.

        Returns:
            List[str]: List of output PDB file paths for all mutants.
        """
        # Refresh node configuration before each run
        self.mutate_relax_instance.node = self.node_hint, read_rosetta_node_config()
        self.mutate_relax_instance.run(mutants, opts=list(self.rosetta_general_opts))
        return [os.path.join(self.temp_dir, f'{mutant.short_mutant_id}.pdb') for mutant in mutants]

    __bibtex__ = copy_rosetta_citation(
        {
            "Relax": """@article{10.1002/pro.2389, author = {Conway, P. and Tyka, M. D. and DiMaio, F. and Konerding, D. E. and Baker, D.}, title = {Relaxation of backbone bond geometry improves protein energy landscape modeling}, journal = {Protein Science}, year = {2013}, volume = {23}, issue = {1}, pages = {47-55}, doi = {10.1002/pro.2389} }"""
        }
    )

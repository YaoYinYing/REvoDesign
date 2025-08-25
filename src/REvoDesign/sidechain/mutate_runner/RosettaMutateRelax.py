import os
from typing import List, Optional, Union
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
    def score(  
            self,
            branch: str,
            variants: List[Mutant],
            opts: Optional[List[Union[str, RosettaScriptsVariableGroup]]] = None
    ) -> Rosetta:
        if not opts:
            opts = []
        score_dir = self.save_dir
        pdb_bn = os.path.basename(self.pdb)
        os.makedirs(score_dir, exist_ok=True)
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
            enable_progressbar=False,  
        )
        variant_names = [v.format_as("${wt_res}${position}${mut_res}") for v in variants]
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
        with timing("Mutate Relax"):
            rosetta.run(inputs=branch_tasks)
        logging.info("Renaming pdb files")
        for m in variants:
            os.rename(
                os.path.join(rosetta.output_pdb_dir, f"{m.full_mutant_id}.{pdb_bn}"),
                os.path.join(self.save_dir, f"{m.short_mutant_id}.pdb"),
            )
        return rosetta
    def run(self, mutants: List[Mutant], opts: Optional[List[str | RosettaScriptsVariableGroup]] = None):  
        return self.score(branch='mutate_relax', variants=mutants, opts=opts)
class MutateRelax_worker(MutateRunnerAbstract):
    name: str = "Rosetta-MutateRelax"
    installed: bool = IS_ROSETTA_RUNNABLE
    def __init__(self, pdb_file: str, **kwargs):
        super().__init__(pdb_file)
        self.pdb_file = pdb_file
        self.temp_dir = self.new_cache_dir
        self.pdb_bn = os.path.basename(pdb_file)
        bus = ConfigBus()
        self.node_hint: NodeHintT = bus.get_value(
            "rosetta.node_hint", default_value="native")  
        self.installed = is_run_node_available(self.node_hint)
        self.rosetta_general_opts: List[str] = read_rosetta_config()
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
        self.mutate_relax_instance.node = self.node_hint, read_rosetta_node_config()
        self.mutate_relax_instance.run([mutant], opts=list(self.rosetta_general_opts))
        return os.path.join(self.temp_dir, f'{mutant.short_mutant_id}.pdb')
    def run_mutate_parallel(
        self,
        mutants: List[Mutant],
        nproc: int = 2,
    ) -> List[str]:
        self.mutate_relax_instance.node = self.node_hint, read_rosetta_node_config()
        self.mutate_relax_instance.run(mutants, opts=list(self.rosetta_general_opts))
        return [os.path.join(self.temp_dir, f'{mutant.short_mutant_id}.pdb') for mutant in mutants]
    __bibtex__ = copy_rosetta_citation(
        {
            "Relax": """@article{10.1002/pro.2389, author = {Conway, P. and Tyka, M. D. and DiMaio, F. and Konerding, D. E. and Baker, D.}, title = {Relaxation of backbone bond geometry improves protein energy landscape modeling}, journal = {Protein Science}, year = {2013}, volume = {23}, issue = {1}, pages = {47-55}, doi = {10.1002/pro.2389} }"""
        }
    )
import os
from typing import List

from RosettaPy.analyser import RosettaEnergyUnitAnalyser
from RosettaPy.app.mutate_relax import ScoreClusters
from RosettaPy.node import NodeHintT, node_picker

from REvoDesign.logger import root_logger

logging = root_logger.getChild(__name__)


def score_clusters(
    pdb, chain_id, node_hint: NodeHintT, tasks_dir: str
) -> List[RosettaEnergyUnitAnalyser]:
    instance = os.path.basename(pdb).rstrip(".pdb")
    task_bn = os.path.basename(tasks_dir)
    cluster_scorer = ScoreClusters(
        pdb=pdb,
        chain_id=chain_id,
        save_dir="cluster_scorings/output/",
        job_id=f"{instance}_{node_hint}_{task_bn}",
        node=node_picker(node_type=node_hint),
    )
    ret = cluster_scorer.run(tasks_dir)
    for i, r in enumerate(ret):
        top = r.best_decoy

        logging.info("-" * 79)
        logging.info(f"Cluster {i} - {top['decoy']} : {top['score']}")
        logging.info(r.top(3))
        logging.info("-" * 79)
    return ret

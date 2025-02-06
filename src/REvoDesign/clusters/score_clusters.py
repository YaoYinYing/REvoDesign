'''
Score the clustered sequences with Rosetta
'''
import os
from typing import List

import pandas as pd
from RosettaPy.analyser import RosettaEnergyUnitAnalyser
from RosettaPy.app.mutate_relax import ScoreClusters
from RosettaPy.node import NodeHintT, node_picker

from REvoDesign.logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


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

    df_dict = {f'c.{i}': r.df for i, r in enumerate(ret)}

    # Add branch information to each dataframe
    for k, df in df_dict.items():
        df.loc[:, 'branch'] = k

    df_merge = pd.concat([df for df in df_dict.values()])

    logging.info(f'Saving cluster scores to cluster.{task_bn}_rosetta.xlsx/csv')
    df_merge.to_excel(f'cluster_scorings/output/cluster.{task_bn}_rosetta.xlsx')
    df_merge.to_csv(f'cluster_scorings/output/cluster.{task_bn}_rosetta.csv')

    return ret

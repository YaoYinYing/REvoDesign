import decimal
import glob
import itertools
import os
import pathlib
import random
import time

import pandas as pd
from Bio import SeqIO
from Bio.Align import PairwiseAligner
from Bio.Align import substitution_matrices
from joblib import parallel_backend
from REvoDesign.tools.logger import python_logging as logger
logging=logger.getChild(__name__)


import matplotlib

matplotlib.use('Agg')
from matplotlib import pyplot as plt
from sklearn.cluster import AgglomerativeClustering
from sklearn.neighbors import NearestCentroid

from REvoDesign.tools.utils import refresh_window, minibatches_generator
from REvoDesign.tools.customized_widgets import ParallelExecutor


class Clustering:
    def __init__(self, fastafile):
        self.fastafile = fastafile

        self.gap_open = -10
        self.gap_extend = -0.5
        self.substitution_matrix = 'PAM30'

        self._save_dir = './cluster'
        self.num_proc = 4
        self.batch_size = 100
        self.num_clusters = 15
        self.shuffle_variant = False
        self.debug = False
        self.resume = False
        self.overwrite = False

        self.seqs = {}
        self.seqs_list = []
        self.scores = [[]]
        self.records = None

        self.records_seqs = []

        self.cluster_output_fp = {}

    def initialize_aligner(self):
        # Add other instance variables here
        self.aligner = PairwiseAligner(
            mode='global',
            substitution_matrix=substitution_matrices.load(
                self.substitution_matrix
            ),
            open_gap_score=self.gap_open,
            extend_gap_score=self.gap_extend,
        )

    def global_alignment(self, seqs, indexes):
        (i, j) = indexes
        (seqA, seqB) = seqs

        # logging.debug(f'Getting mutants {seqA} and {seqB}...')
        # start_time = time.perf_counter()
        # i=self.records_seqs.index(seqA)
        # j=self.records_seqs.index(seqB)

        # end_time = time.perf_counter()

        # logging.debug(f'{seqA} and {seqB} are found. elapse time: {end_time - start_time}')

        r = self.aligner.align(seqA, seqB)

        # logging.debug(f'{i} and {j} are aligned. elapse time: {time.perf_counter() - end_time}')

        return (
            ''.join(str(r.sequences[0]).split('-')),
            ''.join(str(r.sequences[1]).split('-')),
            r.score,
            r[0].aligned[0][0][0],
            r[0].aligned[0][0][1],
            i,
            j,
        )

    def write_fasta_to_file(self, tmpfastafile):
        with open(tmpfastafile, 'w') as f:
            for line in self.seqs:
                f.write(">" + line + '\n')
                f.write(str(self.seqs[line]) + '\n')

    def plot_score_mtx(self, mtx, vmin=1, vmax=3):
        '''plot the mtx'''
        plt.figure(figsize=(5, 5))
        plt.imshow(
            mtx, cmap='Blues', interpolation='none', vmin=vmin, vmax=vmax
        )
        plt.grid(False)
        img_fp = f"{self.save_dir}/Cluster_score_mtx.png"

        plt.savefig(img_fp)
        self.cluster_output_fp['score'] = img_fp
        plt.close()

    def handle_calculation_result(self, results):
        # Handle the results of the calculation as needed
        logging.debug(f"Recieving results in length: {len(results)}")
        return results  # Store the results for further processing

    def set_and_write_clusters(self, progressbar):
        handle = open(self.fastafile, "r")
        self.records = list(SeqIO.parse(handle, "fasta"))
        if self.shuffle_variant:
            # random.shuffle(self.records)
            # https://docs.python.org/zh-cn/3/library/random.html#random.shuffle
            self.records = random.sample(self.records, len(self.records))

        # lookup = {}
        # for i in self.records:
        #     lookup[str(i.seq)] = str(i.name)

        nm_seqs = len(self.records)
        self.records_seqs = [r.seq for r in self.records]
        self.scores = [[0 for i in range(nm_seqs)] for j in range(nm_seqs)]

        # Generate values for each parameter
        seq_num = list(range(nm_seqs))

        # N!, reducing nearly a half of repetative works
        paramlist = itertools.combinations_with_replacement(
            self.records_seqs, 2
        )
        indexlist = itertools.combinations_with_replacement(seq_num, 2)

        # Generate processes equal to the number of cores
        logging.info(f"Number of cpus used: {self.num_proc}")
        self.buffer_file = f"{self.save_dir}/buffer.csv"

        workload = int((len(seq_num) + 1) * len(seq_num) / 2)

        def processing(paramlist, indexlist, batch_size, mode='w'):
            # Distribute the parameter sets evenly across the cores
            # Global alignment returns this: (s1, s2, score, start, end,i,j)
            logging.info(f'Job Number: {workload}')

            logging.info(f"Size of minibatch used: {batch_size}")
            batch_number = (
                workload // batch_size if batch_size < workload else 1
            )

            res_b = []
            batch_count = 0
            with open(
                self.buffer_file,
                mode,
            ) as bw:
                columns = ["S1", "S2", "Score", "Start", "End", "i", "j"]
                if mode == 'w':
                    bw.write(','.join(columns))
                    bw.write('\n')

                progressbar.setRange(0, batch_number)

                for sub_indexlist, sub_paramlist in zip(
                    minibatches_generator(indexlist, batch_size),
                    minibatches_generator(paramlist, batch_size),
                ):
                    batch_count += 1
                    start_time = time.perf_counter()

                    args_list = [
                        (sub_param, sub_index)
                        for sub_param, sub_index in zip(
                            sub_paramlist, sub_indexlist
                        )
                    ]

                    # parallel executor
                    parallel_executor = ParallelExecutor(
                        self.global_alignment, args_list, self.num_proc - 1
                    )

                    parallel_executor.result_signal.connect(
                        self.handle_calculation_result
                    )

                    parallel_executor.start()
                    logging.debug("Starting parallel execution...")

                    while not parallel_executor.isFinished():
                        refresh_window()
                        time.sleep(0.15)

                    progressbar.setValue(batch_count)

                    refresh_window()

                    sub_res = parallel_executor.handle_result()

                    end_time = time.perf_counter()
                    refresh_window()

                    logging.info(
                        f"Cluster progress: {decimal.Decimal(batch_count / batch_number) * 100:{5}.{4}} %   \t{batch_count} / {batch_number}\t elapse time: {end_time - start_time}"
                    )
                    res_b = [
                        ','.join([str(x) for x in list(item)])
                        for item in sub_res
                    ]

                    # logging.info(f"Write Buffer at {time.strftime('%Y/%m/%d %H:%M:%S')}")
                    bw.write('\n'.join(res_b))
                    bw.write('\n')
                    res_b = []

                progressbar.setValue(workload)

        logging.info("Calculating...")
        processing(paramlist, indexlist, self.batch_size, 'w')

        dfs = []
        columns = ["S1", "S2", "Score", "Start", "End", "i", "j"]
        # with open(buffer_file, 'r', newline='\n') as br:
        logging.info('reading buffer ...')

        df = pd.read_csv(self.buffer_file)
        df.astype(
            {
                'i': 'int64',
                'j': 'int64',
            }
        )

        for i, j, _score in zip(df.i, df.j, df.Score):
            self.scores[i][j] = float(_score)
            self.scores[j][i] = float(_score)

        with parallel_backend('threading', n_jobs=self.num_proc):
            logging.info('Clustering in progress ...')
            hc = AgglomerativeClustering(
                n_clusters=self.num_clusters, linkage='ward'
            )
            logging.info('Clustering is done.')
            y_hc = hc.fit_predict(self.scores)
            cluster_labels = hc.labels_

            clf = NearestCentroid()
            clf.fit(self.scores, y_hc)

        target_counts = pd.Series(y_hc).value_counts()
        target_counts.plot.barh()
        plt.title('Cluster Counts')
        plt.xlabel('Count')
        plt.ylabel('Cluster')
        img_fp = f'{self.save_dir}/variants_per_clusters.png'
        plt.savefig(img_fp)
        plt.close()

        self.cluster_output_fp['variant'] = img_fp

        labels = hc.labels_
        cluster = [[] for i in range(self.num_clusters)]
        for i in range(0, nm_seqs):
            cluster[labels[i]].append(self.records[i])

        cluster_centers_fp = (
            f"{self.save_dir}/cluster_centers_stochastic.fasta"
        )

        with open(cluster_centers_fp, 'w') as f:
            for i in range(0, self.num_clusters):
                rd_ = random.choice(cluster[i])
                seq_ = rd_.seq
                name_ = rd_.name + "_cluster_" + str(i)
                f.write(">" + name_ + "\n")
                f.write(str(seq_) + "\n")

        self.cluster_output_fp['cluster_centers'] = cluster_centers_fp

        self.cluster_output_fp['branches'] = []
        for i in range(0, len(cluster)):
            sub_cluster_branches = f"{self.save_dir}/c.{str(i)}.fasta"
            output_handle = open(sub_cluster_branches, "w")
            SeqIO.write(cluster[i], output_handle, "fasta")
            output_handle.close()
            self.cluster_output_fp['branches'].append(sub_cluster_branches)
        df_score = pd.DataFrame(self.scores)
        self.plot_score_mtx(
            df_score,
            vmin=min(df['Score'].to_list()),
            vmax=max(df['Score'].tolist()),
        )

    def run_clustering(self, progressbar):
        fastafile = pathlib.Path(self.fastafile).resolve()
        self.fasta_instance = fastafile.stem
        self.save_dir = (
            pathlib.Path(self._save_dir)
            .resolve()
            .joinpath(self.fasta_instance)
        )

        os.makedirs(self.save_dir, exist_ok=True)

        self._batch_size = self.batch_size
        self.batch_size = self._batch_size // self.num_proc * self.num_proc
        logging.info(f'fix batch_size {self._batch_size} to {self.batch_size}')
        self.set_and_write_clusters(progressbar)

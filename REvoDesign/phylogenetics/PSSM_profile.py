import os
import json
import hashlib
import time
import pandas as pd
import re
import tempfile
from absl import logging
from pymol import cmd
import matplotlib

matplotlib.use('Agg')
import matplotlib.pylab as plt
from REvoDesign.tools.utils import get_color, run_command, WITH_COLABDESIGN


from REvoDesign.tools.customized_widgets import (
    refresh_window,
    ParallelExecutor,
)

from REvoDesign.tools.pymol_utils import (
    get_molecule_sequence,
    find_all_protein_chain_ids_in_protein,
)

from REvoDesign.tools.mutant_tools import (
    expand_range,
    read_customized_indice,
    shorter_range,
    extract_mutants_from_mutant_id,
    extract_mutant_from_sequences,
)
from REvoDesign.common.MutantVisualizer import MutantVisualizer
from REvoDesign.phylogenetics.pymol_pssm_script import process_pssm_mutations

from REvoDesign.common.magic_numbers import DEFAULT_PROFILE_TYPE_GROUP


class PssmAnalyzer:
    def __init__(self, input_pssm_file):
        self.input_pse = ''
        self.output_pse = ''

        self.input_profile = input_pssm_file
        self.input_profile_format = 'PSSM'

        self.external_designer = None
        self.external_designer_temperature = 0.1
        self.external_designer_num_samples = 1
        self.batch = 1
        self.homooligomeric = False

        self.molecule = ''
        self.chain_id = 'A'
        self.pwd = '.'
        self.sequence = ''

        self.design_case = 'default'

        self.preffered_substitutions = ''
        self.reject_aa = 'PC'

        # use PSSM alphabet as default
        self.profile_alphabet = 'ARNDCQEGHILKMFPSTWYV'
        self.cmap = "bwr_r"

        self.results = []
        self.parallel_run = False
        self.nproc = 1

    def plot_custom_indices_segments(
        self,
        df_ori,
        pop=False,
        annotate=False,
        custom_indices_str='',
        cutoff=[-100, 100],
        preferred_substitutions=None,
    ):
        df = df_ori.copy()

        logging.debug(custom_indices_str)

        if custom_indices_str == '':
            custom_indices_str = f'1-{len(self.sequence)}'
            logging.debug(f' --> {custom_indices_str}')

        custom_indices = expand_range(
            shortened_str=custom_indices_str, seperator=',', connector='-'
        )
        logging.info(custom_indices)

        if custom_indices == []:
            custom_indices = [
                resi for resi in range(1, len(self.sequence) + 1)
            ]

        custom_indices = [0] + custom_indices

        df = df.iloc[:, custom_indices]

        sequence = list(self.sequence)
        sequence = [sequence[i - 1] for i in custom_indices[1:] if i >= 1]
        sequence = ''.join(sequence)

        if pop:
            df.pop(0)

        max_abs_value = df.abs().max().max()

        plt.figure(figsize=(0.31 * len(sequence), 5))
        pcm = plt.imshow(
            df, cmap=self.cmap, vmin=-max_abs_value, vmax=max_abs_value
        )

        al_a = list(self.profile_alphabet)

        x_ax = custom_indices[1:]
        plt.xticks(range(len(x_ax)), x_ax, rotation=45)
        plt.yticks(range(20), list(self.profile_alphabet))
        plt.grid(False)

        plt.colorbar(pcm).minorticks_on()

        if annotate:
            for pos in range(0, len(sequence)):
                for a in range(len(self.profile_alphabet)):
                    if al_a[a] == sequence[pos]:
                        plt.text(
                            pos,
                            a,
                            al_a[a],
                            ha="center",
                            va="center",
                            color="k",
                        )

        mutation_candidates = {
            "indices": custom_indices[1:],
            "cutoff": cutoff,
            "mutations": {},
        }
        mutations = []
        for _, resid in enumerate(custom_indices[1:]):
            wt_aa = sequence[_]
            pssm_scores = df_ori.iloc[:, resid]
            mutation_candidates['mutations'][resid] = {
                "wt": wt_aa,
                "wt_pssm": pssm_scores.loc[wt_aa],
                "candidates": {},
            }

            substitutions = pssm_scores[
                (cutoff[0] <= pssm_scores - pssm_scores.loc[wt_aa])
                & (pssm_scores - pssm_scores.loc[wt_aa] <= cutoff[1])
            ]

            # logging.debug('=' * 70)
            # logging.debug(
            #     f'\t{wt_aa}-{resid} ({pssm_scores.loc[wt_aa]}): {len(substitutions)} subsitutions in PSSM score cutoff {cutoff if type(cutoff) == float else str(cutoff)} ')
            # logging.debug('-' * 70)
            for mut_aa, pssm_score in substitutions.items():
                mutation_key = f"{wt_aa}{resid}{mut_aa}"
                if wt_aa == mut_aa:
                    continue
                if preferred_substitutions:
                    if (
                        wt_aa in preferred_substitutions.keys()
                        and mut_aa in preferred_substitutions[wt_aa]
                    ):
                        mutation_candidates['mutations'][resid]["candidates"][
                            mut_aa
                        ] = pssm_score
                        # logging.info(f"{mutation_key}: {pssm_score}")
                        mutations.append(mutation_key)
                else:
                    mutation_candidates['mutations'][resid]["candidates"][
                        mut_aa
                    ] = pssm_score
                    # logging.info(f"{mutation_key}: {pssm_score}")
                    mutations.append(mutation_key)

            # logging.debug('=' * 70)
            # logging.debug('\n')

        os.makedirs(f'{self.pwd}/mutations_pssm', exist_ok=True)

        indices_hash = hashlib.sha256(
            bytes(custom_indices_str.encode())
        ).hexdigest()
        mutation_json_fp = f'{self.pwd}/mutations_pssm/{time.strftime("%Y%m%d", time.localtime())}_{self.molecule}_{self.design_case}_{indices_hash[:10]}.json'
        mutation_png_fp = f'{self.pwd}/{self.molecule}_{self.design_case}_custom_indices_plot_{indices_hash}.png'
        mutant_table_fp = f'{self.pwd}/mutations_pssm/{time.strftime("%Y%m%d", time.localtime())}_{self.molecule}_{self.design_case}_{indices_hash[:10]}_mut.txt'
        json.dump(mutation_candidates, open(mutation_json_fp, 'w'), indent=2)

        plt.savefig(mutation_png_fp)
        plt.close()

        with open(mutant_table_fp, 'w') as mut_file:
            mut_file.write('\n'.join(mutations))

        return mutation_json_fp, mutant_table_fp, mutation_png_fp

    def validate_preffered_mutation_string(
        self,
        preffered_mutation_string,
    ):
        pattern = f'^[{"".join(self.profile_alphabet)}]:[{"".join(self.profile_alphabet)}]+$'
        preffered_mutation_string = preffered_mutation_string.replace(
            '[', ''
        ).replace(']', '')
        if re.match(pattern, preffered_mutation_string):
            return True
        else:
            return False

    def parse_preffered_mutation_string(self, preffered_str):
        preffered_dict = {
            _preffered_sub[0]: [res for res in _preffered_sub[2:]]
            for _preffered_sub in preffered_str.split(' ')
            if self.validate_preffered_mutation_string(_preffered_sub)
        }

        return preffered_dict

    def setup_parameters_for_external_designer(self):
        all_chains = find_all_protein_chain_ids_in_protein(sele=self.molecule)

        if len(all_chains) == 1 or (not self.homooligomeric):
            design_chain_id = [self.chain_id]
        else:
            design_chain_id = [self.chain_id] + [
                chain_id
                for chain_id in all_chains
                if chain_id != self.chain_id
                and get_molecule_sequence(
                    molecule=self.molecule, chain_id=chain_id
                )
                == self.sequence
            ]
            if len(design_chain_id) < 2:
                logging.warning(
                    f'No homooligomer found for chain {self.chain_id}, ignore `homooligomeric` setting'
                )
                self.homooligomeric = False
        self.design_chain_id = design_chain_id

    def setup_external_designer(
        self,
        custom_indices_str='',
    ):
        from REvoDesign.external_designer import EXTERNAL_DESIGNERS

        if not self.input_profile_format in EXTERNAL_DESIGNERS.keys():
            logging.error(
                f'External design {self.input_profile_format} is not registed in `ExternalDesigners.py`'
            )
            return

        # help msg if MPNN is called yet not installed.
        if self.input_profile_format == 'ProteinMPNN':
            if not WITH_COLABDESIGN:
                logging.error(
                    'ColabDesign is not available. Please install it manually then restart pymol for taking effort.'
                    '`system pip -q install git+https://github.com/sokrypton/ColabDesign.git@v1.1.1`'
                )
                return

        # expand design residue index
        expanded_custom_indices = expand_range(
            shortened_str=custom_indices_str, connector='-', seperator=','
        )

        # setup parameters for external designer
        self.setup_parameters_for_external_designer()

        if not (
            self.external_designer_temperature
            and self.external_designer_num_samples
        ):
            logging.error(f'Missing input for external designer')
            return

        magician = EXTERNAL_DESIGNERS[self.input_profile_format]

        # setup MPNN designer
        logging.info(f'Starting {self.input_profile_format}, this may take a while.')
        if self.input_profile_format == 'ProteinMPNN':
            self.external_designer = magician(
                molecule=self.molecule,
                fix_pos=','.join(
                    [
                        f"{self.chain_id}{indice}"
                        for indice in shorter_range(
                            expanded_custom_indices, connector='-'
                        ).split('+')
                    ]
                ),
                inverse=True,
                rm_aa=','.join(list(self.reject_aa)) if self.reject_aa else None,
                chain=','.join(self.design_chain_id),
                homooligomeric=self.homooligomeric,
            )
            return

    def design_protein_using_external_designer(
        self, custom_indices_fp, progress_bar
    ):
        custom_indices_str = read_customized_indice(custom_indices_from_input=custom_indices_fp)
        self.setup_external_designer(custom_indices_str=custom_indices_str)
        if not self.external_designer:
            logging.error(
                f'Failed to initialize external designer {self.input_profile_format}'
            )
            self.output_pse = ''
            return

        logging.info(f'Setting preffered substitutions {self.preffered_substitutions}.')
        self.external_designer.preffer_substitutions(
            aa=self.preffered_substitutions
        )

        logging.info(f'Starting design with {self.input_profile_format}, this may take a long time, depending on batch and design number you required.')
        designs = self.external_designer.designer(
            num=self.external_designer_num_samples,
            batch=self.batch,
            temperature=self.external_designer_temperature,
        )
        logging.info('Design is done. Parsing the results...')

        mutant_objs = []
        score_list = []

        for seq, score in zip(designs['seq'], designs['score']):
            mutant_obj = extract_mutant_from_sequences(
                mutant_sequence=seq, wt_sequence=self.sequence
            )
            mutant_obj.set_mutant_score(score)
            score_list.append(score)
            mutant_objs.append(mutant_obj)

        visualizer = MutantVisualizer(
            molecule=self.molecule, chain_id=self.chain_id
        )
        visualizer.sequence = self.sequence

        visualizer.save_session = self.output_pse
        visualizer.input_session = self.input_pse

        visualizer.parallel_run = self.parallel_run
        visualizer.nproc = self.nproc

        visualizer.group_name = self.design_case

        visualizer.cmap = self.cmap
        visualizer.min_score = min(score_list)
        visualizer.max_score = max(score_list)
        visualizer.mutant_list = mutant_objs
        visualizer.run_mutagenesis_tasks(progress_bar=progress_bar)
        self.output_pse = visualizer.save_session
        logging.info("Done.")


    def design_protein_using_pssm(
        self,
        custom_indices_fp='',
        cutoff=[-100, 100],
    ):
        custom_indices_str=read_customized_indice(custom_indices_from_input=custom_indices_fp)

        profile_parser = MutantVisualizer(
            molecule=self.molecule, chain_id=self.chain_id
        )
        df = profile_parser.parse_profile(
            profile_fp=self.input_profile,
            profile_format=self.input_profile_format,
        )

        if df is None or df.empty:
            logging.error(
                f'Error occurs while parsing profile {self.input_profile} with format {self.input_profile_format}'
            )
            return

        # refresh profile alphabet based on profile reading
        self.profile_alphabet = ''.join(df.T.columns.to_list())

        logging.debug(df.head())

        col_name = df.columns.tolist()
        col_name.insert(0, 0)
        df = df.reindex(columns=col_name)
        df[df.columns[0]] = 0

        if len(self.preffered_substitutions) > 0:
            preffered_dict = self.parse_preffered_mutation_string(
                preffered_str=self.preffered_substitutions
            )
            logging.info(self.preffered_substitutions)
            logging.info(preffered_dict)
        else:
            preffered_dict = None

        (
            mutation_json_fp,
            mutant_table_fp,
            mutation_png_fp,
        ) = self.plot_custom_indices_segments(
            df,
            pop=True,
            custom_indices_str=custom_indices_str,
            annotate=True,
            cutoff=cutoff,
            preferred_substitutions=preffered_dict,
        )

        return mutation_json_fp, mutant_table_fp, mutation_png_fp

    @staticmethod
    def process_position(
        position,
        wt_residue,
        wt_pssm_score,
        candidates,
        input_pse,
        molecule,
        chain_id,
        reject,
        create_full_pdb,
        max_abs_pssm,
        cmap,
    ):
        logging.info(
            f'Runing mutagenesis test for position {position}{wt_residue}...'
        )
        logging.info(f"Candidates for design: {candidates}")
        temp_dir = tempfile.mkdtemp(prefix='pymol_pssm_')
        temp_session_path = os.path.join(temp_dir, f"position_{position}.pse")

        cmd.reinitialize()
        cmd.load(input_pse)
        cmd.hide('surface')
        cmd.center(molecule)
        refresh_window()

        for new_residue, new_residue_score in candidates.items():
            if reject and (new_residue in reject or wt_residue in reject):
                logging.info(
                    f"Skipping rejected mutation: {position}{wt_residue} to {new_residue}"
                )
                refresh_window()
                continue
            else:
                refresh_window()
                color = get_color(
                    cmap, new_residue_score, -max_abs_pssm, max_abs_pssm
                )

                logging.info(
                    f"Mutating {position}{wt_residue}( {wt_pssm_score} ) to {new_residue}( {new_residue_score} ): {color}"
                )
                visualizer = MutantVisualizer(
                    molecule=molecule, chain_id=chain_id
                )
                visualizer.group_name = (
                    f"mt_{wt_residue}{position}_{str(wt_pssm_score)}"
                )
                visualizer.full = create_full_pdb

                _, mutant_obj = extract_mutants_from_mutant_id(
                    mutant_string=f'{chain_id}{wt_residue}{position}{new_residue}_{new_residue_score}',
                    chain_id=chain_id,
                )

                visualizer.create_mutagenesis_objects(
                    mutant_obj=mutant_obj, color=color
                )

                refresh_window()
                time.sleep(0.01)

        refresh_window()
        cmd.hide('everything', 'hydrogens and polymer.protein')
        cmd.delete(molecule)
        cmd.save(temp_session_path)

        return temp_session_path

    def load_mutants_to_pymol_session(
        self,
        mutant_json,
        create_full_pdb,
        progress_bar,
    ):
        mutations = process_pssm_mutations(mutant_json)

        new_residue_scores = []
        for position, wt_residue, wt_pssm_score, candidates in mutations:
            for new_residue, new_residue_score in candidates.items():
                new_residue_scores.append(new_residue_score)

        if not new_residue_scores:
            logging.warning(f'No available designs!')
            return

        max_abs_pssm = max(
            abs(min(new_residue_scores)), abs(max(new_residue_scores))
        )

        mutagenesis_tasks = [
            (
                position,
                wt_residue,
                wt_pssm_score,
                candidates,
                self.input_pse,
                self.molecule,
                self.chain_id,
                self.reject_aa,
                create_full_pdb,
                max_abs_pssm,
                self.cmap,
            )
            for position, wt_residue, wt_pssm_score, candidates in mutations
            if candidates
        ]

        logging.info(
            f'Filter out empty tasks: {len(mutations) - len(mutagenesis_tasks)}'
        )

        progress_bar.setRange(0, 0)

        if self.parallel_run:
            parallel_executor = ParallelExecutor(
                self.process_position, mutagenesis_tasks, n_jobs=self.nproc
            )

            parallel_executor.start()

            while not parallel_executor.isFinished():
                refresh_window()
                time.sleep(0.001)

            progress_bar.setRange(0, len(mutagenesis_tasks))
            progress_bar.setValue(len(mutagenesis_tasks))

            self.results = parallel_executor.handle_result()
        else:
            progress_bar.setRange(0, len(mutagenesis_tasks))

            for mutagenesis_task in mutagenesis_tasks:
                self.results.append(self.process_position(*mutagenesis_task))

                # https://www.jianshu.com/p/38562df9e65d
                # refresh UI if calculation is not done.
                refresh_window()
                progress_bar.setValue(progress_bar.value() + 1)

            progress_bar.setValue(len(mutagenesis_tasks))

        progress_bar.setRange(0, 0)

        # call MutantVisualizer for merge sessions
        session_merger = MutantVisualizer(molecule='', chain_id='')
        session_merger.input_session = self.input_pse
        session_merger.save_session = self.output_pse
        session_merger.mutagenesis_sessions = self.results
        session_merger.merge_sessions_via_commandline()
        self.output_pse = session_merger.save_session
        progress_bar.setRange(0, 1)

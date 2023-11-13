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
from REvoDesign.tools.utils import (
    refresh_window,
    ParallelExecutor,
    get_color,
    extract_mutants,
    run_command,
    run_worker_thread_with_progress,
    make_temperal_input_pdb
)
from REvoDesign.common.MutantVisualizer import MutantVisualizer
from REvoDesign.tools.SessionMerger import PyMOLSessionMerger
from REvoDesign.phylogenetics.pymol_pssm_script import process_pssm_mutations


class PssmAnalyzer:
    def __init__(self, input_pssm_file):
        self.input_profile = input_pssm_file
        self.input_profile_format = 'PSSM'
        self.molecule = ''
        self.chain_id = 'A'
        self.pwd = '.'

        # use PSSM alphabet as default
        self.profile_alphabet = 'ARNDCQEGHILKMFPSTWYV'
        self.cmap = "bwr_r"

        self.results = []
        self.parallel_run = False

    @staticmethod
    def parse_custom_indices(indices_str):
        custom_indices = []
        ranges = indices_str.split(',')
        for r in ranges:
            if '-' in r:
                start, end = r.split('-')
                custom_indices.extend(list(range(int(start), int(end) + 1)))
            else:
                custom_indices.append(int(r))
        return custom_indices

    def plot_custom_indices_segments(
        self,
        df_ori,
        sequence,
        pop=False,
        annotate=False,
        custom_indices_str='',
        alias='undefined',
        design_case='default',
        cutoff=[-100, 100],
        preferred_substitutions=None,
    ):
        df = df_ori.copy()

        if custom_indices_str == '':
            custom_indices_str = f'1-{len(sequence)}'

        custom_indices = self.parse_custom_indices(custom_indices_str)
        logging.info(custom_indices)

        if custom_indices == []:
            custom_indices = [resi for resi in range(1, len(sequence) + 1)]

        custom_indices = [0] + custom_indices

        df = df.iloc[:, custom_indices]

        sequence = list(sequence)
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
        mutation_json_fp = f'{self.pwd}/mutations_pssm/{time.strftime("%Y%m%d", time.localtime())}_{alias}_{design_case}_{indices_hash[:10]}.json'
        mutation_png_fp = f'{self.pwd}/{alias}_{design_case}_custom_indices_plot_{indices_hash}.png'
        mutant_table_fp = f'{self.pwd}/mutations_pssm/{time.strftime("%Y%m%d", time.localtime())}_{alias}_{design_case}_{indices_hash[:10]}_mut.txt'
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

    def design_protein_using_pssm(
        self,
        sequence,
        alias,
        preffered=[],
        design_case='default',
        custom_indices_fp='',
        cutoff=[-100, 100],
    ):
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

        if len(preffered) > 0:
            preffered_dict = self.parse_preffered_mutation_string(
                preffered_str=preffered
            )
            logging.info(preffered)
            logging.info(preffered_dict)
        else:
            preffered_dict = None

        custom_indices_str = (
            open(custom_indices_fp, 'r').read().strip()
            if os.path.exists(custom_indices_fp)
            else ''
        )

        (
            mutation_json_fp,
            mutant_table_fp,
            mutation_png_fp,
        ) = self.plot_custom_indices_segments(
            df,
            sequence,
            pop=True,
            custom_indices_str=custom_indices_str,
            alias=alias,
            design_case=design_case,
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

                _, mutant_obj = extract_mutants(
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
        input_pse,
        output_pse,
        molecule,
        chain_id,
        mutant_json,
        reject,
        create_full_pdb,
        progress_bar,
        nproc,
    ):
        self.input_pse = make_temperal_input_pdb(molecule=molecule,wd=os.path.join(self.pwd,'temperal_pdb'))
        self.output_pse = output_pse
        self.molecule = molecule

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
                input_pse,
                molecule,
                chain_id,
                reject,
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
                self.process_position, mutagenesis_tasks, n_jobs=nproc
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

        progress_bar.setRange(0,0)
        self.merge_sessions_via_commandline()
        progress_bar.setRange(0,1)

    # def merging_sessions(self):
    #     logging.info("Merging all sessions .... This may take a while ...")

    #     cmd.hide('surface')

    #     mutagenesis_sessions = [
    #         session_path for session_path in self.results if session_path
    #     ]
    #     logging.debug(f'mutangesis_sessions: {mutagenesis_sessions}')

    #     merged_temp_session = f"{os.path.join(os.path.dirname(self.output_pse), f'.tmp_{os.path.basename(self.output_pse)}')}"

    #     # a temperal sesion that contains only mutants, all sub-sessions will be removed after merged
    #     tmp_session_merger = PyMOLSessionMerger(
    #         session_paths=mutagenesis_sessions,
    #         save_path=merged_temp_session,
    #     )

    #     tmp_session_merger.delete = True
    #     tmp_session_merger.quiet = 0
    #     tmp_session_merger.mode = 2
    #     tmp_session_merger.merge_sessions()

    #     # final session.
    #     session_merger = PyMOLSessionMerger(
    #         session_paths=[self.input_pse, merged_temp_session],
    #         save_path=self.output_pse,
    #     )

    #     session_merger.delete = False
    #     session_merger.quiet = 0
    #     session_merger.mode = 2
    #     session_merger.merge_sessions()

    def merge_sessions_via_commandline(self):
        from REvoDesign.tools import SessionMerger

        logging.info("Merging all sessions .... This may take a while ...")

        cmd.hide('surface')

        mutagenesis_sessions = [
            session_path for session_path in self.results if session_path
        ]

        logging.debug(f'mutangesis_sessions: {mutagenesis_sessions}')
        merged_temp_session = f"{os.path.join(os.path.dirname(self.output_pse), f'mutate_only.{os.path.basename(self.output_pse)}')}"

        tmp_merge_command=[
            SessionMerger.__file__,
            '--save_path', merged_temp_session,
            '--mode', str(2),
            '--delete',
            '--quiet',
            ] + mutagenesis_sessions
        
        merge_results=run_command(excutable='python',command_list=tmp_merge_command)
        if merge_results.returncode == 0:
            logging.info(f'Temperal merged result is successfully created at {merged_temp_session}')
            self.output_pse=merged_temp_session
        else:
            logging.warning(f'Temperal merged result is failed to create.  Try again with a clean PyMOL session.')
            return
        
        # final_merge_command=[
        #     SessionMerger.__file__,
        #     '--save_path', self.output_pse,
        #     '--mode', str(2),
        #     '--quiet',
        #     ] + [self.input_pse, merged_temp_session]
        
        # final_merge_results=run_command(excutable='python',command_list=final_merge_command)

        # if final_merge_results.returncode:
        #     logging.info(f'Final merged result is successfully created at {self.output_pse}')
        # else:
        #     logging.warning(f'Final merged result is failed to create.')
        #     return
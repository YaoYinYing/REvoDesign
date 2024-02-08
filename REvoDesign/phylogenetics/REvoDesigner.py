import os
import json
import hashlib
import time
import re

from REvoDesign.tools.logger import logging as logger

logging = logger.getChild(__name__)

import matplotlib
import collections
import random
from REvoDesign.common.MutantTree import MutantTree

from REvoDesign.common.Mutant import Mutant
from REvoDesign.external_designer import EXTERNAL_DESIGNERS

matplotlib.use('Agg')
import matplotlib.pylab as plt
from REvoDesign.tools.utils import (
    WITH_COLABDESIGN,
    random_deduplicate,
    run_worker_thread_with_progress,
)


from REvoDesign.tools.pymol_utils import (
    get_molecule_sequence,
    find_all_protein_chain_ids_in_protein,
)

from REvoDesign.tools.mutant_tools import (
    expand_range,
    read_customized_indice,
    shorter_range,
    extract_mutant_from_sequences,
    read_profile_design_mutations,
)
from REvoDesign.common.MutantVisualizer import MutantVisualizer


class REvoDesigner:
    def __init__(self, input_profile):
        self.input_pse = ''
        self.output_pse = ''

        self.input_profile = input_profile
        self.input_profile_format = 'PSSM'

        self.external_designer = None
        self.external_designer_temperature = 0.1
        self.external_designer_num_samples = 1
        self.batch = 1
        self.homooligomeric = False
        self.deduplicate_designs = False
        self.randomized_sample = False
        self.randomized_sample_num = 10

        self.sidechain_solver = 'Dunbrack Rotamer Library'
        self.sidechain_solver_radius = 0

        self.molecule = ''
        self.chain_id = 'A'
        self.pwd = '.'
        self.sequence = ''

        self.design_case = 'default'

        self.preffered_substitutions = ''
        self.reject_aa = ''

        # use PSSM alphabet as default
        self.profile_alphabet = 'ARNDCQEGHILKMFPSTWYV'
        self.cmap = "bwr_r"

        self.results = []
        self.nproc = 1
        self.max_abs_profile = 0
        self.create_full_pdb = False
        self.mutant_tree = None

        self.mutagenesis_tasks = []

    def plot_custom_indices_segments(
        self,
        df_ori,
        custom_indices_str='',
        cutoff=[-100, 100],
        preferred_substitutions=None,
    ):
        """
        Plot custom indices segments on a heatmap.

        Args:
        - df_ori: Original DataFrame.
        - custom_indices_str: String representing custom indices.
        - cutoff: List representing cutoff values.
        - preferred_substitutions: Dictionary of preferred substitutions.

        Returns:
        - Tuple: File paths for JSON and PNG representations of mutations.

        Notes:
        - Generates a heatmap representing custom indices and mutations.
        - Saves JSON and PNG files for visualization.
        """
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
            profile_scores = df_ori.iloc[:, resid]
            mutation_candidates['mutations'][resid] = {
                "wt": wt_aa,
                "wt_profile_score": profile_scores.loc[wt_aa],
                "candidates": {},
            }

            substitutions = profile_scores[
                (cutoff[0] <= profile_scores - profile_scores.loc[wt_aa])
                & (profile_scores - profile_scores.loc[wt_aa] <= cutoff[1])
            ]

            for mut_aa, profile_score in substitutions.items():
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
                        ] = profile_score
                        mutations.append(mutation_key)
                else:
                    mutation_candidates['mutations'][resid]["candidates"][
                        mut_aa
                    ] = profile_score
                    mutations.append(mutation_key)

        os.makedirs(f'{self.pwd}/mutations_design_profile', exist_ok=True)

        indices_hash = hashlib.sha256(
            bytes(custom_indices_str.encode())
        ).hexdigest()

        file_name = f'{time.strftime("%Y%m%d", time.localtime())}_{self.molecule}_{self.design_case}_{indices_hash[:10]}'
        mutation_json_fp = (
            f'{self.pwd}/mutations_design_profile/{file_name}.json'
        )
        mutation_png_fp = (
            f'{self.pwd}/mutations_design_profile/{file_name}.png'
        )

        json.dump(mutation_candidates, open(mutation_json_fp, 'w'), indent=2)

        plt.savefig(mutation_png_fp)
        plt.close()

        return mutation_json_fp, mutation_png_fp

    def validate_preffered_mutation_string(
        self,
        preffered_mutation_string,
    ):
        """
        Validate the format of the preferred mutation string.

        Args:
        - preferred_mutation_string: Preferred mutation string.

        Returns:
        - bool: True if the format is valid, False otherwise.
        """
        pattern = f'^[{"".join(self.profile_alphabet)}]:[{"".join(self.profile_alphabet)}]+$'
        preffered_mutation_string = preffered_mutation_string.replace(
            '[', ''
        ).replace(']', '')
        if re.match(pattern, preffered_mutation_string):
            return True
        else:
            return False

    def parse_preffered_mutation_string(self, preffered_str):
        """
        Parse the preferred mutation string into a dictionary.

        Args:
        - preferred_str: Preferred mutation string.

        Returns:
        - dict: Dictionary representation of preferred mutations.
        """
        preffered_dict = {
            _preffered_sub[0]: [res for res in _preffered_sub[2:]]
            for _preffered_sub in preffered_str.split(' ')
            if self.validate_preffered_mutation_string(_preffered_sub)
        }

        return preffered_dict

    def setup_parameters_for_external_designer(self):
        """
        Set up parameters for the external designer based on molecule and chain ID.

        Notes:
        - Determines the design chain ID based on the molecule and sequence.
        - Sets up parameters required for the external designer.
        """
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
        """
        Set up the external designer for protein design.

        Args:
        - custom_indices_str: String representing custom indices.

        Notes:
        - Initializes the external designer with specified parameters.
        - Handles different types of external designers.
        """
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

        if self.randomized_sample and self.randomized_sample_num > 0:
            expanded_custom_indices = random.sample(
                expanded_custom_indices, self.randomized_sample_num
            )
            logging.info(
                f'Generated random sample indices: {expanded_custom_indices}'
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

        if (
            not self.external_designer  # non-designer is set
            or magician.__name__
            != self.external_designer.__class__.__name__  # designer is switched to another
        ):
            # Magician ProteinMPNN
            if self.input_profile_format == 'ProteinMPNN':
                self.external_designer = magician(
                    molecule=self.molecule,
                )
                self.external_designer.initialize(
                    fix_pos=','.join(
                        [
                            f"{self.chain_id}{indice}"
                            for indice in shorter_range(
                                expanded_custom_indices, connector='-'
                            ).split('+')
                        ]
                        if expanded_custom_indices
                        else None
                    ),
                    inverse=True,
                    rm_aa=','.join(list(self.reject_aa))
                    if self.reject_aa
                    else None,
                    chain=','.join(self.design_chain_id),
                    homooligomeric=self.homooligomeric,
                    ignore_missing=bool('X' in self.sequence),
                )

            # register more Magician at here.
            # elif .....
            return

    def design_protein_using_external_designer(
        self, custom_indices_fp, progress_bar
    ):
        """
        Design protein using an external designer.

        Args:
        - custom_indices_fp: File path to custom indices.
        - progress_bar: Progress bar for displaying progress.

        Notes:
        - Initiates the protein design process using an external designer.
        - Sets up parameters and executes the design process.
        """
        custom_indices_str = read_customized_indice(
            custom_indices_from_input=custom_indices_fp
        )
        logging.info(
            f'Starting {self.input_profile_format}, this may take a while.'
        )

        run_worker_thread_with_progress(
            worker_function=self.setup_external_designer,
            custom_indices_str=custom_indices_str,
            progress_bar=progress_bar,
        )

        if not self.external_designer:
            logging.error(
                f'Failed to initialize external designer {self.input_profile_format}'
            )
            self.output_pse = ''
            return

        logging.info(
            f'Setting preffered substitutions {self.preffered_substitutions}.'
        )
        self.external_designer.preffer_substitutions(
            aa=self.preffered_substitutions
        )

        logging.info(
            f'Starting design with {self.input_profile_format}, this may take a while,'
            'depending on your molecule size, sampling batch and design number that you required.'
        )

        designs = run_worker_thread_with_progress(
            worker_function=self.external_designer.designer,
            num=self.external_designer_num_samples,
            batch=self.batch,
            temperature=self.external_designer_temperature,
            progress_bar=progress_bar,
        )

        logging.info('Design is done. Parsing the results...')

        mutant_objs = []
        score_list = []

        counter_1 = collections.Counter(designs['seq'])

        if any([counter_1.get(seq) > 1 for seq in designs['seq']]):
            logging.warning(
                f'Designs from {self.input_profile_format} contains duplicated items.'
            )

        if self.deduplicate_designs:
            logging.warning(
                f'Deduplicating designs from {self.input_profile_format} ...'
            )
            seqs, scores = random_deduplicate(
                seq=designs['seq'], score=designs['score']
            )
            logging.warning(
                f'Removed designs: {len(designs["seq"])-len(seqs)}'
            )
        else:
            seqs, scores = designs['seq'], designs['score']

        counter_2 = collections.Counter(seqs)

        for seq, score in zip(seqs, scores):
            mutant_obj = extract_mutant_from_sequences(
                mutant_sequence=seq,
                chain_id=self.chain_id,
                wt_sequence=self.sequence,
                fix_missing=bool('X' in self.sequence),
            )
            if not mutant_obj:
                logging.warning('Skipped.')
                continue
            if counter_2.get(seq) > 1:
                logging.warning(
                    f'Design {mutant_obj.get_mutant_id()} has multiple scores!\n'
                    'See: https://github.com/dauparas/ProteinMPNN/issues/19#issuecomment-1283072787\n'
                    'Check `De-duplicated` for picking a random unique one.'
                )

            mutant_obj.mutant_score = score
            score_list.append(score)
            mutant_objs.append(mutant_obj)

        if not mutant_objs:
            logging.warning('No available designs is founded.')
            return

        mutant_tree = {
            self.design_case: {
                mut_obj.get_short_mutant_id(): mut_obj
                for mut_obj in mutant_objs
            }
        }
        self.mutant_tree = MutantTree(mutant_tree=mutant_tree)

        self.output_pse = self.run_mutagenesis_via_mutant_visualizer(
            group_id=self.design_case, progress_bar=progress_bar
        )

        logging.info("Done.")

    def setup_profile_design(
        self,
        custom_indices_fp='',
        cutoff=[-100, 100],
    ):
        """
        Set up profile design based on specified parameters.

        Args:
        - custom_indices_fp: File path to custom indices.
        - cutoff: List representing cutoff values.

        Returns:
        - Tuple: File paths for JSON and PNG representations of mutations.

        Notes:
        - Parses profile data and generates a heatmap of design segments.
        - Saves JSON and PNG files for visualization.
        """
        custom_indices_str = read_customized_indice(
            custom_indices_from_input=custom_indices_fp
        )

        profile_parser = MutantVisualizer(
            molecule=self.molecule, chain_id=self.chain_id
        )
        profile_parser.sequence = self.sequence
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
            mutation_png_fp,
        ) = self.plot_custom_indices_segments(
            df,
            custom_indices_str=custom_indices_str,
            cutoff=cutoff,
            preferred_substitutions=preffered_dict,
        )

        return mutation_json_fp, mutation_png_fp

    def run_mutagenesis_via_mutant_visualizer(self, group_id, progress_bar):
        """
        Runs mutagenesis using MutantVisualizer based on specified parameters.

        Args:
        - self: Instance of the class containing the method.
        - group_id: Identifier for the group of mutations.
        - progress_bar: Progress bar widget to display the progress.

        Returns:
        - str: File path of the saved session after mutagenesis.

        Notes:
        - This method utilizes MutantVisualizer to perform mutagenesis based on the provided parameters.
        - Initializes MutantVisualizer with specific molecule, chain_id, sequence, group_name, and other properties.
        - Sets visualization parameters like cmap, min_score, max_score based on self parameters.
        - Determines mutagenesis parameters based on external_designer and mutant_tree's branch_id.
        - Sets nproc and parallel_run based on the number of processors available.
        - Saves the resulting session file and returns the file path.
        """
        visualizer = MutantVisualizer(
            molecule=self.molecule, chain_id=self.chain_id
        )
        visualizer.sequence = self.sequence
        visualizer.group_name = group_id
        visualizer.full = self.create_full_pdb
        visualizer.cmap = self.cmap
        visualizer.sidechain_solver = self.sidechain_solver
        visualizer.sidechain_solver_radius = self.sidechain_solver_radius
        visualizer.setup_side_chain_solver()

        if (
            self.external_designer
            or self.input_profile_format in EXTERNAL_DESIGNERS
        ):
            branch = self.mutant_tree.get_a_branch(branch_id=group_id)
            score_list = [
                mut_obj.mutant_score for _, mut_obj in branch.items()
            ]
            visualizer.min_score = min(score_list)
            visualizer.max_score = max(score_list)
        else:
            visualizer.min_score = -self.max_abs_profile
            visualizer.max_score = self.max_abs_profile

        visualizer.nproc = self.nproc
        visualizer.parallel_run = self.nproc > 1
        visualizer.input_session = self.input_pse
        visualizer.save_session = os.path.join(
            os.path.dirname(self.output_pse),
            f'group.{group_id}.{os.path.basename(self.output_pse)}',
        )

        visualizer.mutant_tree = MutantTree(
            {group_id: self.mutant_tree.get_a_branch(branch_id=group_id)}
        )
        visualizer.run_mutagenesis_tasks(progress_bar=progress_bar)
        return visualizer.save_session

    def load_mutants_to_pymol_session(
        self,
        mutant_json,
        progress_bar,
    ):
        """
        Load mutants to PyMOL session for visualization.

        Args:
        - mutant_json: JSON file containing mutant information.
        - progress_bar: Progress bar for displaying progress.

        Notes:
        - Loads mutants into PyMOL session for visualization.
        - Handles mutations and creates visualization sessions.
        """
        mutations = read_profile_design_mutations(mutant_json)

        self.mutagenesis_tasks = []
        new_residue_scores = []
        self.mutant_tree = MutantTree({})
        for position, wt_res, wt_score, candidates in mutations:
            if not candidates:
                continue

            # reject wt if required.
            if self.reject_aa and wt_res in self.reject_aa:
                continue

            candidates = {
                k: v for k, v in candidates.items() if k not in self.reject_aa
            }

            for mut_res, mut_score in candidates.items():
                mutant_obj = Mutant(
                    mutant_info=[
                        {
                            'chain_id': self.chain_id,
                            'position': int(position),
                            'wt_res': wt_res,
                            'mut_res': mut_res,
                        }
                    ]
                )
                mutant_obj.mutant_score = float(mut_score)
                mutant_obj.wt_sequence = {self.chain_id: self.sequence}

                mutant_obj.wt_score = float(wt_score)
                self.mutagenesis_tasks.append([mutant_obj])
                self.mutant_tree.add_mutant_to_branch(
                    branch=f"mt_{wt_res}{int(position)}_{str(mutant_obj.wt_score)}",
                    mutant=mutant_obj.get_short_mutant_id(),
                    mutant_info=mutant_obj,
                )

                new_residue_scores.append(mutant_obj.mutant_score)

        self.max_abs_profile = max(
            abs(min(new_residue_scores)), abs(max(new_residue_scores))
        )

        if self.mutant_tree.empty:
            logging.warning(f'No available designs!')
            return

        self.results = []

        for branch_id in self.mutant_tree.all_mutant_branch_ids:
            logging.info(f'Creating mutagenesis for {branch_id}')
            result_session = self.run_mutagenesis_via_mutant_visualizer(
                group_id=branch_id, progress_bar=progress_bar
            )
            self.results.append(result_session)

        # call MutantVisualizer for merge sessions
        session_merger = MutantVisualizer(molecule='', chain_id='')
        session_merger.input_session = self.input_pse
        session_merger.save_session = self.output_pse
        session_merger.mutagenesis_sessions = self.results
        run_worker_thread_with_progress(
            session_merger.merge_sessions_via_commandline,
            progress_bar=progress_bar,
        )
        self.output_pse = session_merger.save_session

'''
Work horse of generating mutant from profile or designer

TODO: need refactor
'''

import collections
import hashlib
import json
import os
import random
import re
import time
from typing import List, Union

import matplotlib
import matplotlib.pylab as plt
import numpy as np
import pandas as pd
from RosettaPy.common.mutation import Mutation, RosettaPyProteinSequence

from REvoDesign import issues
from REvoDesign.basic import MutateRunnerAbstract
from REvoDesign.citations import CitationManager
from REvoDesign.common import Mutant, MutantTree
from REvoDesign.common.mutant_visualise import MutantVisualizer
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.magician import IMPLEMENTED_DESIGNERS, Magician
from REvoDesign.tools.mutant_tools import (expand_range,
                                           extract_mutant_from_sequences,
                                           read_customized_indice,
                                           read_profile_design_mutations,
                                           shorter_range)
from REvoDesign.tools.pymol_utils import (
    find_all_protein_chain_ids_in_protein, get_molecule_sequence)
from REvoDesign.tools.utils import random_deduplicate, require_not_none

matplotlib.use("Agg")
logging = ROOT_LOGGER.getChild(__name__)


class REvoDesigner:
    def __init__(self, input_profile):
        self.input_pse = ""
        self.output_pse = ""
        self.molecule = ""
        self.designable_sequences: RosettaPyProteinSequence
        self.chain_id = "A"

        self.input_profile = input_profile
        self.input_profile_format = "PSSM"

        self.magician_temperature = 0.1
        self.magician_num_samples = 1
        self.batch = 1
        self.homooligomeric = False
        self.deduplicate_designs = False
        self.randomized_sample = False
        self.randomized_sample_num = 10
        self.mutate_runner: MutateRunnerAbstract = None  # type: ignore

        self.pwd = "."
        self.sequence = ""

        self.design_case = "default"

        self.preffered_substitutions = ""
        self.reject_aa = ""

        # use PSSM alphabet as default
        self.profile_alphabet = "ARNDCQEGHILKMFPSTWYV"
        self.cmap = "bwr_r"
        self.results = []
        self.nproc = 1
        self.max_abs_profile = 0
        self.create_full_pdb = False
        self.mutant_tree: MutantTree = None

        self.mutagenesis_tasks = []

        self.visualizer: MutantVisualizer = None
        self.citations: CitationManager = CitationManager()
        self.magician: Magician = Magician()

    def plot_custom_indices_segments(
        self,
        df_ori: pd.DataFrame,
        custom_indices_str="",
        cutoff=[-100, 100],
        preferred_substitutions=None,
        dpi=600,
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

        first_idx: Union[str, int] = df.columns.tolist()[0]
        if first_idx == 0 or first_idx == '0':
            logging.debug("Input profile is zero-indexed, convert to 1-indexed")
            df.columns = df.columns.map(lambda x: int(x) + 1)
        else:
            df.columns = df.columns.map(int)

        logging.debug(custom_indices_str)

        if custom_indices_str == "":
            custom_indices_str = shorter_range(
                [i + 1 for i, aa in enumerate(self.sequence) if aa != 'X'], connector='-', seperator=",")
            logging.debug(f"Got empty custonmized indices, fix to non-X full length --> \n {custom_indices_str}")

        custom_indices = expand_range(
            shortened_str=custom_indices_str, seperator=",", connector="-"
        )
        logging.info(custom_indices)

        if custom_indices == []:
            custom_indices = [
                resi for resi in range(1, len(self.sequence) + 1)
            ]

        # pick out the columns selected by custom indices input
        # one-indexed
        logging.debug(f'Apply custom indices to df: {custom_indices}')
        logging.debug(f'Column names: {df.columns}')
        df_trunc = df.loc[:, custom_indices]
        logging.debug(f'Trucated Dataframe: \n {df_trunc.head()}')

        sequence = list(self.sequence)

        # truncate sequence for labels
        sequence_trunc = "".join([sequence[i - 1] for i in custom_indices])
        logging.debug(f'Trucated sequence: {sequence_trunc}')

        max_abs_value = np.max((np.abs(df_trunc.values.min()), df_trunc.values.max()))

        plt.figure(figsize=(0.31 * len(sequence_trunc), 5),dpi=dpi)
        pcm = plt.imshow(
            df_trunc, cmap=self.cmap, vmin=-max_abs_value, vmax=max_abs_value
        )

        alphabet_row: List[str] = df_trunc.index.to_list()

        x_ax = [i for i in map(str, custom_indices)]
        plt.xticks(range(len(x_ax)), x_ax, rotation=45)
        plt.yticks(range(20), alphabet_row)
        plt.grid(False)

        plt.colorbar(pcm).minorticks_on()

        for truc_seq_idx_x, aa_in_trunc_seq in enumerate(sequence_trunc):
            for aa_ab_idx_y, aa_type in enumerate(alphabet_row):
                if aa_type == aa_in_trunc_seq:
                    plt.text(
                        truc_seq_idx_x,
                        aa_ab_idx_y,
                        aa_type,
                        ha="center",
                        va="center",
                        color="k",
                    )

        mutation_candidates = {
            "indices": custom_indices,
            "cutoff": cutoff,
            "mutations": {},
        }
        mutations = []
        for idx, resid in enumerate(custom_indices):
            # fetch wt aa from untruncated sequence
            wt_aa = sequence[resid - 1]
            profile_scores = df_trunc.loc[:, resid]
            mutation_candidates["mutations"][resid] = {
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
                        mutation_candidates["mutations"][resid]["candidates"][
                            mut_aa
                        ] = profile_score
                        mutations.append(mutation_key)
                else:
                    mutation_candidates["mutations"][resid]["candidates"][
                        mut_aa
                    ] = profile_score
                    mutations.append(mutation_key)

        os.makedirs(f"{self.pwd}/mutations_design_profile", exist_ok=True)

        indices_hash = hashlib.sha256(
            bytes(custom_indices_str.encode())
        ).hexdigest()
        _time_stamp = time.strftime("%Y%m%d", time.localtime())
        file_name = f'{_time_stamp}_{self.molecule}_{self.design_case}_{indices_hash[:10]}'
        mutation_json_fp = (
            f"{self.pwd}/mutations_design_profile/{file_name}.json"
        )
        mutation_png_fp = (
            f"{self.pwd}/mutations_design_profile/{file_name}.png"
        )

        json.dump(mutation_candidates, open(mutation_json_fp, "w"), indent=2)

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
            "[", ""
        ).replace("]", "")
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
            for _preffered_sub in preffered_str.split(" ")
            if self.validate_preffered_mutation_string(_preffered_sub)
        }

        return preffered_dict

    def setup_parameters_for_magician(self):
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
                    f"No homooligomer found for chain {self.chain_id}, ignore `homooligomeric` setting"
                )
                self.homooligomeric = False
        self.design_chain_id = design_chain_id

    def setup_magician(
        self,
        custom_indices_str="",
    ):
        """
        Set up the external designer for protein design.

        Args:
        - custom_indices_str: String representing custom indices.

        Notes:
        - Initializes the external designer with specified parameters.
        - Handles different types of external designers.
        """

        # expand design residue index
        expanded_custom_indices = expand_range(
            shortened_str=custom_indices_str, connector="-", seperator=","
        )

        if self.randomized_sample and self.randomized_sample_num > 0:
            expanded_custom_indices = random.sample(
                expanded_custom_indices, self.randomized_sample_num
            )
            logging.info(
                f"Generated random sample indices: {expanded_custom_indices}"
            )

        # setup parameters for external designer
        self.setup_parameters_for_magician()

        if not (self.magician_temperature and self.magician_num_samples):
            logging.error(
                f"Missing input for magician: {self.input_profile_format}"
            )
            return

        self.magician = self.magician.setup(
            gimmick_name=self.input_profile_format,
            molecule=self.molecule,
            fix_pos=",".join(
                [
                    f"{self.chain_id}{indice}"
                    for indice in shorter_range(
                        expanded_custom_indices, connector="-"
                    ).split("+")
                ]
                if expanded_custom_indices
                else None
            ),
            inverse=True,
            rm_aa=",".join(list(self.reject_aa)) if self.reject_aa else None,
            chain=",".join(self.design_chain_id),
            homooligomeric=self.homooligomeric,
            ignore_missing=bool("X" in self.sequence),
        )

    def design_protein_via_magician(self, custom_indices_fp):
        """
        Design protein using an external designer.

        Args:
        - custom_indices_fp: File path to custom indices.

        Notes:
        - Initiates the protein design process using an external designer.
        - Sets up parameters and executes the design process.
        """
        custom_indices_str = read_customized_indice(
            custom_indices_from_input=custom_indices_fp
        )
        logging.info(
            f"Starting {self.input_profile_format}, this may take a while."
        )

        self.setup_magician(
            custom_indices_str=custom_indices_str,
        )

        if self.magician.gimmick is None:
            logging.error(
                f"Failed to initialize magician {self.input_profile_format}: {self.magician.gimmick}"
            )
            self.output_pse = ""
            return

        logging.info(
            f"Setting preffered substitutions {self.preffered_substitutions}."
        )

        self.magician.gimmick.preffer_substitutions(
            aa=self.preffered_substitutions
        )

        logging.info(
            f"Starting design with {self.input_profile_format}, this may take a while,"
            "depending on your molecule size, sampling batch and design number that you required."
        )

        designs = self.magician.gimmick.designer(
            num=self.magician_num_samples,
            batch=self.batch,
            temperature=self.magician_temperature,
        )

        logging.info("Design is done. Parsing the results...")

        mutant_objs: list[Mutant] = []
        score_list = []

        counter_1 = collections.Counter(designs["seq"])

        if any(counter_1.get(seq) > 1 for seq in designs["seq"]):
            logging.warning(
                f"Designs from {self.input_profile_format} contains duplicated items."
            )

        if self.deduplicate_designs:
            logging.warning(
                f"Deduplicating designs from {self.input_profile_format} ..."
            )
            seqs, scores = random_deduplicate(
                seq=designs["seq"], score=designs["score"]
            )
            logging.warning(
                f'Removed designs: {len(designs["seq"]) - len(seqs)}'
            )
        else:
            seqs, scores = designs["seq"], designs["score"]

        counter_2 = collections.Counter(seqs)

        for seq, score in zip(seqs, scores):
            mutant_obj = extract_mutant_from_sequences(
                mutant_sequence=seq,
                chain_id=self.chain_id,
                wt_sequences=self.designable_sequences,
                fix_missing=bool("X" in self.sequence),
            )
            if mutant_obj is None:
                logging.warning("Skipped.")
                continue
            if counter_2.get(seq) > 1:
                logging.warning(
                    f"Design {mutant_obj.raw_mutant_id} has multiple scores!\n"
                    "See: https://github.com/dauparas/ProteinMPNN/issues/19#issuecomment-1283072787\n"
                    "Check `De-duplicated` for picking a random unique one."
                )

            mutant_obj.mutant_score = score
            mutant_obj.wt_protein_sequence = (
                RosettaPyProteinSequence.from_dict(
                    {self.chain_id: self.sequence}
                )
            )
            score_list.append(score)
            mutant_objs.append(mutant_obj)

        if not mutant_objs:
            logging.warning("No available designs is founded.")
            return

        mutant_tree = {
            self.design_case: {
                mut_obj.short_mutant_id: mut_obj for mut_obj in mutant_objs
            }
        }
        self.mutant_tree = MutantTree(mutant_tree=mutant_tree)
        logging.debug(f"MutantTree: {str(self.mutant_tree)}")

        self.mutant_tree.run_mutate_parallel(
            mutate_runner=self.mutate_runner, nproc=self.nproc
        )

        if not self.visualizer:
            self.setup_visualizer()

        external_design_session = self.run_mutagenesis_via_mutant_visualizer(
            group_id=self.design_case
        )

        logging.warning(f"Saving at {external_design_session}")

        # call MutantVisualizer for merge sessions
        session_merger = MutantVisualizer(molecule="", chain_id="")
        session_merger.input_session = self.input_pse
        session_merger.save_session = self.output_pse
        session_merger.mutagenesis_sessions = [external_design_session]

        session_merger.merge_sessions_via_commandline()

        logging.info("Done.")

    def setup_profile_design(
        self,
        custom_indices_fp="",
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
        profile_parser.designable_sequences = self.designable_sequences
        profile_parser.sequence = self.sequence
        df = profile_parser.parse_profile(
            profile_fp=self.input_profile,
            profile_format=self.input_profile_format,
        )

        if df is None or df.empty:
            logging.error(
                f"Error occurs while parsing profile {self.input_profile} with format {self.input_profile_format}"
            )
            raise issues.NoResultsError(
                f"Error occurs while parsing profile {self.input_profile} with format {self.input_profile_format}"
            )

        # refresh profile alphabet based on profile reading
        self.profile_alphabet = "".join(df.T.columns.to_list())

        logging.debug(df.head())

        if self.preffered_substitutions:
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

    def setup_visualizer(self):
        self.visualizer = MutantVisualizer(
            molecule=self.molecule, chain_id=self.chain_id
        )
        self.visualizer.sequence = self.sequence

        self.visualizer.full = self.create_full_pdb
        self.visualizer.cmap = self.cmap

        self.visualizer.nproc = self.nproc

        self.visualizer.input_session = self.input_pse
        self.visualizer.mutate_runner = self.mutate_runner

        if (
            self.magician.gimmick
            or self.input_profile_format in IMPLEMENTED_DESIGNERS
        ):
            score_list = [
                mut_obj.mutant_score
                for mut_obj in self.mutant_tree.all_mutant_objects
            ]
            self.visualizer.min_score = min(score_list)
            self.visualizer.max_score = max(score_list)
        else:
            self.visualizer.min_score = -self.max_abs_profile
            self.visualizer.max_score = self.max_abs_profile

    @require_not_none("visualizer", fallback_setup='setup_visualizer')
    def run_mutagenesis_via_mutant_visualizer(self, group_id):
        """
        Runs mutagenesis using MutantVisualizer based on specified parameters.

        Args:
        - self: Instance of the class containing the method.
        - group_id: Identifier for the group of mutations.

        Returns:
        - str: File path of the saved session after mutagenesis.

        Notes:
        - This method utilizes MutantVisualizer to perform mutagenesis based on the provided parameters.
        - Initializes MutantVisualizer with specific molecule, chain_id, sequence, group_name, and other properties.
        - Sets visualization parameters like cmap, min_score, max_score based on self parameters.
        - Determines mutagenesis parameters based on magician and mutant_tree's branch_id.
        - Sets nproc and parallel_run based on the number of processors available.
        - Saves the resulting session file and returns the file path.
        """

        self.visualizer.group_name = group_id

        self.visualizer.save_session = os.path.join(
            os.path.dirname(self.output_pse),
            f"group.{group_id}.{os.path.basename(self.output_pse)}",
        )

        self.visualizer.mutant_tree = MutantTree(
            {group_id: self.mutant_tree.get_a_branch(branch_id=group_id)}
        )

        self.visualizer.run_mutagenesis_tasks()
        return self.visualizer.save_session

    def load_mutants_to_pymol_session(
        self,
        mutant_json,
    ):
        """
        Load mutants to PyMOL session for visualization.

        Args:
        - mutant_json: JSON file containing mutant information.

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
                    mutations=[
                        Mutation(
                            chain_id=self.chain_id,
                            position=int(position),
                            wt_res=wt_res,
                            mut_res=mut_res,
                        )
                    ],
                    wt_protein_sequence=self.designable_sequences,
                )
                mutant_obj.mutant_score = float(mut_score)
                mutant_obj.wt_score = float(wt_score)

                self.mutagenesis_tasks.append([mutant_obj])
                self.mutant_tree.add_mutant_to_branch(
                    branch=f"mt_{wt_res}{int(position)}_{str(mutant_obj.wt_score)}",
                    mutant=mutant_obj.short_mutant_id,
                    mutant_obj=mutant_obj,
                )

                new_residue_scores.append(mutant_obj.mutant_score)

        self.max_abs_profile = max(
            abs(min(new_residue_scores)), abs(max(new_residue_scores))
        )

        if self.mutant_tree.empty:
            logging.warning("No available designs!")
            return

        self.mutant_tree.run_mutate_parallel(
            mutate_runner=self.mutate_runner, nproc=self.nproc
        )

        self.results = []

        for branch_id in self.mutant_tree.all_mutant_branch_ids:
            logging.info(f"Creating mutagenesis for {branch_id}")
            result_session = self.run_mutagenesis_via_mutant_visualizer(
                group_id=branch_id,
            )
            self.results.append(result_session)

        # call MutantVisualizer for merge sessions
        session_merger = MutantVisualizer(molecule="", chain_id="")
        session_merger.input_session = self.input_pse
        session_merger.save_session = self.output_pse
        session_merger.mutagenesis_sessions = self.results
        session_merger.merge_sessions_via_commandline()

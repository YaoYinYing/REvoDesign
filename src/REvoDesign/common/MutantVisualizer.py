import gc
import os
import tempfile
from typing import Optional
import warnings

import matplotlib
import pandas as pd
from Bio import SeqIO
from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign import issues, root_logger
from REvoDesign.common.Mutant import Mutant
from REvoDesign.common.MutantTree import MutantTree
from REvoDesign.common.ProfileParsers import ProfileManager
from REvoDesign.sidechain_solver import MutateRunnerAbstract
from REvoDesign.tools.mutant_tools import (extract_mutant_from_sequences,
                                           extract_mutants_from_mutant_id)
from REvoDesign.tools.utils import get_color, run_command
from REvoDesign.external_designer import Magician, implemented_designers

matplotlib.use('Agg')
logging = root_logger.getChild(__name__)


class MutantVisualizer:
    def __init__(self, molecule, chain_id):
        self.molecule = molecule
        self.chain_id = chain_id
        self.designable_sequences: RosettaPyProteinSequence
        self.mutfile = ''
        self.input_session = ''
        self.save_session = None
        self.nproc = os.cpu_count()
        self.full = False
        self.cmap = "bwr_r"
        self.key_col = "best_leaf"
        self.score_col = "totalscore"
        self.group_name = 'default_group'
        self.sequence = ''
        self.profile = ''
        self.profile_format: str = 'PSSM'
        self.scorer = None
        self.mutate_runner: MutateRunnerAbstract = None

        self.profile_scoring_df: pd.DataFrame = None

        self.min_score = 0.5
        self.max_score = 0.5

        self.min_score_profile = 0
        self.max_score_profile = 0
        self.mutant_tree: MutantTree = MutantTree({})

        self.consider_global_score_from_profile = False

        self.magician=Magician()

    def process_mutant(self, mutant_obj: Mutant):
        """
        Process a specific position based on the information in the Mutant object.

        Args:
        - self: Instance of the class containing the method.
        - mutant_obj (Mutant): Mutant object containing information about the position.

        Returns:
        - temp_session_path (str): Filepath to the temporary session containing processed data.

        Notes:
        - Loads the input session, hides surface, visualizes the mutant, and creates mutagenesis objects.
        - Saves the processed session data to a temporary file and returns the file path.
        """
        score = mutant_obj.mutant_score

        color = get_color(self.cmap, score, self.min_score, self.max_score)
        logging.info(
            f" Visualizing {mutant_obj.short_mutant_id} ({mutant_obj.raw_mutant_id}) : {color} with {self.mutate_runner.__class__.__name__}"
        )
        temp_session_path = self.create_mutagenesis_objects(
            mutant_obj, color, in_place=False
        )

        return temp_session_path

    # provide a full function of PyMOL mutate that requires explicit mutagenesis description as mutant object
    def create_mutagenesis_objects(
        self, mutant_obj: Mutant, color, in_place=True
    ):
        """
        Creates mutagenesis objects in PyMOL based on explicit mutagenesis descriptions.

        Args:
        - self: Instance of the class containing the method.
        - mutant_obj (Mutant): Mutant object containing explicit mutagenesis description.
        - color: Color to assign to the mutagenesis objects.
        - inplace: ask PyMOL mutate runner to not stay in place after mutate is done

        Returns:
        - None

        Notes:
        - Creates mutagenesis objects in PyMOL based on the provided Mutant object.
        - Handles explicit mutagenesis descriptions by applying mutations and assigning colors.
        """
        from pymol import cmd, util

        new_obj_name = mutant_obj.short_mutant_id
        score = mutant_obj.mutant_score

        temp_dir = tempfile.mkdtemp(prefix='RD_design_')
        temp_mutant_path = os.path.join(
            temp_dir, f"{self.molecule}_{new_obj_name}.pse"
        )

        mut_pos = [
            f'(c. {mut_info.chain_id} and i. {str(mut_info.position)})'
            for mut_info in mutant_obj.mutations
        ]

        if not self.mutate_runner:
            raise RuntimeError('no mutate runner is instantiated yet.')

        # use precomputed pdb if it exists. otherwise run the runner to get one.
        if not (temp_mutant_pdb_path := mutant_obj.pdb_fp):
            temp_mutant_pdb_path = self.mutate_runner.run_mutate(
                mutant=mutant_obj,
            )
            mutant_obj.pdb_fp = temp_mutant_pdb_path

            self.mutate_runner.cite()

        if not in_place:
            cmd.reinitialize()

        cmd.load(temp_mutant_pdb_path, new_obj_name)

        cmd.hide('lines', f'{new_obj_name}')
        cmd.hide('cartoon', f'{new_obj_name}')
        cmd.show(
            "sticks",
            f' {new_obj_name} and ( {" or ".join([f"( {pos} )" for pos in mut_pos])} ) and '
            '(sidechain or n. CA) and (not hydrogen)',
        )

        cmd.hide('everything', 'hydrogens and polymer.protein')

        if score:
            cmd.alter(
                f' {new_obj_name} and ( {" or ".join([f"( {pos} )" for pos in mut_pos])} ) and (sidechain or n. CA) ',
                f'b={score}',
            )

        if not self.full:
            # logging.debug(f'Removing:  {new_obj_name} and not ( ({" or ".join(mut_pos)}) and (sidechain or n. CA))')
            cmd.remove(
                f' {new_obj_name} and not ( ({" or ".join(mut_pos)}) and (sidechain or n. CA))'
            )

        # set backbone color
        cmd.set_color(f'color_{new_obj_name}', color)
        cmd.color(
            f'color_{new_obj_name}',
            f'({new_obj_name} and ({" or ".join(mut_pos)}) )',
        )
        util.cnc(f'{new_obj_name} and ({" or ".join(mut_pos)})', _self=cmd)

        if self.group_name:
            cmd.group(self.group_name, new_obj_name)

        if not in_place:
            cmd.save(temp_mutant_path)
            cmd.reinitialize()

        return temp_mutant_path

    def parse_profile(self, profile_fp, profile_format) -> pd.DataFrame:
        """
        Parse the profile data based on the specified format and return the processed DataFrame.

        Args:
        - profile_fp (str): File path of the profile data.
        - profile_format (str): Format of the profile data (e.g., 'PSSM', 'CSV', 'TSV').

        Returns:
        - DataFrame: Processed DataFrame based on the profile format.

        Notes:
        - Parses the profile data based on the specified format and returns a processed DataFrame.
        - Handles different formats (PSSM, CSV, TSV) and processes the data accordingly.
        - Initializes and uses external designers if available for specific profile formats.
        - Logs debug information during the processing for easier debugging.
        - Returns the processed DataFrame or None based on the profile format.
        """


        args = {
            "profile_input": profile_fp,
            "molecule": self.molecule,
            "chain_id": self.chain_id,
            "sequence": self.sequence,
        }

        pm = ProfileManager(profile_type=profile_format)
        pm.parse(args)

        self.profile_scoring_df = pm.parser.df
        self.min_score_profile = pm.parser.min_score_profile
        self.max_score_profile = pm.parser.max_score_profile

        return self.profile_scoring_df

    def run(self):
        """
        Runs mutation tasks.

        Reads mutation data from different file formats (CSV, TXT, FASTA) and performs mutation-related operations.
        Calculates scores for mutants and adds them to the mutant tree.
        Determines the range for the color bar based on mutant scores.
        Adjusts score ranges based on certain conditions.

        Raises:
        - ValueError: If an invalid file format is encountered or if required columns are missing in the data.

        """
        # Check the file format and read data accordingly
        if self.mutfile.lower().endswith('.csv'):
            # Read mutation data from CSV file using pandas
            mutation_data = pd.read_csv(self.mutfile)
        elif self.mutfile.lower().endswith('.txt'):
            # Read mutation data from TXT file using pandas and use 'key_col' as the column name
            mutation_data = pd.read_csv(
                self.mutfile, sep='\t', names=[self.key_col]
            )
        elif any(
            self.mutfile.lower().endswith(ext)
            for ext in ['.fasta', '.fas', '.fa']
        ):
            # Read mutant data from fasta file.
            _mutation_objs = [
                extract_mutant_from_sequences(
                    mutant_sequence=str(mut_record.seq),
                    wt_sequences=self.designable_sequences,
                    chain_id=self.chain_id,
                )
                for mut_record in SeqIO.parse(
                    open(self.mutfile), format='fasta'
                )
            ]

            mutation_data = pd.DataFrame.from_dict(
                {
                    self.key_col: [
                        mut_obj.short_mutant_id for mut_obj in _mutation_objs if mut_obj is not None
                    ]
                }
            )

        else:
            raise issues.InvalidInputError(
                "Invalid file format. Only CSV, FASTA and TXT formats are supported."
            )

        # Check if the key_col exists in the dataframe
        if self.key_col not in mutation_data.columns:
            raise issues.InvalidInputError(
                f"Variant column '{self.key_col}' not found in the data."
            )

        # Check if the score_col exists in the dataframe, if not, add it with a default value of 1
        if self.score_col not in mutation_data.columns:
            logging.warning(
                f"Score column '{self.score_col}' not found in the data. Setting score to 1."
            )
            mutation_data[self.score_col] = 1

        for _, row in mutation_data.iterrows():
            variant_obj: Mutant = extract_mutants_from_mutant_id(
                mutant_string=row[self.key_col],
                sequences=self.designable_sequences,
            )

            # skip None variant (failed to be parsed)
            if variant_obj.empty:
                continue

            _variant_info = variant_obj.mutations

            variant_obj.wt_protein_sequence = self.designable_sequences

            # external scorer stays highest priority.
            if self.scorer:
                _score = self.scorer.scorer(variant_obj)
                logging.debug(
                    f'Reading profile score for scorcer {type(self.scorer)}: {_score}'
                )

            # the profile scoring is a bit more complicated if the mutant contains multiple substitutions.
            # so we have to igore it here.
            elif (
                len(_variant_info) == 1
                and self.profile_scoring_df is not None
                and (not self.profile_scoring_df.empty)
            ):
                _score = self.profile_scoring_df.loc[
                    _variant_info[0].mut_res,
                    str(_variant_info[0].position - 1),
                ]
                logging.warning(
                    f'Reading profile score for variant {variant_obj.short_mutant_id}: {_score}'
                )

            else:
                _score = row[self.score_col]
                logging.debug(
                    f'Reading mutant table score for variant {variant_obj.short_mutant_id}: {_score}'
                )

            variant_obj.mutant_score = float(_score)  # type: ignore
            self.mutant_tree.add_mutant_to_branch(
                branch=self.group_name,
                mutant=variant_obj.short_mutant_id,
                mutant_obj=variant_obj,
            )

        # Determine the range for color bar
        score_list = self.mutant_tree.all_mutant_scores

        logging.debug(f'Scores: {score_list}')

        if (
            self.consider_global_score_from_profile  # Toggle the global score flag
            and (self.profile_scoring_df is not None)  # profile df is not None
            and (not self.profile_scoring_df.empty)  # profile df is not empty
            and (not self.scorer)  # no external scorer enabled
        ):
            self.min_score = self.min_score_profile
            self.max_score = self.max_score_profile

        else:
            self.min_score = min(score_list)
            self.max_score = max(score_list)

        self.run_mutagenesis_tasks()

    def run_mutagenesis_tasks(self):
        """
        Runs mutagenesis tasks based on the MutantTree.

        Args:
        - self: Instance of the class containing the method.

        Notes:
        - This method initiates and manages the execution of mutagenesis tasks using parallel processing
        if self.parallel_run is True.
        - The method uses multiprocessing for parallel execution of tasks.
        - If parallel_run is True:
            - It initializes a ParallelExecutor with specified parameters and starts the execution.
            - Handles the results obtained from parallel execution.
        - If parallel_run is False:
            - Executes mutagenesis tasks sequentially without parallel processing.
        - After executing mutagenesis tasks, it performs merging sessions via command line.
        """

        if not self.mutate_runner:
            raise RuntimeError('no mutate runner is instantiated yet.')

        if any(
            not (m.pdb_fp and os.path.isfile(m.pdb_fp))
            for m in self.mutant_tree.all_mutant_objects
        ):
            logging.warning(
                f're-compute sidechain for {self.mutant_tree.branch_num}: {self.mutant_tree.mutant_num} MutantTree.'
            )

            self.mutant_tree.run_mutate_parallel(
                mutate_runner=self.mutate_runner,
                nproc=self.nproc,  # type: ignore
            )

        self.mutagenesis_sessions = []
        for m in self.mutant_tree.all_mutant_objects:
            self.mutagenesis_sessions.append(self.process_mutant(m))
            gc.collect()

        self.merge_sessions_via_commandline()

    def merge_sessions_via_commandline(self):
        '''
        To call this commandline interface of session merger:

        # Instantialize `MutantVisualizer`. molecule and chain_id can be set as empty str.
        session_merger=MutantVisualizer(molecule=self.molecule, chain_id=self.chain_id)

        # input and output
        session_merger.input_session=self.input_pse
        session_merger.save_session=self.output_pse

        # all mutagenesis sessions
        session_merger.mutagenesis_sessions=self.results

        # run the session merger
        session_merger.merge_sessions_via_commandline()

        #session merger will save a temperal sesion based on given output session file path.


        '''
        from REvoDesign.tools import SessionMerger

        logging.debug(f'mutangesis_sessions: {self.mutagenesis_sessions}')
        merged_temp_session = os.path.join(
            os.path.dirname(self.save_session),
            'temp_sessions',
            f'mutate_only.{os.path.basename(self.save_session)}',
        )
        os.makedirs(os.path.dirname(merged_temp_session), exist_ok=True)

        tmp_merge_command = [
            SessionMerger.__file__,
            '--save_path',
            merged_temp_session,
            '--mode',
            str(2),
            '--delete',
            '--quiet',
        ] + self.mutagenesis_sessions

        merge_results = run_command(
            excutable='python', command_list=tmp_merge_command
        )
        if merge_results.returncode == 0:
            logging.info(
                f'Temperal merged result is successfully created at {merged_temp_session}'
            )
            os.rename(merged_temp_session, self.save_session)
        else:
            warnings.warn(
                issues.InvalidSessionWarning(
                    f'Temperal merged result is failed to create. Try again with a clean PyMOL session. \n'
                    f'STDOUT:\n{merge_results.stdout}\n'
                    f'STDERR:\n{merge_results.stderr}'
                )
            )
            return

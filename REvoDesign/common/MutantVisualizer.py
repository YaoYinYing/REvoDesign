import gc
import os
import time
import tempfile
from typing import Union
import pandas as pd

from Bio import SeqIO
from pymol import cmd
import matplotlib
from REvoDesign.sidechain_solver import (
    PyMOL_mutate,
    DLPacker_worker,
    PIPPack_worker,
)

from REvoDesign.REvoDesign import logging as logger

logging = logger.getChild(__name__)

from REvoDesign.common.MutantTree import MutantTree

matplotlib.use('Agg')

from REvoDesign.common.Mutant import Mutant

from REvoDesign.tools.utils import (
    get_color,
    run_command,
)


from REvoDesign.tools.mutant_tools import (
    extract_mutants_from_mutant_id,
    extract_mutant_from_sequences,
)


class MutantVisualizer:
    def __init__(self, molecule, chain_id):
        self.molecule = molecule
        self.chain_id = chain_id
        self.mutfile = ''
        self.input_session = ''
        self.save_session = None
        self.nproc = os.cpu_count()
        self.parallel_run = False
        self.full = False
        self.cmap = "bwr_r"
        self.key_col = "best_leaf"
        self.score_col = "totalscore"
        self.group_name = 'default_group'
        self.sequence = ''
        self.profile = ''
        self.profile_format: str = 'PSSM'
        self.scorer = None
        self.mutate_runner: Union[
            PyMOL_mutate, DLPacker_worker, PIPPack_worker
        ] = None

        self.profile_scoring_df = None

        self.min_score = 0.5
        self.max_score = 0.5

        self.min_score_profile = 0
        self.max_score_profile = 0
        self.mutant_tree: MutantTree = MutantTree({})

        self.consider_global_score_from_profile = False

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
            f" Visualizing {mutant_obj.short_mutant_id} ({mutant_obj.full_mutant_id}) : {color}"
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
            f'(c. {mut_info["chain_id"]} and i. {str(mut_info["position"])})'
            for mut_info in mutant_obj.mutant_info
        ]

        if not self.mutate_runner:
            raise RuntimeError(f'no mutate runner is instantiated yet.')

        temp_mutant_pdb_path = self.mutate_runner.run_mutate(
            mutant_obj=mutant_obj,
            in_place=in_place,
        )

        if not in_place:
            cmd.reinitialize()

        cmd.load(temp_mutant_pdb_path)

        cmd.hide('lines', f'{new_obj_name}')
        cmd.hide('cartoon', f'{new_obj_name}')
        cmd.show(
            "sticks",
            f' {new_obj_name} and ( {" or ".join([f"( {pos} )" for pos in mut_pos])} ) and (sidechain or n. CA) and (not hydrogen)',
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
            cmd.group(
                self.group_name,
                f'{new_obj_name}',
            )

        if not in_place:
            cmd.save(temp_mutant_path)
            cmd.reinitialize()

        return temp_mutant_path

    def parse_profile(self, profile_fp, profile_format):
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
        from REvoDesign.external_designer import EXTERNAL_DESIGNERS

        # select the designer
        if profile_format in EXTERNAL_DESIGNERS.keys():
            logging.debug(
                f'Will use {profile_format} as sequence scoring method.'
            )
            magician = EXTERNAL_DESIGNERS[profile_format]

            self.scorer = magician(molecule=self.molecule)
            self.scorer.initialize(ignore_missing=bool('X' in self.sequence))
            if not self.scorer:
                logging.error(
                    f'Failed to initialize designer from `{profile_format}`: {self.scorer.__class__.__name__}'
                )
                return
            return

        if profile_format == 'Pythia-ddG':
            df_path = os.path.join(
                os.path.abspath('.'),
                'pythia',
                f'{self.molecule}_pred_mask.csv',
            )
            if not os.path.exists(df_path):
                from REvoDesign.clients.PythiaBiolibClient import PythiaBiolib

                ddg_runner = PythiaBiolib(
                    molecule=self.molecule, chain_id=self.chain_id
                )
                ddg_runner.work_dir = os.path.join(
                    os.path.abspath('.'), 'pythia'
                )
                os.makedirs(ddg_runner.work_dir, exist_ok=True)
                df_path = ddg_runner.predict()

                if not df_path:
                    logging.error('Oops! error occurs during pythia running!')
                    return

                logging.debug(f'Result file is stored at: {df_path}')
            else:
                logging.warning(
                    f'Find expected Pythia output: `{df_path}`, skipping.'
                )
            # a nested call of parse_profile to convert ddg csv into dataframe.
            df = self.parse_profile(profile_fp=df_path, profile_format='CSV')

            return df

        if not profile_fp:
            logging.warning(f'profile not available: {profile_fp}')
            return None

        profile_bn = os.path.basename(profile_fp)

        if profile_format == 'PSSM':
            df_pssm_raw = self.convert_PSSM_file_to_df(
                input_pssm_file=profile_fp
            )
            csv_fp = os.path.join(
                os.path.dirname(profile_fp), f'{profile_bn}.csv'
            )
            df_pssm_raw.to_csv(csv_fp)
            df = pd.read_csv(csv_fp, index_col=0)

            score_max_abs = max(abs(df.min().min()), abs(df.max().max()))
            self.min_score_profile = -score_max_abs
            self.max_score_profile = score_max_abs
            logging.debug(
                f'Profile data: min {self.min_score_profile} max {self.max_score_profile}'
            )

            return df

        elif profile_format == 'CSV':
            df = pd.read_csv(profile_fp, index_col=0)
            df = df.astype(float)

            # try to transpose if the shape is 20 col x N row
            if len(df.columns) == 20:
                df = df.T
                logging.debug(f'Profile data is transposed.')

                column_rename_mapping = {pos: str(pos) for pos in df.columns}
                logging.debug(f'Rename column : {column_rename_mapping}')
                df.rename(columns=column_rename_mapping, inplace=True)

            if str(df.columns[0]) != "0":
                logging.debug(f'Profile data does not matche default format.')
                # Calculate the number of columns (N) in the DataFrame
                N = len(df.columns)

                logging.debug(f'Column : {df.columns}')

                # Create a dictionary to map old column names to new column names
                column_rename_mapping = {
                    str(int(i)): str(int(i) - 1) for i in df.columns
                }

                logging.debug(f'Rename column : {column_rename_mapping}')

                # Rename the columns using the mapping
                df.rename(columns=column_rename_mapping, inplace=True)

            logging.debug(df.columns)

            if (
                len(df.columns) == len(self.sequence.replace('X', ''))
                and 'X' in self.sequence
            ):
                logging.warning('Missing residues from structure.')

                non_missing_resi = [
                    i for i, j in enumerate(self.sequence) if j != 'X'
                ]
                # Create a dictionary to map old column names to new column names
                column_rename_mapping = {
                    str(int(i)): str(int(j))
                    for i, j in zip(df.columns, non_missing_resi)
                }
                # Rename the columns using the mapping
                df.rename(columns=column_rename_mapping, inplace=True)
                logging.debug(f'Repaired: {df.columns}')

                # Fill missing columns with zeros
                logging.warning('Filling missing with zeros')
                for i, j in enumerate(self.sequence):
                    if j == 'X':
                        df.insert(
                            loc=i, column=f'{i}', value=[0 for k in range(20)]
                        )

                logging.debug(f'Filled: {df.columns}')

            if len(df.columns) > 20 and str(df.columns[0]) == '0':
                logging.debug(f'Profile data matches default format.')

                score_max_abs = max(abs(df.min().min()), abs(df.max().max()))
                self.min_score_profile = -score_max_abs
                self.max_score_profile = score_max_abs
                logging.debug(
                    f'Profile data: min {self.min_score_profile} max {self.max_score_profile}'
                )
                return df
            else:
                logging.debug(f'Failed to process profile data {profile_fp}..')
                return
        elif profile_format == 'TSV':
            df = pd.read_table(profile_fp, names=['mut', 'score'])
            return df

        else:
            logging.error(
                f'Unknown profile {profile_fp} or format {profile_format}'
            )
            return None

    def convert_PSSM_file_to_df(self, input_pssm_file):
        """
        Converts a PSSM file to a pandas DataFrame.

        Args:
        - self: Instance of the class containing the method.
        - input_pssm_file (str): Path to the input PSSM file.

        Returns:
        - df (DataFrame): Pandas DataFrame containing the parsed PSSM data.

        Notes:
        - Reads the PSSM file, parses the table header, defines column specifications, and reads the table data.
        - Transposes the DataFrame and drops NaN values to clean the data before returning.
        """
        PSSM_Alphabet = 'ARNDCQEGHILKMFPSTWYV'
        # Fetch table header of PSSM
        c = 0
        for line in open(input_pssm_file):
            pssm_header = line
            c += 1
            if c == 3:
                break

        logging.info(pssm_header)

        # Define colspecs info for parsing pssm data
        # Guess index for PSSM file by the widths of pssm_header
        _idx = [pssm_header.index(ab) for ab in PSSM_Alphabet]
        logging.info(_idx)

        # Guess colspecs for read_fwf to read the table
        _width = _idx[1] - _idx[0]
        colspec = [
            (_idx[i] - _width + 1, _idx[i] + 1) for i in range(len(_idx))
        ]
        logging.info(colspec)
        df = pd.read_fwf(input_pssm_file, skiprows=2, colspecs=colspec)

        # Remove the rest lines
        df.dropna(axis=0, inplace=True)

        df = df.T
        return df

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
        elif (
            self.mutfile.lower().endswith('.fasta')
            or self.mutfile.lower().endswith('.fas')
            or self.mutfile.lower().endswith('.fa')
        ):
            # Read mutant data from fasta file.
            _mutation_objs = [
                extract_mutant_from_sequences(
                    mutant_sequence=str(mut_record.seq),
                    wt_sequence=self.sequence,
                    chain_id=self.chain_id,
                )
                for mut_record in SeqIO.parse(
                    open(self.mutfile, 'r'), format='fasta'
                )
            ]

            # Remove None items
            while None in mutation_data:
                _mutation_objs.pop(None)
            mutation_data = pd.DataFrame.from_dict(
                {
                    self.key_col: [
                        mut_obj.short_mutant_id for mut_obj in _mutation_objs
                    ]
                }
            )

        else:
            raise ValueError(
                "Invalid file format. Only CSV, FASTA and TXT formats are supported."
            )

        # Check if the key_col exists in the dataframe
        if self.key_col not in mutation_data.columns:
            raise ValueError(
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
                sequences={self.chain_id: self.sequence},
            )

            # skip None variant (failed to be parsed)
            if variant_obj.empty:
                continue

            _variant_info = variant_obj.mutant_info

            variant_obj.wt_sequences = {self.chain_id: self.sequence}

            # external scorer stays highest priority.
            if self.scorer:
                _sequence = variant_obj.get_mutant_sequence_single_chain(
                    chain_id=self.chain_id, ignore_missing=True
                )

                _score = self.scorer.scorer(sequence=_sequence)
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
                    _variant_info[0]['mut_res'],
                    str(int(_variant_info[0]['position']) - 1),
                ]
                logging.warning(
                    f'Reading profile score for variant {variant_obj.short_mutant_id}: {_score}'
                )

            else:
                _score = row[self.score_col]
                logging.debug(
                    f'Reading mutant table score for variant {variant_obj.short_mutant_id}: {_score}'
                )

            variant_obj.mutant_score = float(_score)
            self.mutant_tree.add_mutant_to_branch(
                branch=self.group_name,
                mutant=variant_obj.short_mutant_id,
                mutant_info=variant_obj,
            )

        # Determine the range for color bar
        score_list = [
            variant_obj.mutant_score
            for variant_obj in self.mutant_tree.all_mutant_objects
        ]
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
        - This method initiates and manages the execution of mutagenesis tasks using parallel processing if self.parallel_run is True.
        - The method uses multiprocessing for parallel execution of tasks.
        - If parallel_run is True:
            - It initializes a ParallelExecutor with specified parameters and starts the execution.
            - Handles the results obtained from parallel execution.
        - If parallel_run is False:
            - Executes mutagenesis tasks sequentially without parallel processing.
        - After executing mutagenesis tasks, it performs merging sessions via command line.
        """
        from REvoDesign.tools.customized_widgets import (
            refresh_window,
            ParallelExecutor,
        )

        # Create a multiprocessing pool
        self.mutagenesis_tasks = [
            [variant] for variant in self.mutant_tree.all_mutant_objects
        ]

        if self.parallel_run:
            parallel_executor = ParallelExecutor(
                self.process_mutant,
                args=self.mutagenesis_tasks,
                n_jobs=self.nproc,
            )

            parallel_executor.start()

            while not parallel_executor.isFinished():
                # logging.info(f'Running ....')
                refresh_window()
                time.sleep(0.001)

            self.results = parallel_executor.handle_result()

            logging.info("Merging all sessions .... This may take a while ...")

            cmd.hide('surface')

            self.mutagenesis_sessions = [
                session_path for session_path in self.results if session_path
            ]
            gc.collect()
        else:
            self.mutagenesis_sessions = []
            for mutagenesis_task in self.mutagenesis_tasks:
                self.mutagenesis_sessions.append(
                    self.process_mutant(*mutagenesis_task)
                )

                # https://www.jianshu.com/p/38562df9e65d
                # refresh UI if calculation is not done.

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

        # **** IMPORTANT *****:::::
        # `save_session` will be altered after successful merge so you have to manually set it back to final result.
        self.output_pse=session_merger.save_session

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
            self.save_session = merged_temp_session
        else:
            logging.warning(
                f'Temperal merged result is failed to create. Try again with a clean PyMOL session. \n'
                f'STDOUT:\n{merge_results.stdout}\n'
                f'STDERR:\n{merge_results.stderr}'
            )
            return

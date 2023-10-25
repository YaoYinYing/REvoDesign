import os
import time
import tempfile
import pandas as pd
from Bio.Data import IUPACData
from Bio import SeqIO
from pymol import cmd, util
import matplotlib

matplotlib.use('Agg')

from REvoDesign.common.magic_numbers import DEFAULT_PROFILE_TYPE
from REvoDesign.common.Mutant import Mutant
from REvoDesign.phylogenetics.pymol_pssm_script import mutate
from REvoDesign.tools.merge_sessions import merge_sessions
from REvoDesign.tools.utils import (
    get_color,
    extract_mutants,
    extract_mutant_info,
    get_molecule_sequence,
)
from absl import logging


class MutantVisualizer:
    def __init__(self, molecule, chain_id):
        self.molecule = molecule
        self.chain_id = chain_id
        self.mutfile = ''
        self.input_session = None
        self.save_session = None
        self.nproc = os.cpu_count()
        self.full = False
        self.cmap = "bwr_r"
        self.key_col = "best_leaf"
        self.score_col = "totalscore"
        self.group_name = 'default_group'
        self.sequence = get_molecule_sequence(
            molecule=self.molecule, chain_id=self.chain_id
        )
        self.profile = ''
        self.profile_format = DEFAULT_PROFILE_TYPE

        # this should be set via the following:
        # visualizer=MutantVisualizer(molecule=molecule,chain_id=chainid)
        # visualizer.profile_scoring_df=visualizer.parse_profile(
        #         profile_fp=design_profile,
        #         profile_format=design_profile_format)
        self.profile_scoring_df = None

        self.min_score = 0.5
        self.max_score = 0.5

        self.min_score_profile = 0
        self.max_score_profile = 0

        self.consider_global_score_from_profile = False

    def process_position(self, mutant_obj: Mutant):
        mutant = mutant_obj.get_mutant_id()
        score = mutant_obj.get_mutant_score()
        temp_dir = tempfile.mkdtemp(prefix='pymol_pssm_')
        temp_session_path = os.path.join(temp_dir, f"position_{mutant}.pse")
        cmd.load(self.input_session)

        cmd.hide('surface')

        color = get_color(self.cmap, score, self.min_score, self.max_score)
        logging.info(f" Visualizing {mutant} {score}: {color}")
        self.create_mutagenesis_objects(mutant_obj, color)
        cmd.hide('everything', 'hydrogens and polymer.protein')
        cmd.delete(self.molecule)
        cmd.save(temp_session_path)
        cmd.reinitialize()
        return temp_session_path

    # provide a full function of PyMOL mutate that requires explicit mutagenesis description
    def create_mutagenesis_objects(self, mutant_obj: Mutant, color):
        # mutant: <chain_id><wt><pos><mut>_..._<score>
        mutant = mutant_obj.get_mutant_id()
        new_obj_name = mutant
        cmd.create(f"{new_obj_name}", self.molecule)

        mut_pos = []
        score = mutant_obj.get_mutant_score()

        for mut_info in mutant_obj.get_mutant_info():
            chain_id = mut_info['chain_id']
            position = mut_info['position']
            new_residue = mut_info['mut_res']

            new_residue_3 = IUPACData.protein_letters_1to3[new_residue].upper()
            # mut_pos.append(position)

            mut_pos.append(f'(c. {chain_id} and i. {str(position)})')
            mutate(new_obj_name, chain_id, position, new_residue_3)

            if score:
                cmd.alter(
                    f" {new_obj_name} and i. {str(position)} and (sidechain or n. CA) ",
                    f'b={score}',
                )

            cmd.hide('lines', f'{new_obj_name}')
            cmd.show(
                "sticks",
                f' {new_obj_name} and c. {chain_id} and i. {str(position)} and (sidechain or n. CA) and (not hydrogen)',
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

    def parse_profile(self, profile_fp, profile_format):
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

    def run_with_progressbar(self, progress_bar):
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
            _mutation_data = [
                extract_mutant_info(
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
                _mutation_data.pop(None)
            mutation_data = pd.DataFrame.from_dict(
                {self.key_col: _mutation_data}
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
            logging.info(
                f"Warning: Score column '{self.score_col}' not found in the data. Setting score to 1."
            )
            mutation_data[self.score_col] = 1

        self.mutant_list = []
        score_list = []
        for _, row in mutation_data.iterrows():
            variant, variant_obj = extract_mutants(
                mutant_string=row[self.key_col],
                chain_id=self.chain_id,
                sequence=self.sequence,
            )

            # skip None variant (failed to be parsed)
            if not variant:
                continue

            _variant_info = variant_obj.get_mutant_info()

            # the profile scoring is a bit more complicated if the mutant contains multiple substitutions.
            # so we have to igore it here.
            if (
                len(_variant_info) == 1
                and self.profile_scoring_df is not None
                and (not self.profile_scoring_df.empty)
            ):
                _score = self.profile_scoring_df.loc[
                    _variant_info[0]['mut_res'],
                    str(int(_variant_info[0]['position']) - 1),
                ]
                logging.debug(
                    f'Reading profile score for variant {variant_obj.get_mutant_id()}: {_score}'
                )
            else:
                _score = row[self.score_col]
                logging.debug(
                    f'Reading mutant table score for variant {variant_obj.get_mutant_id()}: {_score}'
                )

            variant_obj.set_mutant_score(float(_score))

            self.mutant_list.append(variant_obj)

            score_list.append(float(_score))

        # Determine the range for color bar

        if (
            self.consider_global_score_from_profile
            and (self.profile_scoring_df is not None)
            and (not self.profile_scoring_df.empty)
        ):
            self.min_score = self.min_score_profile
            self.max_score = self.max_score_profile

        else:
            self.min_score = min(score_list)
            self.max_score = max(score_list)

        self.run_mutagenesis_tasks(progress_bar=progress_bar)

    def run_mutagenesis_tasks(self, progress_bar):
        from REvoDesign.tools.utils import refresh_window, ParallelExecutor

        # Create a multiprocessing pool
        self.mutagenesis_tasks = [[variant] for variant in self.mutant_list]

        progress_bar.setRange(0, 0)

        parallel_executor = ParallelExecutor(
            self.process_position,
            args=self.mutagenesis_tasks,
            n_jobs=self.nproc,
        )

        parallel_executor.start()

        while not parallel_executor.isFinished():
            # logging.info(f'Running ....')
            refresh_window()
            time.sleep(0.001)

        progress_bar.setRange(0, len(self.mutant_list))
        progress_bar.setValue(len(self.mutant_list))

        self.results = parallel_executor.handle_result()
        cmd.reinitialize()

        logging.info("Merging all sessions .... This may take a while ...")

        cmd.hide('surface')

        mutagenesis_sessions = [
            session_path for session_path in self.results if session_path
        ]
        logging.debug(f'mutangesis_sessions: {mutagenesis_sessions}')

        merged_temp_session = f"{os.path.join(os.path.dirname(self.save_session), f'.tmp_{os.path.basename(self.save_session)}')}"
        merge_sessions(
            session_paths=mutagenesis_sessions,
            save_path=merged_temp_session,
            mode=2,
            quiet=0,
        )

        merge_sessions(
            session_paths=[self.input_session, merged_temp_session],
            save_path=self.save_session,
            mode=2,
            quiet=0,
        )

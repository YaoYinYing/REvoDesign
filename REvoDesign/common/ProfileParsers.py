from abc import ABC, abstractmethod
from dataclasses import dataclass
import os

import pandas as pd

from REvoDesign import issues
from REvoDesign import root_logger

logging = root_logger.getChild(__name__)


class ProfileManager:
    def __init__(self, profile_type: str):
        self.profile_type = profile_type
        self.parser: ProfileParserAbstract = None

    def _initialize_parser(self, kwargs):
        if self.profile_type == 'Pythia-ddG':
            return Pythia_ddG_Parser(**kwargs)

        if self.profile_type == 'PSSM':
            return PSSM_Parser(**kwargs)

        elif self.profile_type == 'CSV':
            return CSVProfileParser(**kwargs)
        elif self.profile_type == 'TSV':
            return TSVProfileParser(**kwargs)

        else:
            raise issues.InvalidInputError(
                f'Unknown profile format {self.profile_type}: {kwargs=}'
            )

    def parse(self, kwargs):
        if not (parser := self._initialize_parser(kwargs)):
            raise issues.ConfigureError(
                f'Failed to parse profile in {self.profile_type} with config ({kwargs=})'
            )

        self.parser = parser
        self.parser.parse()


@dataclass
class ProfileParserAbstract(ABC):
    profile_input: str
    molecule: str
    chain_id: str
    sequence: str

    df: pd.DataFrame = None

    @abstractmethod
    def parse(self) -> pd.DataFrame:
        ...

    @property
    def score_max_abs(self) -> float:
        if not isinstance(self.df, pd.DataFrame) or self.df.empty:
            raise issues.UnexpectedWorkflowError('dataframe is not parsed!')
        return max(abs(self.df.min().min()), abs(self.df.max().max()))

    @property
    def min_score_profile(self) -> float:
        return -self.score_max_abs

    @property
    def max_score_profile(self) -> float:
        return self.score_max_abs

    @property
    def profile_input_bn(self) -> str:
        if self.profile_input and os.path.exists(self.profile_input):
            return os.path.basename(self.profile_input)
        raise issues.InvalidInputError(f'Not a file: {self.profile_input=}')

    @property
    def is_valid_profile(self) -> bool:
        return os.path.exists(self.profile_input)


class PSSM_Parser(ProfileParserAbstract):
    @staticmethod
    def convert_PSSM_file_to_df(input_pssm_file):
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

    def parse(self) -> pd.DataFrame:
        if not self.is_valid_profile:
            raise issues.NoResultsError(
                f'Profile {self.profile_input} does not exist.'
            )

        df_pssm_raw = self.convert_PSSM_file_to_df(
            input_pssm_file=self.profile_input
        )
        csv_fp = os.path.join(
            os.path.dirname(self.profile_input), f'{self.profile_input_bn}.csv'
        )
        df_pssm_raw.to_csv(csv_fp)
        logging.info(f'Saving CSV at {csv_fp=}')
        self.df = pd.read_csv(csv_fp, index_col=0)
        logging.debug(
            f'Profile data: min {self.min_score_profile} max {self.max_score_profile}'
        )

        return self.df


class CSVProfileParser(ProfileParserAbstract):
    def parse(self) -> pd.DataFrame:
        if not self.is_valid_profile:
            raise issues.NoResultsError(
                f'Profile {self.profile_input} does not exist.'
            )

        self.df = self._parse()
        logging.debug(
            f'Profile data: min {self.min_score_profile} max {self.max_score_profile}'
        )
        return self.df

    def _parse(self):
        df = pd.read_csv(self.profile_input, index_col=0)
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

            return df
        else:
            logging.debug(
                f'Failed to process profile data {self.profile_input}..'
            )
            return


# TODO this may not work
class TSVProfileParser(ProfileParserAbstract):
    def parse(self) -> pd.DataFrame:
        if not self.is_valid_profile:
            raise issues.NoResultsError(
                f'Profile {self.profile_input} does not exist.'
            )
        self.df = pd.read_table(self.profile_input, names=['mut', 'score'])
        return self.df


class Pythia_ddG_Parser(ProfileParserAbstract):
    def parse(self) -> pd.DataFrame:
        self.profile_input = os.path.join(
            os.path.abspath('.'),
            'pythia',
            f'{self.molecule}_pred_mask.csv',
        )
        if not os.path.exists(self.profile_input):
            self._run_cloud()
        else:
            logging.warning(
                f'Find expected Pythia output: `{self.profile_input}`, skipping.'
            )
        # a nested call of parse_profile to convert ddg csv into dataframe.
        csv_parser = CSVProfileParser(
            profile_input=self.profile_input,
            molecule=self.molecule,
            chain_id=self.chain_id,
            sequence=self.sequence,
        )
        csv_parser.parse()

        self.df = csv_parser.df

        return self.df

    def _run_cloud(self):
        from REvoDesign.clients.PythiaBiolibClient import PythiaBiolib

        ddg_runner = PythiaBiolib(
            molecule=self.molecule, chain_id=self.chain_id
        )
        ddg_runner.work_dir = os.path.join(os.path.abspath('.'), 'pythia')
        os.makedirs(ddg_runner.work_dir, exist_ok=True)
        self.profile_input = ddg_runner.predict()

        if not self.profile_input:
            logging.error('Oops! error occurs during pythia running!')
            return

        logging.debug(f'Result file is stored at: {self.profile_input}')
        ddg_runner.cite()

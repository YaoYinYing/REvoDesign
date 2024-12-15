'''
Module for DataFrame parsers.
'''

import os
from abc import ABC, abstractmethod

import pandas as pd

from REvoDesign import issues, root_logger

logging = root_logger.getChild(__name__)


class ProfileParserAbstract(ABC):
    """
    `ProfileParserAbstract` is an abstract base class designed to parse profile data associated with
    molecular structures.

    Attributes:
    - `profile_input`: str, the path to the input profile file.
    - `molecule`: str, the name of the molecule.
    - `chain_id`: str, identifier for a specific chain within the molecule's structure.
    - `sequence`: str, the amino acid or nucleotide sequence related to the profile.
    - `df`: pd.DataFrame, optional, stores parsed data; default is None.

    Abstract Methods:
    - `parse()`: Must be implemented by subclasses to parse the profile data into a DataFrame.

    Properties:
    - `score_max_abs`: float, computes the maximum absolute value from the parsed DataFrame's min and max values.
    - `min_score_profile`: float, derived from `score_max_abs`, represents the minimum possible score for the profile.
    - `max_score_profile`: float, derived from `score_max_abs`, represents the maximum possible score for the profile.
    - `profile_input_bn`: str, returns the basename of `profile_input` if it exists as a file.
    - `is_valid_profile`: bool, checks if the `profile_input` file exists.
    """

    name: str
    # whether lower scores are preferred
    prefer_lower: bool = False

    def __init__(
        self,
        profile_input: str,
        molecule: str,
        chain_id: str,
        sequence: str,
    ):

        self.profile_input = profile_input
        self.molecule = molecule
        self.chain_id = chain_id
        self.sequence = sequence

        # internal variables
        self.df: pd.DataFrame = None  # type: ignore

    @abstractmethod
    def parse(self) -> pd.DataFrame:
        """
        Abstract method to be implemented by subclasses that parses the profile data and returns it as a DataFrame.

        Returns:
        - pd.DataFrame, containing the parsed profile data.
        """
        ...

    @property
    def score_max_abs(self) -> float:
        """
        Computes the maximum absolute value between the minimum and maximum values of the DataFrame.

        Returns:
        - float, maximum absolute value found in the DataFrame.

        Raises:
        - UnexpectedWorkflowError: If the DataFrame is not properly initialized or empty.
        """
        if not isinstance(self.df, pd.DataFrame) or self.df.empty:
            raise issues.UnexpectedWorkflowError("dataframe is not parsed!")
        return max(abs(self.df.min().min()), abs(self.df.max().max()))

    @property
    def min_score_profile(self) -> float:
        """
        Calculates the minimum possible score for the profile based on `score_max_abs`.

        Returns:
        - float, representing the minimum score.
        """
        return -self.score_max_abs

    @property
    def max_score_profile(self) -> float:
        """
        Calculates the maximum possible score for the profile based on `score_max_abs`.

        Returns:
        - float, representing the maximum score.
        """
        return self.score_max_abs

    @property
    def profile_input_bn(self) -> str:
        """
        Retrieves the basename of the `profile_input` file if it exists.

        Returns:
        - str, the basename of the input file.

        Raises:
        - InvalidInputError: If `profile_input` does not point to an existing file.
        """
        if self.profile_input and os.path.exists(self.profile_input):
            return os.path.basename(self.profile_input)
        raise issues.InvalidInputError(f"Not a file: {self.profile_input=}")

    @property
    def is_valid_profile(self) -> bool:
        """
        Validates whether the `profile_input` file exists.

        Returns:
        - bool, True if the file exists, False otherwise.
        """
        return os.path.exists(self.profile_input)


class PSSM_Parser(ProfileParserAbstract):
    name = "PSSM"

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
        PSSM_Alphabet = "ARNDCQEGHILKMFPSTWYV"
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
                f"Profile {self.profile_input} does not exist."
            )

        df_pssm_raw = self.convert_PSSM_file_to_df(
            input_pssm_file=self.profile_input
        )

        # Explanation: Add 1 to each column index to convert to one-indexing
        df_pssm_raw.columns = [col + 1 for col in range(len(df_pssm_raw.columns))]

        csv_fp = os.path.join(
            os.path.dirname(self.profile_input), f"{self.profile_input_bn}.csv"
        )
        df_pssm_raw.to_csv(csv_fp)
        logging.info(f"Saving CSV at {csv_fp=}")
        self.df = pd.read_csv(csv_fp, index_col=0)
        logging.debug(
            f"Profile data: min {self.min_score_profile} max {self.max_score_profile}"
        )

        return self.df


class CSVProfileParser(ProfileParserAbstract):
    name = "CSV"
    prefer_lower = True

    def parse(self) -> pd.DataFrame:
        if not self.is_valid_profile:
            raise issues.NoResultsError(
                f"Profile {self.profile_input} does not exist."
            )

        self.df = self._parse()
        logging.debug(
            f"Profile data: min {self.min_score_profile} max {self.max_score_profile}"
        )
        return self.df

    def _parse(self):
        df = pd.read_csv(self.profile_input, index_col=0)
        df = df.astype(float)

        # try to transpose if the shape is 20 col x N row
        if len(df.columns) == 20:
            df = df.T
            logging.debug("Profile data is transposed.")

            column_rename_mapping = {pos: str(pos) for pos in df.columns}
            logging.debug(f"Rename column : {column_rename_mapping}")
            df.rename(columns=column_rename_mapping, inplace=True)

        if str(df.columns[0]) != "0":
            logging.debug("Profile data does not matche default format.")
            # Calculate the number of columns (N) in the DataFrame
            len(df.columns)

            logging.debug(f"Column : {df.columns}")

            # Create a dictionary to map old column names to new column names
            column_rename_mapping = {
                str(int(i)): str(int(i) - 1) for i in df.columns
            }

            logging.debug(f"Rename column : {column_rename_mapping}")

            # Rename the columns using the mapping
            df.rename(columns=column_rename_mapping, inplace=True)

        logging.debug(df.columns)

        if (
            len(df.columns) == len(self.sequence.replace("X", ""))
            and "X" in self.sequence
        ):
            logging.warning("Missing residues from structure.")

            non_missing_resi = [
                i for i, j in enumerate(self.sequence) if j != "X"
            ]
            # Create a dictionary to map old column names to new column names
            column_rename_mapping = {
                str(int(i)): str(int(j))
                for i, j in zip(df.columns, non_missing_resi)
            }
            # Rename the columns using the mapping
            df.rename(columns=column_rename_mapping, inplace=True)
            logging.debug(f"Repaired: {df.columns}")

            # Fill missing columns with zeros
            logging.warning("Filling missing with zeros")
            for i, j in enumerate(self.sequence):
                if j == "X":
                    df.insert(
                        loc=i, column=f"{i}", value=[0 for k in range(20)]
                    )

            logging.debug(f"Filled: {df.columns}")

        if len(df.columns) > 20 and str(df.columns[0]) == "0":
            logging.debug("Profile data matches default format.")

            return df
        else:
            logging.debug(
                f"Failed to process profile data {self.profile_input}.."
            )
            return


# TODO this may not work
class TSVProfileParser(ProfileParserAbstract):
    name = "TSV"

    def parse(self) -> pd.DataFrame:
        if not self.is_valid_profile:
            raise issues.NoResultsError(
                f"Profile {self.profile_input} does not exist."
            )
        self.df = pd.read_table(self.profile_input, names=["mut", "score"])
        return self.df


class Pythia_ddG_Parser(ProfileParserAbstract):
    """
    The `Pythia_ddG_Parser` class is designed to parse the binding free energy (ddG) predictions from Pythia
    and convert them into a DataFrame format.

    Methods:
    - `parse`: Parses the ddG data and returns it as a pandas DataFrame. If the expected output does not exist,
    triggers a cloud computation.
    - `_run_cloud`: Internal method to initiate Pythia calculations in case the output is not found locally.
    Sets up the working directory and handles the execution and citation of Pythia.
    """

    name = "Pythia-ddG"
    prefer_lower = True

    def parse(self) -> pd.DataFrame:
        """
        Parses the Pythia ddG prediction file and returns its content as a pandas DataFrame.

        Returns:
        - `pd.DataFrame`: DataFrame containing parsed ddG data.

        If the expected Pythia output file does not exist, the `_run_cloud` method is invoked to generate
        the predictions remotely.
        """
        self.profile_input = os.path.join(
            os.path.abspath("."),
            "pythia",
            f"{self.molecule}_pred_mask.csv",
        )

        # Check for existing Pythia output; if not present, initiate cloud computation.
        if not os.path.exists(self.profile_input):
            self._run_cloud()
        else:
            logging.warning(
                f"Found expected Pythia output: `{self.profile_input}`, skipping computation."
            )

        # Instantiate and use CSVProfileParser to convert the CSV into a DataFrame.
        csv_parser = CSVProfileParser(
            profile_input=self.profile_input,
            molecule=self.molecule,
            chain_id=self.chain_id,
            sequence=self.sequence,
        )
        csv_parser.parse()

        # Assign the DataFrame from CSVParser to this instance's attribute.
        self.df = csv_parser.df

        return self.df

    def _run_cloud(self):
        """
        Internal method that triggers Pythia calculations in a remote environment when local output is missing.

        Establishes the working directory for Pythia, initiates the prediction process, and handles result
        storage and citation.
        In case of errors during Pythia execution, logs an error message.
        """
        from REvoDesign.clients.PythiaBiolibClient import PythiaBiolib

        ddg_runner = PythiaBiolib(
            molecule=self.molecule, chain_id=self.chain_id
        )
        ddg_runner.work_dir = os.path.join(os.path.abspath("."), "pythia")
        os.makedirs(ddg_runner.work_dir, exist_ok=True)

        # Execute Pythia prediction and handle potential errors.
        self.profile_input = ddg_runner.predict()

        if not self.profile_input:
            logging.error("An error occurred during the Pythia run!")
            return

        logging.debug(f"The result file is stored at: {self.profile_input}")
        ddg_runner.cite()


all_parser_classes = (
    PSSM_Parser,
    CSVProfileParser,
    TSVProfileParser,
    Pythia_ddG_Parser,
)


class ProfileManager:
    def __init__(self, profile_type: str):
        self.profile_type = profile_type
        self.parser: ProfileParserAbstract = None  # type: ignore

    def _initialize_parser(self, kwargs) -> "ProfileParserAbstract":

        try:
            parser_class = [
                parser
                for parser in all_parser_classes
                if parser.name == self.profile_type
            ][0]
            return parser_class(**kwargs)

        except IndexError:
            raise issues.InvalidInputError(
                f"Unknown profile format {self.profile_type}: {kwargs=}"
            )

    def parse(self, kwargs):
        if not (parser := self._initialize_parser(kwargs)):
            raise issues.ConfigureError(
                f"Failed to parse profile in {self.profile_type} with config ({kwargs=})"
            )

        self.parser = parser
        self.parser.parse()

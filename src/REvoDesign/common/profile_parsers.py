import os
from abc import ABC, abstractmethod
import pandas as pd
from REvoDesign import ROOT_LOGGER, issues
logging = ROOT_LOGGER.getChild(__name__)
class ProfileParserAbstract(ABC):
    name: str
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
        self.df: pd.DataFrame = None  
    @abstractmethod
    def parse(self) -> pd.DataFrame:
        ...
    @property
    def score_max_abs(self) -> float:
        if not isinstance(self.df, pd.DataFrame) or self.df.empty:
            raise issues.UnexpectedWorkflowError("dataframe is not parsed!")
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
        raise issues.InvalidInputError(f"Not a file: {self.profile_input=}")
    @property
    def is_valid_profile(self) -> bool:
        return os.path.exists(self.profile_input)
class PSSM_Parser(ProfileParserAbstract):
    name = "PSSM"
    @staticmethod
    def convert_PSSM_file_to_df(input_pssm_file):
        PSSM_Alphabet = "ARNDCQEGHILKMFPSTWYV"
        c = 0
        for line in open(input_pssm_file):
            pssm_header = line
            c += 1
            if c == 3:
                break
        logging.info(pssm_header)
        _idx = [pssm_header.index(ab) for ab in PSSM_Alphabet]
        logging.info(_idx)
        _width = _idx[1] - _idx[0]
        colspec = [
            (_idx[i] - _width + 1, _idx[i] + 1) for i in range(len(_idx))
        ]
        logging.info(colspec)
        df = pd.read_fwf(input_pssm_file, skiprows=2, colspecs=colspec)
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
        if len(df.columns) == 20:
            df = df.T
            logging.debug("Profile data is transposed.")
            column_rename_mapping = {pos: str(pos) for pos in df.columns}
            logging.debug(f"Rename column : {column_rename_mapping}")
            df.rename(columns=column_rename_mapping, inplace=True)
        if str(df.columns[0]) != "0":
            logging.debug("Profile data does not matche default format.")
            len(df.columns)
            logging.debug(f"Column : {df.columns}")
            column_rename_mapping = {
                str(int(i)): str(int(i) - 1) for i in df.columns
            }
            logging.debug(f"Rename column : {column_rename_mapping}")
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
            column_rename_mapping = {
                str(int(i)): str(int(j))
                for i, j in zip(df.columns, non_missing_resi)
            }
            df.rename(columns=column_rename_mapping, inplace=True)
            logging.debug(f"Repaired: {df.columns}")
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
        logging.debug(
            f"Failed to process profile data {self.profile_input}.."
        )
        raise issues.InvalidInputError(f"Failed to process profile data {self.profile_input}..")
class TSVProfileParser(ProfileParserAbstract):
    name = "TSV"
    def parse(self) -> pd.DataFrame:
        if not self.is_valid_profile:
            raise issues.NoResultsError(
                f"Profile {self.profile_input} does not exist."
            )
        self.df = pd.read_table(self.profile_input, names=["mut", "score"])
        return self.df
ALL_PARSER_CLASSES = (
    PSSM_Parser,
    CSVProfileParser,
    TSVProfileParser,
)
class ProfileManager:
    def __init__(self, profile_type: str):
        self.profile_type = profile_type
        self.parser: ProfileParserAbstract = None  
    def _initialize_parser(self, kwargs) -> "ProfileParserAbstract":
        try:
            parser_class = [
                parser
                for parser in ALL_PARSER_CLASSES
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
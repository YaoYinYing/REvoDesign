'''
Shortcut functions of sequence designs
'''


import os

import warnings


from REvoDesign import ROOT_LOGGER, issues
from REvoDesign.common.profile_parsers import PSSM_Parser


logging = ROOT_LOGGER.getChild(__name__)


def shortcut_pssm2csv(pssm: str) -> None:
    """Shortcut for PSSM to CSV conversion.

    Args:
        pssm (str): PSSM raw file path

    Returns:
        None
    """
    logging.info(f"Converting {pssm}...")
    p = PSSM_Parser(profile_input=pssm, molecule="", chain_id="", sequence="")
    p.parse()

    expected_csv = f"{pssm}.csv"
    if not os.path.exists(expected_csv):
        warnings.warn(issues.NoResultsWarning(f"Expected {expected_csv=}"))

    logging.info(expected_csv)


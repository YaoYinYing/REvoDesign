'''
Utils for Rosetta
'''
import os
from typing import List, Union
import warnings

from RosettaPy.utils.repository import partial_clone

from platformdirs import user_cache_dir

from REvoDesign import issues


def setup_minimal_rosetta_db(subdirectory_to_clone: str):
    """
    Sets up the minimal Rosetta database required by cloning a specific subdirectory from the Rosetta repository.

    Args:
    subdirectory_to_clone (str): The subdirectory in the Rosetta database to clone.

    Returns:
    str: The path to the Rosetta database after cloning.
    """
    # Get the ROSETTA3_DB environment variable
    rosetta3_db_path = os.environ.get("ROSETTA3_DB")
    # If the environment variable exists, return its value directly
    if rosetta3_db_path:
        return rosetta3_db_path

    # Partially clone the Rosetta database
    rosetta3_db_path = partial_clone(
        repo_url="https://github.com/RosettaCommons/rosetta",
        target_dir=user_cache_dir('rosetta_db_clone', ensure_exists=True),
        subdirectory_as_env="database",
        subdirectory_to_clone=subdirectory_to_clone,
        env_variable="ROSETTA3_DB",
    )
    # Output the value of the ROSETTA3_DB environment variable
    print(f'ROSETTA3_DB={os.environ.get("ROSETTA3_DB")}')
    return rosetta3_db_path


def list_fastrelax_scripts() -> List[str]:
    """
    Lists the fast relax scripts in the Rosetta database.

    Returns:
    List[str]: A list of names of the fast relax scripts.
    """
    # Specify the subdirectory containing the relax scripts
    subdirectory = "sampling/relax_scripts"
    # Set up the Rosetta database and get the database path
    rosetta3_db_path = setup_minimal_rosetta_db(f"database/{subdirectory}")

    # List all the relax scripts in the specified subdirectory and remove the .txt extension
    all_relax_scripts = [
        f.rstrip('.txt') for f in os.listdir(
            os.path.join(
                rosetta3_db_path,
                subdirectory)) if f.endswith('.txt') and not f.startswith('README')]
    return all_relax_scripts


def extra_res_to_opts(ligands_params: Union[List[str], str]) -> List[str]:
    """
    Generates options for ligand parameters.

    Parameters:
        ligands_params (Union[List[str], str]): List of ligand parameters or a single parameter.

    Returns:
        List[str]: List of command-line options for ligand parameters.
    """
    if isinstance(ligands_params, str):
        ligands_params = ligands_params.split('|')

    ligands = []
    for _, l in enumerate(ligands_params):
        if not (isinstance(l, str) and l.endswith(".params")):
            warnings.warn(issues.BadDataWarning(f"Invalid Parameter input for ligand - {l}"))
            continue

        if not os.path.isfile(l):
            warnings.warn(issues.BadDataWarning(f"Ignore nofound ligand - {l}"))
            continue

        ligands.extend(["-extra_res_fa" if l.endswith("fa.params") else "-extra_res_cen", os.path.abspath(l)])
    return ligands

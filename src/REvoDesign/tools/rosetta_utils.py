'''
Utils for Rosetta
'''
import os
import platform
import shutil
import warnings
from typing import Any, Dict, List, Optional, Union

import docker
import docker.errors
from hydra import errors as hydra_errors
from omegaconf import DictConfig
from platformdirs import user_cache_dir
from RosettaPy.node import NodeHintT
from RosettaPy.node.wsl import which_wsl
from RosettaPy.utils.repository import partial_clone

from REvoDesign import ROOT_LOGGER, issues
from REvoDesign.bootstrap.set_config import ConfigConverter, reload_config_file
from REvoDesign.driver.ui_driver import ConfigBus

logging = ROOT_LOGGER.getChild(__name__)


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
        f[:-4] for f in os.listdir(
            os.path.join(
                rosetta3_db_path,
                subdirectory)) if f.endswith('.txt') and not f.startswith('README') and '.dualspace' not in f]
    return all_relax_scripts


def extra_res_to_opts(ligands_params: Union[List[str], str]) -> List[str]:
    """
    Generates options for ligand parameters.

    Parameters:
        ligands_params (Union[List[str], str]): List of ligand parameters or a single parameter.

    Returns:
        List[str]: List of command-line options for ligand parameters.
    """
    if not ligands_params:
        return []
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


def is_run_node_available(node_hint: Optional[NodeHintT]) -> bool:
    """
    Determine if the specified runtime environment indicated by `node_hint` is available.

    Parameters:
    - node_hint (Optional[NodeHintT]): A hint that specifies the desired runtime environment.

    Returns:
    - bool: True if the specified runtime environment is available, False otherwise.
    """

    # Check for "native" or unspecified environment by verifying the ROSETTA_BIN environment variable
    if node_hint is None or node_hint == "native":
        return not os.environ.get("ROSETTA_BIN", "") == ""

    # Check for WSL environment availability on Windows systems
    if node_hint.startswith("wsl"):
        if platform.system() != "Windows":
            return False
        return is_wsl_available()

    # Check for Docker environment availability
    if node_hint.startswith("docker"):
        return is_docker_available()

    # Check for MPI environment availability by checking if mpirun is in PATH
    if node_hint == "mpi":
        return shutil.which("mpirun") is not None

    return False


def is_wsl_available():
    """
    Check if Windows Subsystem for Linux (WSL) is available on the current machine.

    This function attempts to determine if WSL is available by trying to locate the WSL binary.
    If the WSL binary is found, it indicates that WSL is available.

    Returns:
        bool: Returns True if WSL is available, otherwise returns False.
    """
    try:
        # Attempt to get the path of the WSL binary
        wsl_bin = which_wsl()
        # If the WSL binary is found, return True
        return wsl_bin is not None
    except RuntimeError:
        # If an error occurs, it indicates that WSL may not be available
        warnings.warn(
            issues.PlatformNotSupportedWarning(
                "WSL is not available on this machine."
            )
        )
        # Return False, indicating that WSL is not available
        return False


def is_docker_available() -> bool:
    """
    Checks if Docker is available on the current machine.

    This function attempts to connect to Docker using the Docker client from the environment.
    If the connection is successful, it indicates that Docker is available, and the function returns True.
    If a DockerException is raised during the connection attempt, it indicates that Docker is not available,
    and a warning is issued before returning False.

    Returns:
        bool: True if Docker is available, otherwise False.
    """
    try:
        # Attempt to create a Docker client and then release the reference to test Docker's availability.
        client = docker.from_env()
        del client
        return True
    except docker.errors.DockerException as e:
        # If Docker is not available, issue a warning and return False.
        warnings.warn(issues.PlatformNotSupportedWarning(
            f"Docker is not available(uninstalled or unlaunched) on this machine: {e}"))
        return False


def read_rosetta_node_config() -> Dict[str, Any]:
    '''
    Read the Rosetta node configuration from the configuration bus.

    Returns:
        Dict[str, str]: Dictionary containing the Rosetta node configuration.
            If no node config is found, it returns an empty dictionary.
    '''

    bus = ConfigBus()
    rosetta_node_hint = bus.get_value('rosetta.node_hint', str)
    logging.info(f"Using Rosetta node: {rosetta_node_hint}")

    try:
        node_config: DictConfig = reload_config_file(f'rosetta-node/{rosetta_node_hint}')['rosetta-node']['node_config']
    except hydra_errors.MissingConfigException as e:
        raise issues.ConfigureOutofDateError(
            f'Rosetta node config not found. Please check your configuration files.') from e

    logging.info(f"Using node config: {node_config}")
    node_config.update({"nproc": bus.get_value("ui.header_panel.nproc", int)})
    logging.info(f"Using node config: {node_config}")
    return ConfigConverter.convert(node_config)

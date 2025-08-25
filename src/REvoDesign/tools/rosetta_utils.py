'''
Utils for Rosetta
'''
import copy
import os
import platform
import shutil
import warnings
from typing import Any, Dict, List, Optional, Sequence, Union
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
ALL_NODES: Sequence[NodeHintT] = ("docker", "docker_mpi", "mpi", "wsl", "wsl_mpi", "native")
def setup_minimal_rosetta_db(subdirectory_to_clone: str):
    """
    Sets up the minimal Rosetta database required by cloning a specific subdirectory from the Rosetta repository.
    Args:
    subdirectory_to_clone (str): The subdirectory in the Rosetta database to clone.
    Returns:
    str: The path to the Rosetta database after cloning.
    """
    
    rosetta3_db_path = os.environ.get("ROSETTA3_DB")
    
    if rosetta3_db_path:
        return rosetta3_db_path
    
    rosetta3_db_path = partial_clone(
        repo_url="https://github.com/RosettaCommons/rosetta",
        target_dir=user_cache_dir('rosetta_db_clone', ensure_exists=True),
        subdirectory_as_env="database",
        subdirectory_to_clone=subdirectory_to_clone,
        env_variable="ROSETTA3_DB",
    )
    
    print(f'ROSETTA3_DB={os.environ.get("ROSETTA3_DB")}')
    return rosetta3_db_path
def list_fastrelax_scripts() -> List[str]:
    """
    Lists the fast relax scripts in the Rosetta database.
    Returns:
    List[str]: A list of names of the fast relax scripts.
    """
    
    subdirectory = "sampling/relax_scripts"
    
    rosetta3_db_path = setup_minimal_rosetta_db(f"database/{subdirectory}")
    
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
    
    if node_hint is None or node_hint == "native":
        return os.environ.get("ROSETTA_BIN", "") != ""
    
    if node_hint.startswith("wsl"):
        if platform.system() != "Windows":
            return False
        return is_wsl_available()
    
    if node_hint.startswith("docker"):
        return is_docker_available()
    
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
        
        wsl_bin = which_wsl()
        
        return wsl_bin is not None
    except RuntimeError:
        
        warnings.warn(
            issues.PlatformNotSupportedWarning(
                "WSL is not available on this machine."
            )
        )
        
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
        
        client = docker.from_env()
        del client
        return True
    except docker.errors.DockerException as e:
        
        warnings.warn(issues.PlatformNotSupportedWarning(
            f"Docker is not available(uninstalled or unlaunched) on this machine: {e}"))
        return False
def is_rosetta_runnable() -> bool:
    """
    Check if there are available run nodes to execute Rosetta tasks
    This function iterates through all nodes and checks if at least one run node is available.
    It verifies the availability of each node by calling the is_run_node_available function.
    Returns:
        bool: True if at least one run node is available, False otherwise
    """
    
    return any(is_run_node_available(node_hint) for node_hint in ALL_NODES)
IS_ROSETTA_RUNNABLE: bool = is_rosetta_runnable()
def read_rosetta_config(key_path: str = "rosetta.opts.general") -> List[str]:
    """
    Read Rosetta configuration options and parse them into a list of strings
    Args:
        key_path (str): Path to the configuration key, defaults to "rosetta.opts.general"
    Returns:
        List[str]: Parsed Rosetta configuration options as a list of strings
    """
    
    opts = ConfigBus().get_value(key_path, str)
    logging.warning(f"Got Rosetta opts: {opts}")
    
    rosetta_general_opts: List[str] = opts.split(" ")
    
    if rosetta_general_opts == [''] or not rosetta_general_opts:
        rosetta_general_opts = []
    logging.warning(f"Using Rosetta opts: {rosetta_general_opts}")
    return rosetta_general_opts
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
ROSETTA_COMMON_CITATION: dict[str, Union[str, tuple]] = {
    'Rosetta': """@article{10.1038/s41592-020-0848-2, author = {Leman, J. K. and Weitzner, B. D. and Lewis, S. M. and Adolf‐Bryfogle, J. and Alam, N. and Alford, R. F. and Aprahamian, M. L. and Baker, D. and Barlow, K. A. and Barth, P. and Basanta, B. and Bender, B. J. and Blacklock, K. and Bonet, J. and Boyken, S. E. and Bradley, P. and Bystroff, C. and Conway, P. and Cooper, S. and Correia, B. E. and Coventry, B. and Das, R. and Jong, R. M. d. and DiMaio, F. and Dsilva, L. and Dunbrack, R. L. and Ford, A. S. and Frenz, B. and Fu, D. and Geniesse, C. and Goldschmidt, L. and Gowthaman, R. and Gray, J. J. and Gront, D. and Guffy, S. L. and Horowitz, S. and Huang, P. and Huber, T. and Jacobs, T. M. and Jeliazkov, J. R. and Johnson, D. K. and Kappel, K. and Karanicolas, J. and Khakzad, H. and Khar, K. R. and Khare, S. D. and Khatib, F. and Khramushin, A. and King, C. and Kleffner, R. and Koepnick, B. and Kortemme, T. and Kuenze, G. and Kuhlman, B. and Kuroda, D. and Labonte, J. W. and Lai, J. and Lapidoth, G. and Leaver‐Fay, A. and Lindert, S. and Linsky, T. W. and London, N. and Lubin, J. H. and Lyskov, S. and Maguire, J. B. and Malmström, L. and Marcos, E. and Marcu, O. and Marze, N. and Meiler, J. and Moretti, R. and Mulligan, V. K. and Nerli, S. and Norn, C. and Ó’Conchúir, S. and Ollikainen, N. and Ovchinnikov, S. and Pacella, M. S. and Pan, X. and Park, H. and Pavlovicz, R. E. and Pethe, M. A. and Pierce, B. G. and Pilla, K. B. and Raveh, B. and Renfrew, P. D. and Burman, S. S. R. and Rubenstein, A. B. and Sauer, M. F. and Scheck, A. and Schief, W. R. and Schueler‐Furman, O. and Sedan, Y. and Sevy, A. M. and Sgourakis, N. G. and Shi, L. and Siegel, J. B. and Silva, D. and Smith, S. T. and Song, Y. and Stein, A. and Szegedy, M. and Teets, F. D. and Thyme, S. B. and Wang, R. Y. and Watkins, A. M. and Zimmerman, L. and Bonneau, R.}, title = {Macromolecular modeling and design in rosetta: recent methods and frameworks}, journal = {Nature Methods}, year = {2020}, volume = {17}, issue = {7}, pages = {665-680}, doi = {10.1038/s41592-020-0848-2} }""",
    'Rosetta3': """
@incollection{LEAVERFAY2011545,
title = {Chapter nineteen - Rosetta3: An Object-Oriented Software Suite for the Simulation and Design of Macromolecules},
editor = {Michael L. Johnson and Ludwig Brand},
series = {Methods in Enzymology},
publisher = {Academic Press},
volume = {487},
pages = {545-574},
year = {2011},
booktitle = {Computer Methods, Part C},
issn = {0076-6879},
doi = {https://doi.org/10.1016/B978-0-12-381270-4.00019-6},
url = {https://www.sciencedirect.com/science/article/pii/B9780123812704000196},
author = {Andrew Leaver-Fay and Michael Tyka and Steven M. Lewis and Oliver F. Lange and James Thompson and Ron Jacak and Kristian W. Kaufman and P. Douglas Renfrew and Colin A. Smith and Will Sheffler and Ian W. Davis and Seth Cooper and Adrien Treuille and Daniel J. Mandell and Florian Richter and Yih-En Andrew Ban and Sarel J. Fleishman and Jacob E. Corn and David E. Kim and Sergey Lyskov and Monica Berrondo and Stuart Mentzer and Zoran Popović and James J. Havranek and John Karanicolas and Rhiju Das and Jens Meiler and Tanja Kortemme and Jeffrey J. Gray and Brian Kuhlman and David Baker and Philip Bradley},
abstract = {We have recently completed a full rearchitecturing of the Rosetta molecular modeling program, generalizing and expanding its existing functionality. The new architecture enables the rapid prototyping of novel protocols by providing easy-to-use interfaces to powerful tools for molecular modeling. The source code of this rearchitecturing has been released as Rosetta3 and is freely available for academic use. At the time of its release, it contained 470,000 lines of code. Counting currently unpublished protocols at the time of this writing, the source includes 1,285,000 lines. Its rapid growth is a testament to its ease of use. This chapter describes the requirements for our new architecture, justifies the design decisions, sketches out central classes, and highlights a few of the common tasks that the new software can perform.}
}""",
    'RosettaScripts': """
@article{10.1371/journal.pone.0020161,
    doi = {10.1371/journal.pone.0020161},
    author = {Fleishman, Sarel J. AND Leaver-Fay, Andrew AND Corn, Jacob E. AND Strauch, Eva-Maria AND Khare, Sagar D. AND Koga, Nobuyasu AND Ashworth, Justin AND Murphy, Paul AND Richter, Florian AND Lemmon, Gordon AND Meiler, Jens AND Baker, David},
    journal = {PLOS ONE},
    publisher = {Public Library of Science},
    title = {RosettaScripts: A Scripting Language Interface to the Rosetta Macromolecular Modeling Suite},
    year = {2011},
    month = {06},
    volume = {6},
    url = {https://doi.org/10.1371/journal.pone.0020161},
    pages = {1-10},
    abstract = {Macromolecular modeling and design are increasingly useful in basic research, biotechnology, and teaching. However, the absence of a user-friendly modeling framework that provides access to a wide range of modeling capabilities is hampering the wider adoption of computational methods by non-experts. RosettaScripts is an XML-like language for specifying modeling tasks in the Rosetta framework. RosettaScripts provides access to protocol-level functionalities, such as rigid-body docking and sequence redesign, and allows fast testing and deployment of complex protocols without need for modifying or recompiling the underlying C++ code. We illustrate these capabilities with RosettaScripts protocols for the stabilization of proteins, the generation of computationally constrained libraries for experimental selection of higher-affinity binding proteins, loop remodeling, small-molecule ligand docking, design of ligand-binding proteins, and specificity redesign in DNA-binding proteins.},
    number = {6},
}""",
    'Rosetta All-Atom Energy Function': """
@article{10.1021/acs.jctc.7b00125, author = {Alford, R. F. and Leaver‐Fay, A. and Jeliazkov, J. R. and O’Meara, M. J. and DiMaio, F. and Park, H. and Shapovalov, M. V. and Renfrew, P. D. and Mulligan, V. K. and Kappel, K. and Labonte, J. W. and Pacella, M. S. and Bonneau, R. and Bradley, P. and Dunbrack, R. L. and Das, R. and Baker, D. and Kuhlman, B. and Kortemme, T. and Gray, J. J.}, title = {The rosetta all-atom energy function for macromolecular modeling and design}, journal = {Journal of Chemical Theory and Computation}, year = {2017}, volume = {13}, issue = {6}, pages = {3031-3048}, doi = {10.1021/acs.jctc.7b00125} }"""
}
def copy_rosetta_citation(citetation: dict[str, Union[str, tuple]]) -> dict[str, Union[str, tuple]]:
    """
    Copy Rosetta citation information and update with custom citation content
    This function creates a copy of the Rosetta common citation information and updates it
    with the provided custom citation information. It is mainly used to generate complete
    citation information by combining common and specific parts.
    Parameters:
        citetation (dict[str, Union[str, tuple]]): Custom citation information dictionary
                                                  used to update the common citation information
    Returns:
        dict[str, Union[str, tuple]]: Updated complete citation information dictionary
    """
    
    cc = copy.copy(ROSETTA_COMMON_CITATION)  
    
    cc.update(citetation)
    return cc
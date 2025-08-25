'''
Molecule utilities with PyMOL
TODO: deprecate this module with biotite or biopython
'''
import os
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from immutabledict import immutabledict
from pymol import cmd, get_version_message
from pymol.parsing import QuietException
from pymol.setting import index_dict
from REvoDesign import issues
from REvoDesign.logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)
def is_empty_session():
    return len(cmd.get_names(type="objects", enabled_only=0)) == 0
def is_hidden_object(selection="(all)"):
    return (
        len(cmd.get_names(type="objects", selection=selection, enabled_only=1))
        == 0
    )
def fetch_exclusion_expressions():
    return [""] + [sel for sel in refresh_all_selections()]
def is_polymer_protein(sele=""):
    """
    Check if the selection represents a protein polymer with at least 10 residues.
    Args:
        sele (str): Selection string. Defaults to an empty string.
    Returns:
        bool or None: Returns True if the selection represents a protein polymer with at least 10 residues,
                      otherwise returns False. Returns None if the selection is empty.
    """
    if not sele:
        return None  
    
    resi_list = [
        at.resi for at in cmd.get_model(f"({sele}) and polymer.protein").atom
    ]
    unique_residues = set(resi_list)
    
    return len(unique_residues) > 10
def find_small_molecules_in_protein(sele):
    """
    Find small molecules within a protein selection.
    Args:
        sele (str): Selection string.
    Returns:
        list or None: Returns a list of unique small molecule names found within the selection.
                      Returns an empty list if no small molecules are found or if the selection is empty.
                      Returns None if the selection is not provided.
    """
    if not sele:
        warnings.warn(
            issues.NoInputWarning(
                "Selection for small molecules is not provided."
            )
        )
        return None  
    
    small_molecules = [
        at.resn
        for at in cmd.get_model(f"( {sele} ) and (not polymer.protein)").atom
    ]
    logging.info(f"Found small molecule names: {small_molecules}")
    unique_small_molecules = list(set(small_molecules))
    if unique_small_molecules:
        warnings.warn(
            issues.MoleculeWarning(
                "Could not find unique small molecules with standalone chain id. \n"
                'A possible fix is calling `alter r. RES, chain="<chain-id>"` to fix the problem \n'
                "then re-load this session."
            )
        )
        
        return unique_small_molecules
    warnings.warn(issues.FallingBackWarning("Falling back to all `hetatm`"))
    small_molecules = [
        at.resn
        for at in cmd.get_model("hetatm and (not polymer.protein)").atom
    ]
    unique_small_molecules = list(set(small_molecules))
    
    return unique_small_molecules if unique_small_molecules else []
def find_design_molecules():
    """
    Find design molecules that are polymer proteins.
    Returns:
        list: Returns a list of design molecules that are identified as polymer proteins.
    """
    
    objects = [
        object
        for object in cmd.get_names(
            "public_nongroup_objects", enabled_only=1, selection="all"
        )
        if is_polymer_protein(object)
    ]
    if not objects:
        raise issues.MoleculeUnloadedError(
            "Failed to load objects. Is it enabled?"
        )
    return objects
def find_all_protein_chain_ids_in_protein(sele) -> List[str]:
    """
    Function: find_all_protein_chain_ids_in_protein
    Usage: chain_ids = find_all_protein_chain_ids_in_protein(selection)
    This function finds all chain IDs assigned to a protein molecule within the given selection.
    Args:
    - sele (str): PyMOL selection string
    Returns:
    - list: List of chain IDs assigned to a protein molecule within the selection.
            Returns None if the selection is empty or no protein chains are found.
    """
    if not sele:
        return []
    
    chain_ids = [chain_id for chain_id in cmd.get_chains(sele) if chain_id]
    all_chains = [
        chain_id
        for chain_id in chain_ids
        if is_polymer_protein(f"( {sele} and c. {chain_id} )")
    ]
    if not all_chains:
        raise issues.MoleculeError(f"Fail to fetch all chain ids in {sele=}")
    return all_chains
def is_distal_residue_pair(
    molecule,
    chain_id,
    resi_1,
    resi_2,
    minimal_distance=20,
    use_sidechain_angle=False,
):
    """
    Check if a pair of amino acid residues are distal based on certain conditions.
    Parameters:
    - molecule (str): The name of the molecule.
    - chain_id (str): The chain identifier.
    - resi_1 (int): The residue number of the first amino acid.
    - resi_2 (int): The residue number of the second amino acid.
    - minimal_distance (float, optional): The minimum distance threshold for residues to be considered distal. Default is 20.
    - use_sidechain_angle (bool, optional): Whether to consider the orientation of side chains. Default is False.
    Returns:
    - distal (bool): True if the residues are distal, False otherwise.
    """
    
    sequence = get_molecule_sequence(molecule=molecule, chain_id=chain_id)
    
    resi_1 = int(resi_1)
    resi_2 = int(resi_2)
    
    resn_1 = sequence[resi_1 - 1]
    resn_2 = sequence[resi_2 - 1]
    
    Ca_atom_1 = f"{molecule} and c. {chain_id} and i. {resi_1} and n. CA"
    Ca_atom_2 = f"{molecule} and c. {chain_id} and i. {resi_2} and n. CA"
    
    Ca_distance = cmd.get_distance(atom1=Ca_atom_1, atom2=Ca_atom_2)
    
    if (not use_sidechain_angle) or any(
        resn == "G" for resn in [resn_1, resn_2]
    ):
        return Ca_distance > minimal_distance
    
    SC_atoms_1 = f"{molecule} and c. {chain_id} and i. {resi_1} and sidechain and not hydrogen"
    SC_atoms_2 = f"{molecule} and c. {chain_id} and i. {resi_2} and sidechain and not hydrogen"
    
    Ca_atom_1_coord = np.array(cmd.get_coords(Ca_atom_1)[0])
    Ca_atom_2_coord = np.array(cmd.get_coords(Ca_atom_2)[0])
    SC_COM_1 = np.array(cmd.centerofmass(SC_atoms_1))
    SC_COM_2 = np.array(cmd.centerofmass(SC_atoms_2))
    
    sidechain_orient = np.dot(
        SC_COM_1 - Ca_atom_1_coord, SC_COM_2 - Ca_atom_2_coord
    )
    sidechain_com_dist = abs(np.linalg.norm(SC_COM_1 - SC_COM_2))
    
    if sidechain_orient < 0:
        if sidechain_com_dist >= Ca_distance:
            
            
            logging.warning(
                f"Sidechain: {resi_1}{resn_1} vs {resi_2}{resn_2}: opposite, distal."
            )
            return True
        
        
        logging.warning(f'Sidechain: {resi_1}{resn_1} vs {resi_2}{resn_2}: opposite, '
                        f'{"distal" if sidechain_com_dist > minimal_distance else "closed"}.')
        return sidechain_com_dist > minimal_distance
    logging.warning(f'Sidechains: {resi_1}{resn_1} and {resi_2}{resn_2}: same, '
                    f'{"distal" if sidechain_com_dist > minimal_distance else "closed"}.')
    
    
    
    
    
    
    return sidechain_com_dist > minimal_distance
def renumber_chain_ids(target_protein):
    """
    Function: renumber_chain_ids
    Usage: renumber_chain_ids(target_protein)
    This function renumbers chain IDs of a given protein molecule using alphabets A-Z.
    It alters the chain IDs of the protein structure in PyMOL.
    Args:
    - target_protein (str): PyMOL selection string of the target protein
    Returns:
    - None
    """
    chain_ids = cmd.get_chains(target_protein)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for chain_id, _alphabet in zip(chain_ids, alphabet):
        logging.info(f"rechain: {chain_id} - {_alphabet}")
        cmd.alter(
            f"{target_protein} and c. {chain_id}", f"chain='{_alphabet}'"
        )
def get_molecule_sequence(molecule, chain_id, keep_missing=True):
    """
    Function: get_molecule_sequence
    Usage: sequence = get_molecule_sequence(molecule, chain_id)
    This function retrieves the amino acid sequence of a molecule (protein) specified by a given chain ID.
    Args:
    - molecule (str): PyMOL selection string of the molecule
    - chain_id (str): Chain ID of the molecule
    - keep_missing (bool): Keep missing residues in structure as 'X'
    Returns:
    - str: Amino acid sequence of the specified molecule and chain
    """
    from Bio.Data import IUPACData
    protein_letters_3to1_upper = {
        key.upper(): val.upper()
        for key, val in IUPACData.protein_letters_3to1.items()
    }
    CA = [
        atom
        for atom in cmd.get_model(
            f"( {molecule} and c. {chain_id} and n. CA )"
        ).atom
    ]
    if keep_missing:
        resi = [int(atom.resi) for atom in CA]
        resi_max = max(resi)
        resn = []
        offset = 0
        for i in range(1, resi_max + 1):
            if i in resi:
                res = CA[i - 1 + offset].resn
                resn.append(protein_letters_3to1_upper[res])
            else:
                resn.append("X")
                offset -= 1
        return "".join(resn)
    return "".join([protein_letters_3to1_upper[atom.resn] for atom in CA])
def get_atom_pair_cst(selection="sele"):
    """
    Function: get_atom_pair_cst
    Usage: cst = get_atom_pair_cst(selection='sele')
    This function generates a distance constraint (cst) in CHARMM format for a pair of atoms selected in PyMOL.
    Args:
    - selection (str): PyMOL selection string for the atom pair (default is 'sele')
    Returns:
    - str or None: Distance constraint in CHARMM format if exactly 2 atoms are selected; otherwise, returns None
    """
    _s = cmd.get_model(selection=selection).atom
    if len(_s) != 2:
        logging.error(
            f"Atom pair selection {selection} must contain exactly 2 atoms!"
        )
        return
    cst = f"AtomPair {_s[0].name} {_s[0].resi}{_s[0].chain} {_s[1].name} {_s[1].resi}{_s[1].chain} HARMONIC 3 0.5"
    return cst
def autogrid_flexible_residue(molecule, chain_id, selection):
    """
    Function: autogrid_flexible_residue
    Usage: flex_residues = autogrid_flexible_residue(molecule, chain_id, selection)
    This function generates a string specifying flexible residues for AutoGrid in AutoDock.
    Args:
    - molecule (str): PyMOL selection string of the molecule
    - chain_id (str): Chain ID of the molecule
    - selection (str): PyMOL selection string for residue selection
    Returns:
    - str or None: String specifying flexible residues for AutoGrid in AutoDock.
                   Returns None if any of the input parameters (molecule, chain_id, selection) are invalid.
    """
    if not molecule or not chain_id or not selection:
        logging.warning(
            f"Invalid parameters: \nmolecule - {molecule}\n chain_id - {chain_id} \n selection - {selection}"
        )
        return None
    residues = "_".join(
        list(
            {
                f"{at.resn.upper()}{at.resi}"
                for at in cmd.get_model(f"{selection} and n. CA").atom
            }
        )
    )
    autodock_flexible_residues = f"{molecule}:{chain_id}:{residues}"
    logging.info(
        f"Flexible residues for AutoGrid: {autodock_flexible_residues}"
    )
    return autodock_flexible_residues
def refresh_all_selections():
    """
    Function: refresh_all_selections
    Usage: selections = refresh_all_selections()
    This function refreshes and logs information about all PyMOL selections except 'sele' and those starting with '_align'.
    Returns:
    - list: List of all non-'sele' selections (excluding those starting with '_align')
    """
    from REvoDesign.tools.mutant_tools import shorter_range
    selections = [
        sel
        for sel in cmd.get_names(type="selections")
        if sel != "sele" and (not sel.startswith("_align"))
    ]
    for sel in selections:
        _resi = sorted(list({at.resi for at in cmd.get_model(sel).atom}))
        logging.info(f"{sel}: i. {shorter_range([int(x) for x in _resi])}")
    return selections
def is_a_REvoDesign_session():
    """
    Function: is_a_REvoDesign_session
    Usage: result = is_a_REvoDesign_session()
    This function checks if it's a REvoDesign session by verifying the
    existence of public group objects.
    Returns:
    - bool: True if it's a REvoDesign session (public group objects exist),
        False otherwise.
    """
    if check := bool(cmd.get_names(type="public_group_objects")):
        warnings.warn(
            issues.REvoDesignSessionsWarning(
                "Loading mutants into a REvoDesign session may trigger"
                "unexpected segmentation fault.\nIn order to keep the"
                "session's feature, you should always create seperate"
                "sessions according to your dataset and merge them "
                "manually in PyMOL window."
            )
        )
    return check
def make_temperal_input_pdb(
    molecule,
    chain_id="",
    segment_id="",
    resn="",
    selection="",
    save_as_format="pdb",
    wd=os.getcwd(),
    reload=True,
):
    """
        Function: make_temperal_input_pdb
        Usage: input_file = make_temperal_input_pdb(molecule, chain_id=None, segment_id=None, format='pdb', wd=os.getcwd(), reload=True)
    exi
        This function generates a temporary input PDB file from the specified molecule selection.
        It supports selection by chain ID, segment ID, or both.
        Args:
        - molecule (str): PyMOL selection string of the molecule
        - chain_id (str): Chain id of the molecule (default is None)
        - segment_id (str): Segment id of the molecule (default is None)
        - resn (str): Residue name of the molecule (useful for small-molecule ligand)
        - selection (str): Customized selection in PyMOL syntax.
        - format (str): File format for the generated PDB file (default is 'pdb')
        - wd (str): Working directory path where the file will be saved (default is current working directory)
        - reload (bool): Whether to reload the PyMOL session after generating the file (default is True)
        Returns:
        - str: Path to the generated temporary input PDB file
    """
    os.makedirs(wd, exist_ok=True)
    input_file = os.path.join(
        wd,
        f'seg{segment_id}_chain{chain_id}_resn{resn}_sel{selection.replace(" ", "-")[:20]}',
        f"{molecule}.{save_as_format}",
    )
    os.makedirs(os.path.dirname(input_file), exist_ok=True)
    selection_str = molecule
    if chain_id:
        selection_str += f" and chain {chain_id}"
    if segment_id:
        selection_str += f" and segi {segment_id}"
    if resn:
        selection_str += f" and resn {resn}"
    if selection:
        selection_str += f" and {selection}"
    try:
        cmd.save(input_file, selection_str, -1)
    except QuietException:
        raise issues.MoleculeUnloadedError(
            "Could not save molecule because it is not loaded yet."
        )
    if reload:
        cmd.reinitialize()
        cmd.load(input_file)
    logging.warning(
        "A temporary session is created based on your molecule selection: \n"
        f"{molecule} (chain: {chain_id}, segment: {segment_id}), resn: {resn} --> {input_file}"
    )
    return input_file
def extract_smiles_from_chain(
    molecule, chain_id="", segment_id="", resn="", selection=""
) -> list[str]:
    from rdkit import Chem
    from rdkit.Chem import MolToSmiles
    """
    Function: extract_smiles_from_chain
    Usage: smiles_string = extract_smiles_from_chain(molecule, chain_id=None, segment_id=None)
    This function extracts the SMILES string of a small molecule from a given chain and/or segment identifier
    in a PyMOL session.
    Usage:
    `
        python
        from REvoDesign.tools.pymol_utils import extract_smiles_from_chain
        print(extract_smiles_from_chain(molecule='1hx9', chain_id='A', segment_id='D', resn='FHP', selection=''))
        python end
    `
    Args:
    - molecule (str): PyMOL selection string of the molecule
    - chain_id (str): Chain identifier from which SMILES will be extracted (default is None)
    - segment_id (str): Segment identifier from which SMILES will be extracted (default is None)
    - resn (str): Residue from which SMILES will be extracted (default is None)
    Returns:
    - str: The SMILES string list of the specified molecule
    """
    
    temp_pdb = make_temperal_input_pdb(
        molecule,
        chain_id=chain_id,
        segment_id=segment_id,
        resn=resn,
        selection=selection,
        save_as_format="sdf",
        wd=os.path.abspath("./ligand"),
        reload=False,
    )
    
    smiles = []
    with Chem.SDMolSupplier(temp_pdb, removeHs=False) as suppl:
        for mol in suppl:
            if mol is None:
                continue
            print(mol.GetNumAtoms())
            
            smiles.append(MolToSmiles(mol))
    
    
    return smiles
def any_posision_has_been_selected():
    selected_positions = [
        x
        for x in cmd.get_names(type="selections", enabled_only=1)
        if x == "sele"
    ]
    return bool(selected_positions)
def get_all_groups(enabled_only: bool = False) -> List[str]:
    return cmd.get_names("group_objects", int(enabled_only))
def renumber_protein_chain(molecule: Union[str, List[str]], chain: Optional[str] = None, offset: int = 0) -> None:
    """
    Renumbers a protein chain in PyMOL by applying an offset to residue indices.
    Args:
        molecule (str|List[str]): Name of the PyMOL molecule object.
        chain (Optional[str]): Name of the chain to be renumbered. If None, applies to all chains.
        offset (int): Residue index offset to apply (default is 0, meaning no change).
    Usage:
        
        renumber_protein_chain("8X3E", "A", 32)
        
        renumber_protein_chain("1ABC", offset=-10)
    """
    if offset == 0:
        return  
    if isinstance(molecule, (list, tuple)):
        molecule = f' ({" or ".join(molecule)}) '
    selection = f"{molecule}" if chain is None else f"{molecule} and chain {chain}"
    cmd.alter(selection, f"resv += {offset}")
    cmd.rebuild()  
PYMOL_SETTINGS: immutabledict[str, int] = immutabledict(index_dict)
@dataclass
class PyMOLSetting:
    name: str
    val: Any
    typing: type
    obj: Optional[str] = ''
    def apply(self):
        cmd.set(self.name, self.typing(self.val), selection=self.obj or '')
    @property
    def as_dict_item(self) -> Tuple[str, Any]:
        return self.name, self
def get_pymol_settings(keyword: str, obj: Optional[str] = '') -> Dict[str, PyMOLSetting]:
    return {
        key_name: PyMOLSetting(key_name, cmd.get(key_name, selection=obj or ''), type(cmd.get(key_name)), obj)
        for key_name in PYMOL_SETTINGS
        if keyword in key_name
    }
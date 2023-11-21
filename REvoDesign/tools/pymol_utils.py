from pymol import cmd
from absl import logging
import os

from REvoDesign.tools.mutant_tools import shorter_range
from REvoDesign.tools.utils import suppress_print

PYMOL_VERSION = cmd.get_version()[0]


def is_empty_session():
    return len(cmd.get_names(type='objects', enabled_only=0)) == 0


def fetch_exclusion_expressions():
    return [""] + [sel for sel in refresh_all_selections()]


def is_polymer_protein(sele=''):
    if not sele:
        return None

    # return a bool of protein that contain at least 10 residues
    return (
        len(
            set(
                [
                    at.resi
                    for at in cmd.get_model(
                        f'({sele}) and polymer.protein'
                    ).atom
                ]
            )
        )
        > 10
    )


def find_small_molecules_in_protein(sele):
    if not sele:
        return
    # return a list of small molecules
    return [''] + list(
        set(
            [
                at.resn
                for at in cmd.get_model(
                    f'( {sele} ) and (not polymer.protein)'
                ).atom
            ]
        )
    )


def find_design_molecules():
    objects = [
        object
        for object in cmd.get_names(
            'public_nongroup_objects', enabled_only=1, selection='all'
        )
        if is_polymer_protein(object)
    ]
    return objects


def find_all_protein_chain_ids_in_protein(sele):
    if not sele:
        return
    # return a list of chain IDs that assigned to a protein molecule
    return [
        chain_id
        for chain_id in cmd.get_chains(sele)
        if is_polymer_protein(f'( {sele} and c. {chain_id} )')
    ]


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

    # Step 1: Get the sequence of the molecule and chain
    sequence = get_molecule_sequence(molecule=molecule, chain_id=chain_id)

    # Convert residue numbers to integers
    resi_1 = int(resi_1)
    resi_2 = int(resi_2)

    # Retrieve one-letter amino acid codes for the two residues
    resn_1 = sequence[resi_1 - 1]
    resn_2 = sequence[resi_2 - 1]

    # Construct strings representing CA atoms of the two residues
    Ca_atom_1 = f'{molecule} and c. {chain_id} and i. {resi_1} and n. CA'
    Ca_atom_2 = f'{molecule} and c. {chain_id} and i. {resi_2} and n. CA'

    # Calculate the distance between the CA atoms
    Ca_distance = cmd.get_distance(atom1=Ca_atom_1, atom2=Ca_atom_2)

    # Check if either of the residues is glycine or not using sidechain angle
    if any([resn == 'G' for resn in [resn_1, resn_2]]) or (
        not use_sidechain_angle
    ):
        return Ca_distance > minimal_distance
    else:
        import numpy as np

        # Construct strings representing sidechain atoms of the two residues
        SC_atoms_1 = f'{molecule} and c. {chain_id} and i. {resi_1} and sidechain and not hydrogen'
        SC_atoms_2 = f'{molecule} and c. {chain_id} and i. {resi_2} and sidechain and not hydrogen'

        # Get coordinates of CA and Sidechain  atoms
        Ca_atom_1_coord = np.array(cmd.get_coords(Ca_atom_1)[0])
        Ca_atom_2_coord = np.array(cmd.get_coords(Ca_atom_2)[0])
        SC_COM_1 = np.array(cmd.centerofmass(SC_atoms_1))
        SC_COM_2 = np.array(cmd.centerofmass(SC_atoms_2))

        # Calculate the orientation of the side chains
        sidechain_orient = np.dot(
            SC_COM_1 - Ca_atom_1_coord, SC_COM_2 - Ca_atom_2_coord
        )
        sidechain_com_dist = abs(np.linalg.norm(SC_COM_1 - SC_COM_2))

        # Check if the side chains are oriented in opposite directions
        if sidechain_orient < 0:
            logging.warning(
                f'Sidechains of {resi_1}{resn_1} and {resi_2}{resn_2} are oriented in opposite directions. Considered as a distal pair.'
            )

            if sidechain_com_dist >= Ca_distance:
                # /-------------\
                # *---Ca   Ca---*
                return True
            else:
                #       /--\
                # Ca---*    *---Ca
                return sidechain_com_dist > minimal_distance
        else:
            logging.warning(
                f'Sidechains of {resi_1}{resn_1} and {resi_2}{resn_2} are oriented in same directions.'
            )
            # Ca---*
            #        \
            #         \
            #          \
            #      Ca---*
            # Check if sidechain distance is greater than the minimal distance
            return sidechain_com_dist > minimal_distance


def renumber_chain_ids(target_protein):
    chain_ids = cmd.get_chains(target_protein)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for chain_id, _alphabet in zip(chain_ids, alphabet):
        logging.info(f'rechain: {chain_id} - {_alphabet}')
        cmd.alter(
            f'{target_protein} and c. {chain_id}', f'chain=\'{_alphabet}\''
        )


def get_molecule_sequence(molecule, chain_id):
    from Bio.Data import IUPACData

    protein_letters_3to1_upper = {
        key.upper(): val.upper()
        for key, val in IUPACData.protein_letters_3to1.items()
    }
    return ''.join(
        [
            protein_letters_3to1_upper[atom.resn]
            for atom in cmd.get_model(
                f'( {molecule} and c. {chain_id} and n. CA )'
            ).atom
        ]
    )


def get_atom_pair_cst(selection='sele'):
    _sele = cmd.get_model(selection=selection).atom
    if len(_sele) != 2:
        logging.error(
            f'Atom pair selection {selection} must contain exactly 2 atoms!'
        )
        return
    else:
        cst = f'AtomPair {_sele[0].name} {_sele[0].resi}{_sele[0].chain} {_sele[1].name} {_sele[1].resi}{_sele[1].chain} HARMONIC 3 0.5'
        return cst


def autogrid_flexible_residue(molecule, chain_id, selection):
    if not molecule or not chain_id or not selection:
        logging.warning(
            f'Invalid parameters: \nmolecule - {molecule}\n chain_id - {chain_id} \n selection - {selection}'
        )
        return None
    residues = '_'.join(
        list(
            set(
                [
                    f'{at.resn.upper()}{at.resi}'
                    for at in cmd.get_model(f'{selection} and n. CA').atom
                ]
            )
        )
    )
    autodock_flexible_residues = f'{molecule}:{chain_id}:{residues}'
    logging.info(
        f'Flexible residues for AutoGrid: {autodock_flexible_residues}'
    )
    return autodock_flexible_residues


def refresh_all_selections():
    selections = [
        sel
        for sel in cmd.get_names(type='selections')
        if sel != 'sele' and (not sel.startswith('_align'))
    ]

    for sel in selections:
        _resi = sorted(list(set([at.resi for at in cmd.get_model(sel).atom])))
        logging.info(f'{sel}: i. {shorter_range([int(x) for x in _resi])}')
    return selections


def is_a_REvoDesign_session():
    return bool(cmd.get_names(type='public_group_objects'))


def make_temperal_input_pdb(molecule, format='pdb', wd=os.getcwd(), reload=True):
    os.makedirs(wd, exist_ok=True)

    input_file = os.path.join(wd, f'{molecule}.{format}')
    if not os.path.exists(input_file):
        cmd.save(input_file, f'{molecule}', -1)
    if reload:
        cmd.reinitialize()
        cmd.load(input_file)
    logging.warning(
        'A temperal session is created based on your molecule selection: \n'
        f'{molecule} --> {input_file}'
    )
    return input_file


# http://www.pymolwiki.org/index.php/rotkit
@suppress_print
def mutate(molecule, chain, resi, target="CYS", mutframe="1"):
    target = target.upper()
    cmd.wizard("mutagenesis")
    # cmd.do("refresh_wizard")
    cmd.refresh_wizard()
    cmd.get_wizard().set_mode("%s" % target)
    selection = "/%s//%s/%s" % (molecule, chain, resi)
    cmd.get_wizard().do_select(selection)
    cmd.frame(str(mutframe))
    cmd.get_wizard().apply()
    # cmd.set_wizard("done")
    cmd.set_wizard()
    # cmd.refresh()

cmd.extend("mutate", mutate)
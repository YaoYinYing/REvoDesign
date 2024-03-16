import os
import re
import json
import time

from omegaconf import DictConfig
from REvoDesign.common.Mutant import Mutant
from Bio.Data import IUPACData
from REvoDesign.common.MutantTree import MutantTree
from pymol import cmd
from REvoDesign.sidechain_solver import SidechainSolver
from REvoDesign.tools.pymol_utils import is_hidden_object
from REvoDesign.tools.utils import filepath_does_exists
from REvoDesign import ConfigBus, FileExtentions

from REvoDesign import root_logger

logging = root_logger.getChild(__name__)

# Dictionary comprehension to create a mapping from 3-letter amino acid codes to 1-letter codes.
# It utilizes the IUPACData module from Biopython, which contains standard codes for amino acids.
protein_letters_3to1 = {
    v.upper(): k.upper()  # Mapping the 3-letter code (value) to its corresponding 1-letter code (key)
    for k, v in IUPACData.protein_letters_1to3.items()  # Looping through the items in the 1-to-3-letter amino acid dictionary
}


def extract_mutants_from_mutant_id(
    mutant_string: str, sequences: dict = {}
) -> Mutant:
    '''
    Extract mutant info from an mutant id string. This mutant can be virtual from PyMOL session.

    Parameters:
    mutant_string (str): Underscore-seperated mutant string that contains the mutations and score (if possible).
                        <chain_id><wt_res><resi><mut_res>_...._<score>
    sequences (dict): Wild-type chain: sequence of design molecule

    Returns:
    tuple:
        Mutant : Mutant object.
    '''
    logging.debug(f'Parsing {mutant_string}')

    # Use regular expression to find all mutants in the string
    mutants = re.findall(r'([A-Z]{0,2}\d+[A-Z]{1})', mutant_string)

    mutant_info = []
    for mut in mutants:
        # full description of mutation, <chain_id><wt_res><pos><mut>
        if re.match(r'[A-Z]{2}\d+[A-Z]{1}', mut):
            logging.debug(f'full description: {mut}')
            _mut = re.match(r'([A-Z]{1})([A-Z]{1})(\d+)([A-Z]{1})', mut)
            _chain_id = _mut.group(1)

            _position = _mut.group(3)
            _wt_res = _mut.group(2)
            _mut_res = _mut.group(4)

        # reduced description of mutation, <wt_res><pos><mut>, missing <chain_id>
        elif re.match(r'[A-Z]{1}\d+[A-Z]{1}', mut):
            logging.debug(f'reduced description: {mut}')
            if not (mutant_info or sequences):
                logging.error(
                    f'Error while processing mutant id {mut}: Invalid sequences: {sequences}'
                )
                continue
            _mut = re.match(r'([A-Z]{1})(\d+)([A-Z]{1})', mut)

            _chain_id = list(sequences.keys())[0]
            _position = int(_mut.group(2))
            _wt_res = _mut.group(1)
            _mut_res = _mut.group(3)

        # fuzzy description of mutation, <pos><mut>, missing <chain_id> and <wt_res>
        elif re.match(r'\d+[A-Z]{1}', mut):
            logging.debug(f'fuzzy description: {mut}')
            # silent error report while mismatching the score term
            if not (mutant_info or sequences):
                logging.error(
                    f'Error while processing mutant id {mut}: Invalid sequences: {sequences}'
                )
                continue

            _mut = re.match(r'(\d+)([A-Z]{1})', mut)

            _chain_id = list(sequences.keys())[0]
            _position = int(_mut.group(1))
            _wt_res = list(sequences.values())[0][_position - 1]
            _mut_res = _mut.group(2)

        else:
            logging.error(f'Error while processing mutant id {mut}. ')
            continue

        mutant_info.append(
            {
                'chain_id': _chain_id,
                'position': int(_position),
                'wt_res': _wt_res,
                'mut_res': _mut_res,
            }
        )

    if not mutant_info:
        # early return if the input string failes to be parsed
        return Mutant(mutant_info, 0)

    # if the mutation has a position of score, we need to extract it.
    mutant_score = extract_mutant_score_from_string(
        mutant_string=mutant_string
    )

    # Instantializing a Mutant obj
    mutant_obj = Mutant(mutant_info, mutant_score)
    if sequences:
        mutant_obj.wt_sequences = sequences

    logging.debug(mutant_obj)

    # Join the mutants into a single string separated by underscores and instantialized Mutant obj
    return mutant_obj


def extract_mutant_score_from_string(mutant_string):
    '''
    Extract mutant score from an mutant string

    Parameters:
    mutant_string (str): Underscore-seperated mutant string that contains the mutations and score (if possible).
                        <chain_id><wt_res><resi><mut_res>_...._<score>

    Returns:
    float: Mutant score.
    '''
    if re.match(r'[\d+\w]+_[-\d\.e]+', mutant_string):
        matched_mutant_id = re.match(
            r'[\w\d\-]+_(\-?\d+\.?\d*e?\-?\d*)$', mutant_string
        )
        mutant_score = matched_mutant_id.group(1)
        mutant_score = float(mutant_score)
        return mutant_score
    return None


def extract_mutant_from_sequences(
    mutant_sequence, wt_sequence, chain_id='A', fix_missing=False
) -> Mutant:
    '''
    Extract mutant from mutant sequence.

    Parameters:
    mutant_sequence (str): Mutant sequence.
    wt_sequence (str): Wild-type sequence.
    chain_id (str): Chain id
    fix_missing (bool): Fix missing residue ('X') in mutant according to the WT sequence.

    Returns:
    Mutant: Mutant object
    '''
    _wt_sequence = wt_sequence.replace('X', '')
    _mutant_sequence = mutant_sequence.replace('X', '')

    if len(_mutant_sequence) != len(_wt_sequence):
        logging.error(
            f'Lengths of filtered WT and mutant are not equal to each other: {len(_wt_sequence)}: {len(_mutant_sequence)}'
        )
        return None

    if mutant_sequence == wt_sequence:
        logging.warning(f'WT and mutant sequences are identical.')
        return None

    if 'X' in wt_sequence and not fix_missing:
        logging.warning(f'WT has missing residue masked as "X"!')

    if fix_missing:
        _mutant_sequence = ''
        offset = 0
        for i, c in enumerate(wt_sequence):
            if c != 'X':
                _mutant_sequence += mutant_sequence[i + offset]
            else:
                _mutant_sequence += 'X'
                offset -= 1

        if len(_mutant_sequence) != len(wt_sequence):
            logging.error(
                f'Lengths of WT and fixed mutant are not equal to each other: {len(wt_sequence)}: {len(_mutant_sequence)}'
            )
            return None

        mutant_sequence = _mutant_sequence

    mut_info = [
        {
            'chain_id': chain_id,
            'position': i + 1,
            'wt_res': res,
            'mut_res': mutant_sequence[i],
        }
        for i, res in enumerate(wt_sequence)
        if res != mutant_sequence[i]
    ]
    logging.debug(mut_info)

    mutant_obj = Mutant(mutant_info=mut_info)
    mutant_obj.mutant_score = 0

    return mutant_obj


def shorter_range(input_list, connector='-', seperator='+'):
    """
    Shorten a list of integers by representing consecutive ranges with hyphens,
    and non-consecutive integers with plus signs.

    Parameters:
    input_list (list): A list of integers to be shortened.
    connector (str): A string for connecting consecutive ranges
    seperator (str): A string for separating non-consecutive ranges

    Returns:
    str: A string expression representing the shortened integer list.

    Example:
    >>> input_list = [395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409]
    >>> result = shorter_range(input_list)
    >>> print(result)
    "395-409"

    >>> input_list = [395, 396, 397, 398, 399, 400, 401, 403, 404, 405, 406, 407, 408, 409]
    >>> result = shorter_range(input_list)
    >>> print(result)
    "395-401+403-409"
    """

    # Filter out non-integer items and sort the list
    input_list = sorted([item for item in input_list if isinstance(item, int)])

    if not input_list:
        return

    range_pairs = []
    start, end = input_list[0], input_list[0]

    for item in input_list[1:]:
        if item == end + 1:
            end = item
        else:
            if start == end:
                range_pairs.append(str(start))
            else:
                range_pairs.append(f"{start}{connector}{end}")
            start, end = item, item

    # Handle the last range or single number
    if start == end:
        range_pairs.append(str(start))
    else:
        range_pairs.append(f"{start}{connector}{end}")

    return seperator.join(range_pairs)


def expand_range(shortened_str, connector='-', seperator='+') -> list[int]:
    """
    Expand a shortened string expression representing a list of integers to the original list.

    Parameters:
    shortened_str (str): A shortened string expression representing a list of integers.
    connector (str): A string for connecting consecutive ranges
    seperator (str): A string for separating non-consecutive ranges

    Returns:
    list: A list of integers corresponding to the original input.

    Example:
    >>> shortened_str = "395-401+403-409"
    >>> result = expand_range(shortened_str)
    >>> print(result)
    [395, 396, 397, 398, 399, 400, 401, 403, 404, 405, 406, 407, 408, 409]
    """
    expanded_list = []

    if shortened_str.isdigit():
        return [int(shortened_str)]

    ranges = shortened_str.split(seperator)

    for rng in ranges:
        if '-' in rng:
            start, end = map(int, rng.split(connector))
            expanded_list.extend(range(start, end + 1))
        else:
            expanded_list.append(int(rng))

    return expanded_list


def extract_mutant_from_pymol_object(pymol_object, sequences: dict) -> Mutant:
    '''
    Extract mutant info from an existing pymol object.

    Parameters:
    pymol_object (str): object to extract from.
    sequences (dict[str]): Wild-type sequence of design molecule and chain

    Returns:
    Mutant : Mutant object.
    '''
    from pymol import cmd

    mutant_info = []

    for chain_id in sequences:
        sequence = sequences[chain_id]
        for at in cmd.get_model(f'{pymol_object} and n. CA').atom:
            mutant_info.append(
                {
                    'chain_id': at.chain,
                    'position': int(at.resi),
                    'wt_res': sequence[int(at.resi) - 1] if sequence else 'X',
                    'mut_res': protein_letters_3to1[at.resn],
                }
            )

    mutant_obj = Mutant(mutant_info=mutant_info)
    mutant_obj.mutant_score = extract_mutant_score_from_string(pymol_object)
    mutant_obj.wt_sequences = sequences

    return mutant_obj


def read_customized_indice(custom_indices_from_input='') -> str:
    """
    Reads and processes customized indices based on the provided input.

    Args:
    - custom_indices_from_input (str): String containing customized indices.

    Returns:
    - str: Processed customized indices string.
    """

    if not custom_indices_from_input:
        return ''

    if filepath_does_exists(custom_indices_from_input):
        custom_indices_str = (
            open(custom_indices_from_input, 'r').read().strip()
        )
        return custom_indices_str

    # treat input as a digit
    if custom_indices_from_input.isdigit():
        return custom_indices_from_input

    # direct input of customized indices: 1-20;78-99
    if any([custom_indices_from_input.count(x) >= 1 for x in '-:,;+ ']):
        from REvoDesign.tools.utils import count_and_sort_characters

        _guessed_connector = count_and_sort_characters(
            input_string=custom_indices_from_input, characters='-:'
        )

        _guessed_seperator = count_and_sort_characters(
            input_string=custom_indices_from_input, characters=',;+ '
        )

        guessed_connector = (
            list(_guessed_connector.keys())[0] if _guessed_connector else '-'
        )
        guessed_seperator = (
            list(_guessed_seperator.keys())[0] if _guessed_seperator else ','
        )

        custom_indices_str = expand_range(
            shortened_str=custom_indices_from_input,
            connector=guessed_connector,
            seperator=guessed_seperator,
        )

        return ','.join([str(x) for x in custom_indices_str])

    else:
        logging.error(
            f'Failed in parsing customized indice file/string: {custom_indices_from_input}'
        )
        return ''


def process_mutations(data):
    """
    Process mutations based on provided data.

    Args:
    - data (dict): Dictionary containing 'indices' and 'mutations' keys.
                   'indices': List of positions.
                   'mutations': Dictionary of mutations with positions as keys.

    Returns:
    - list: List containing tuples of processed mutation data.
            Each tuple contains:
                - Position
                - Wild-type residue
                - Wild-type profile score
                - Candidates
    """
    positions = data['indices']
    mutations = data['mutations']
    result = []
    for position in positions:
        if str(position) in mutations:
            mutation = mutations[str(position)]
            wt_residue = mutation['wt']
            wt_profile_score = mutation['wt_profile_score']
            candidates = mutation['candidates']
            result.append((position, wt_residue, wt_profile_score, candidates))
    return result


def read_profile_design_mutations(filename):
    data = json.load(open(filename))
    return process_mutations(data)


def existed_mutant_tree(sequences: dict[str, str], enabled_only=1):
    """
    Creates a tree structure of existing mutants based on PyMOL objects.

    Parameters:
    - sequences: dict[str,str]
        A dict of strings representing the designable sequences.
        eg. {'A': 'MANGHFDTYE', 'B': 'MCSAKLPIQWE'}

    Returns:
    - MutantTree
        An instance of MutantTree class containing the mutant tree structure.
    """
    _mutant_tree = {
        group_id: {
            mutant_id: extract_mutant_from_pymol_object(
                pymol_object=mutant_id, sequences=sequences
            )
            for mutant_id in cmd.get_object_list(f'({group_id})')
            if not enabled_only or not is_hidden_object(selection=mutant_id)
        }
        for group_id in cmd.get_names(
            type='group_objects', enabled_only=enabled_only
        )
        if not group_id.startswith('multi_design')
    }
    return MutantTree(_mutant_tree)


def quick_mutagenesis(
    mutant_tree: MutantTree,
    sidechain_solver: SidechainSolver,
):
    from REvoDesign.common.MutantVisualizer import MutantVisualizer
    from REvoDesign.tools.pymol_utils import make_temperal_input_pdb
    from REvoDesign.tools.utils import run_worker_thread_with_progress

    bus: ConfigBus = ConfigBus()

    molecule = bus.get_value('ui.header_panel.input.molecule')
    chain_id = bus.get_value('ui.header_panel.input.chain_id')
    designable_sequences: dict = bus.get_value('designable_sequences')
    sequence: str = designable_sequences.get(chain_id)

    nproc = bus.get_value('ui.header_panel.nproc')
    progress_bar = bus.ui.progressBar

    if mutant_tree.empty:
        logging.warning(f'Mutant tree is empty!')
        return

    score_list = [
        mut_obj.mutant_score
        for group_id in mutant_tree.all_mutant_branch_ids
        for _, mut_obj in mutant_tree.get_a_branch(branch_id=group_id).items()
    ]

    results = []

    input_pdb = make_temperal_input_pdb(molecule=molecule, reload=False)
    visualizer = MutantVisualizer(molecule=molecule, chain_id=chain_id)
    cfg = bus.cfg

    visualizer.nproc = nproc
    visualizer.parallel_run = nproc > 1
    visualizer.input_session = input_pdb
    visualizer.sequence = sequence

    visualizer.full = cfg.ui.visualize.full_pdb
    visualizer.cmap = cfg.ui.header_panel.cmap
    visualizer.mutate_runner = sidechain_solver.mutate_runner

    visualizer.min_score = min(score_list)
    visualizer.max_score = max(score_list)

    for group_id in mutant_tree.all_mutant_branch_ids:
        visualizer.group_name = group_id

        visualizer.save_session = os.path.join(
            os.path.dirname(input_pdb),
            f'group.{group_id}.{os.path.basename(input_pdb).replace(".pdb",".pze")}',
        )

        visualizer.mutant_tree = MutantTree(
            {group_id: mutant_tree.get_a_branch(branch_id=group_id)}
        )

        visualizer.run_mutagenesis_tasks()
        results.append(visualizer.save_session)

    # call MutantVisualizer for merge sessions
    session_merger = MutantVisualizer(molecule='', chain_id='')
    session_merger.input_session = input_pdb
    session_merger.save_session = os.path.join(
        os.path.dirname(input_pdb),
        f'merged.{os.path.basename(input_pdb).replace(".pdb",".pze")}',
    )
    session_merger.mutagenesis_sessions = results
    run_worker_thread_with_progress(
        session_merger.merge_sessions_via_commandline,
        progress_bar=progress_bar,
    )
    cmd.load(session_merger.save_session, partial=2)
    return


def save_mutant_choices(output_mut_txt_fn: str, mutant_tree: MutantTree):
    if not mutant_tree:
        logging.error(f"No Mutant tree is given!")
        return

    if mutant_tree.empty:
        logging.warning(f'mutant tree is empty. save nothing.')
        return

    mutants_to_save = mutant_tree.all_mutant_ids
    logging.info(f"saving: {mutants_to_save}")

    # TODO mutant_choices function
    output_mut_txt_dir = os.path.dirname(output_mut_txt_fn)
    if not os.path.exists(output_mut_txt_dir):
        logging.warning(
            f'Parent dir for mutant table does NOT exist! {output_mut_txt_dir}'
        )
        # os.makedirs(output_mut_txt_dir,exist_ok=True)
        logging.warning(f'Skip saving mutant file.')
        return

    if os.path.exists(output_mut_txt_fn):
        logging.warning(
            f'Mutant table exists and will be overriden! {output_mut_txt_fn}'
        )
        write_input_mutant_table(
            output_mut_txt_fn,
            [mt.raw_mutant_id for mt in mutant_tree.all_mutant_objects],
        )

    else:
        logging.info(f'Mutant table is created at {output_mut_txt_fn}')
        write_input_mutant_table(
            output_mut_txt_fn,
            [mt.raw_mutant_id for mt in mutant_tree.all_mutant_objects],
        )

    output_mut_txt_dir_ckp = os.path.join(
        output_mut_txt_dir, f'./checkpoints/'
    )
    os.makedirs(output_mut_txt_dir_ckp, exist_ok=True)

    output_mut_txt_bn_ckp = f'ckp_{time.strftime("%Y%m%d_%H%M%S", time.localtime())}.{os.path.basename(output_mut_txt_fn)}'
    output_mut_txt_ckp = os.path.join(
        output_mut_txt_dir_ckp, output_mut_txt_bn_ckp
    )

    logging.info(f'Saving checkpoint: {output_mut_txt_ckp}')
    write_input_mutant_table(
        output_mut_txt_ckp, [mt for mt in mutants_to_save]
    )


def write_input_mutant_table(output_mut_txt_fn, mutant_list):
    open(output_mut_txt_fn, 'w').write(
        '\n'.join(mutant_list) if mutant_list else ''
    )


def determine_profile_type(profile_fp):
    profile_bn = os.path.basename(profile_fp)
    if profile_bn.endswith('.csv'):
        return 'CSV'
    elif profile_bn.endswith('.txt'):
        return 'TSV'
    elif profile_bn.endswith('.pssm') or profile_bn.endswith('ascii_mtx_file'):
        return 'PSSM'
    else:
        return


def get_mutant_table_columns(mutfile):
    import pandas as pd

    table_extensions = [
        f'.{ext}' for ext, _ in FileExtentions.MutableFileExt.items()
    ]

    if not any(
        [True for ext in table_extensions if mutfile.lower().endswith(ext)]
    ):
        return None

    elif mutfile.lower().endswith('.txt'):
        return None

    elif mutfile.lower().endswith('.csv'):
        mutation_data = pd.read_csv(mutfile)

    elif mutfile.lower().endswith('.tsv'):
        mutation_data = pd.read_fwf(mutfile)

    elif mutfile.lower().endswith('.xlsx') or mutfile.lower().endswith('.xls'):
        mutation_data = pd.read_excel(mutfile)

    return list(mutation_data.columns)

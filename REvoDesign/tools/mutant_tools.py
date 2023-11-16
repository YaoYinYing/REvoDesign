from typing import Iterable
from absl import logging
import re
from REvoDesign.common.Mutant import Mutant
from Bio.Data import IUPACData

from REvoDesign.tools.utils import filepath_does_exists

protein_letters_3to1 = {
    v.upper(): k.upper() for k, v in IUPACData.protein_letters_1to3.items()
}


def extract_mutants_from_mutant_id(
    mutant_string, chain_id=None, sequence=None
):
    '''
    Extract mutant info from an mutant id string. This mutant can be virtual from PyMOL session.

    Parameters:
    mutant_string (str): Underscore-seperated mutant string that contains the mutations and score (if possible).
                        <chain_id><wt_res><resi><mut_res>_...._<score>
    chain_id (str): design chain id.
    sequence (str): Wild-type sequence of design molecule and chain

    Returns:
    tuple:
        [0] - Parsed mutant string (no score)
        [1] - Mutant : Mutant object.
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
            _chain_id = (
                _mut.group(1)
                if chain_id is None or chain_id == ''
                else chain_id
            )
            _position = _mut.group(3)
            _wt_res = _mut.group(2)
            _mut_res = _mut.group(4)

        # reduced description of mutation, <wt_res><pos><mut>, missing <chain_id>
        elif re.match(r'[A-Z]{1}\d+[A-Z]{1}', mut):
            logging.debug(f'reduced description: {mut}')
            if not (mutant_info or chain_id):
                logging.error(
                    f'Error while processing mutant id {mut}: Invalid chain id: {chain_id}'
                )
                continue
            _mut = re.match(r'([A-Z]{1})(\d+)([A-Z]{1})', mut)

            _chain_id = chain_id
            _position = int(_mut.group(2))
            _wt_res = _mut.group(1)
            _mut_res = _mut.group(3)

        # fuzzy description of mutation, <pos><mut>, missing <chain_id> and <wt_res>
        elif re.match(r'\d+[A-Z]{1}', mut):
            logging.debug(f'fuzzy description: {mut}')
            # silent error report while mismatching the score term
            if not (mutant_info or chain_id):
                logging.error(
                    f'Error while processing mutant id {mut}: Invalid chain id: {chain_id}'
                )
                continue
            if not (sequence or mutant_info):
                logging.error(
                    f'Error while processing mutant id {mut}: Invalid sequence: {sequence}'
                )
                continue

            _mut = re.match(r'(\d+)([A-Z]{1})', mut)

            _chain_id = chain_id
            _position = int(_mut.group(1))
            _wt_res = sequence[_position - 1]
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
        return None, None

    # if the mutation has a position of score, we need to extract it.
    mutant_score = extract_mutant_score_from_string(
        mutant_string=mutant_string
    )

    # Instantializing a Mutant obj
    mutant_obj = Mutant(mutant_info, mutant_score)

    logging.debug(mutant_obj)

    # Join the mutants into a single string separated by underscores and instantialized Mutant obj
    return '_'.join(mutants), mutant_obj


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
    mutant_sequence, wt_sequence, chain_id='A'
) -> Mutant:
    '''
    Extract mutant from mutant sequence.

    Parameters:
    mutant_sequence (str): Mutant sequence.
    wt_sequence (str): Wild-type sequence.
    chain_id (str): Chain id

    Returns:
    Mutant: Mutant object
    '''
    if len(mutant_sequence) != len(wt_sequence):
        logging.error(
            f'Lengths of WT and mutant are not equal to each other: {len(wt_sequence)}: {len(mutant_sequence)}'
        )
        return None

    if mutant_sequence == wt_sequence:
        logging.warning(f'WT and mutant sequences are identical.')
        return None

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

    mutant_obj = Mutant(mutant_info=mut_info, mutant_score=0)

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


def expand_range(shortened_str, connector='-', seperator='+'):
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


def extract_mutant_from_pymol_object(pymol_object, sequence=''):
    '''
    Extract mutant info from an existing pymol object.

    Parameters:
    pymol_object (str): object to extract from.
    sequence (str): Wild-type sequence of design molecule and chain

    Returns:
    Mutant : Mutant object.
    '''
    from pymol import cmd

    mutant_info = [
        {
            'chain_id': at.chain,
            'position': int(at.resi),
            'wt_res': sequence[int(at.resi) - 1] if sequence else 'X',
            'mut_res': protein_letters_3to1[at.resn],
        }
        for at in cmd.get_model(f'{pymol_object} and n. CA').atom
    ]
    mutant_obj = Mutant(
        mutant_info=mutant_info,
        mutant_score=extract_mutant_score_from_string(pymol_object),
    )

    return mutant_obj


def read_customized_indice(custom_indices_from_input='') -> str: 
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

        guessed_connector = list(_guessed_connector.keys())[0] if _guessed_connector else '-'
        guessed_seperator = list(_guessed_seperator.keys())[0] if _guessed_seperator else ','

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

'''
This module contains functions for handling mutants.
'''

import json
import os
import re
import time
import warnings
from typing import List, Mapping, Optional, Tuple, Union

import numpy as np
import pandas as pd
from Bio.Data import IUPACData
from pymol import cmd
from RosettaPy.common.mutation import Mutation, RosettaPyProteinSequence

from REvoDesign import ConfigBus, file_extensions, issues
from REvoDesign.common import Mutant, MutantTree
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.sidechain import SidechainSolver
from REvoDesign.tools.customized_widgets import QButtonMatrix, REvoDesignWidget
from REvoDesign.tools.pymol_utils import is_hidden_object

from .utils import cmap_reverser, get_color, timing

logging = ROOT_LOGGER.getChild(__name__)

# Dictionary comprehension to create a mapping from 3-letter amino acid codes to 1-letter codes.
# It utilizes the IUPACData module from Biopython, which contains standard codes for amino acids.
protein_letters_3to1 = {
    v.upper(): k.upper()  # Mapping the 3-letter code (value) to its corresponding 1-letter code (key)
    # Looping through the items in the 1-to-3-letter amino acid dictionary
    for k, v in IUPACData.protein_letters_1to3.items()
}

NOT_ALLOWED_GROUP_ID_PREFIX: tuple = (
    "RDPM",
    "multi_design",
    "cep",
    "invalid_cep",
)


def extract_mutants_from_mutant_id(
    mutant_string: str,
    sequences: Union[Mapping[str, str], RosettaPyProteinSequence],
    wt_before_chain: bool = False
) -> Mutant:
    """
    Extract mutant info from an mutant id string. This mutant can be virtual from PyMOL session.

    Parameters:
    mutant_string (str): Underscore-seperated mutant string that contains the mutations and score (if possible).
                        <chain_id><wt_res><resi><mut_res>_...._<score>
    sequences (dict): Wild-type chain: sequence of design molecule
    wt_before_chain (bool): Some people write WT residue before chain_id. This helps to correct recognizing of this pattern

    Returns:
    tuple:
        Mutant : Mutant object.
    """
    logging.debug(f"Parsing {mutant_string}")
    if isinstance(sequences, Mapping):
        sequences = RosettaPyProteinSequence.from_dict(dict(sequences))

    # Use regular expression to find all mutants in the string
    mutants = re.findall(r"([A-Z]{0,2}\d+[A-Z]{1})", mutant_string)

    mutations = []
    for mut in mutants:
        # full description of mutation, <chain_id><wt_res><pos><mut>
        if re.match(r"[A-Z]{2}\d+[A-Z]{1}", mut):
            logging.debug(f"full description: {mut}")
            _mut = re.match(r"([A-Z]{1})([A-Z]{1})(\d+)([A-Z]{1})", mut)
            if not wt_before_chain:
                _chain_id = _mut.group(1)
                _wt_res = _mut.group(2)
            else:
                _wt_res = _mut.group(1)
                _chain_id = _mut.group(2)

            _position = _mut.group(3)

            _mut_res = _mut.group(4)

        # reduced description of mutation, <wt_res><pos><mut>, missing <chain_id>
        elif re.match(r"[A-Z]{1}\d+[A-Z]{1}", mut):
            logging.debug(f"reduced description: {mut}")

            _mut = re.match(r"([A-Z]{1})(\d+)([A-Z]{1})", mut)

            _chain_id = sequences.all_chain_ids[
                0
            ]  # expected as the first chain.
            _position = int(_mut.group(2))
            _wt_res = _mut.group(1)
            _mut_res = _mut.group(3)

        # fuzzy description of mutation, <pos><mut>, missing <chain_id> and <wt_res>
        elif re.match(r"\d+[A-Z]{1}", mut):
            logging.debug(f"fuzzy description: {mut}")

            _mut = re.match(r"(\d+)([A-Z]{1})", mut)

            _chain_id = sequences.all_chain_ids[
                0
            ]  # expected as the first chain.
            _position = int(_mut.group(1))
            _wt_res = list(sequences.get_sequence_by_chain(_chain_id))[
                _position - 1
            ]
            _mut_res = _mut.group(2)

        else:
            warnings.warn(
                issues.BadDataWarning(
                    f"Error while processing mutant id {mut}. "
                )
            )
            continue

        mutations.append(
            Mutation(
                chain_id=_chain_id,
                position=int(_position),
                wt_res=_wt_res,
                mut_res=_mut_res,
            )
        )

    if not mutations:
        raise issues.InvalidInputError(
            f"No valid mutations found in `{mutant_string}`"
        )

    mutant_obj = Mutant(mutations, sequences)

    # if the mutation has a position of score, we need to extract it.
    mutant_score = extract_mutant_score_from_string(
        mutant_string=mutant_string
    )
    if mutant_score:
        mutant_obj.mutant_score = mutant_score

    logging.debug(mutant_obj)

    # Join the mutants into a single string separated by underscores and instantialized Mutant obj
    return mutant_obj


def extract_mutant_score_from_string(mutant_string: str) -> Optional[float]:
    """
    Extract mutant score from an mutant string

    Parameters:
    mutant_string (str): Underscore-seperated mutant string that contains the mutations and score (if possible).
                        <chain_id><wt_res><resi><mut_res>_...._<score>

    Returns:
    float: Mutant score.
    """
    if re.match(r"[\d+\w]+_[-\d\.e]+", mutant_string):
        matched_mutant_id = re.match(
            r"[\w\d\-]+_(\-?\d+\.?\d*e?\-?\d*)$", mutant_string
        )
        mutant_score = matched_mutant_id.group(1)
        mutant_score = float(mutant_score)
        return mutant_score
    return None


def extract_mutant_from_sequences(
    mutant_sequence: str,
    wt_sequences: RosettaPyProteinSequence,
    chain_id: str = "A",
    fix_missing: bool = False,
) -> Optional[Mutant]:
    """
    Extract mutant from mutant sequence.

    Parameters:
    mutant_sequence (str): Mutant sequence.
    wt_sequence (str): Wild-type sequence.
    chain_id (str): Chain id
    fix_missing (bool): Fix missing residue ('X') in mutant according to the WT sequence.

    Returns:
    Mutant: Mutant object
    """

    wt_sequence = wt_sequences.get_sequence_by_chain(chain_id=chain_id)
    _wt_sequence = wt_sequence.replace("X", "")
    _mutant_sequence = mutant_sequence.replace("X", "")

    if len(_mutant_sequence) != len(_wt_sequence):
        raise issues.InvalidInputError(
            "Lengths of filtered WT and mutant are not equal to each other: "
            f"{len(_wt_sequence)}: {len(_mutant_sequence)}")

    if mutant_sequence == wt_sequence:
        logging.warning("WT and mutant sequences are identical.")
        return

    if "X" in wt_sequence and not fix_missing:
        warnings.warn(
            issues.ResidueMissingWarning(
                'WT has missing residue masked as "X"!'
            )
        )

    if fix_missing:
        _mutant_sequence = ""
        offset = 0
        for i, c in enumerate(wt_sequence):
            if c != "X":
                _mutant_sequence += mutant_sequence[i + offset]
            else:
                _mutant_sequence += "X"
                offset -= 1

        if len(_mutant_sequence) != len(wt_sequence):
            raise issues.NoInputError(
                "Lengths of WT and fixed mutant are not equal to each other: "
                f"{len(wt_sequence)}: {len(_mutant_sequence)}")

        mutant_sequence = _mutant_sequence

    mut_info = [
        Mutation(
            chain_id=chain_id,
            position=i + 1,
            wt_res=res,
            mut_res=mutant_sequence[i],
        )
        for i, res in enumerate(wt_sequence)
        if res != mutant_sequence[i]
    ]
    logging.debug(mut_info)

    mutant_obj = Mutant(mutations=mut_info, wt_protein_sequence=wt_sequences)
    mutant_obj.mutant_score = 0

    return mutant_obj


def shorter_range(
    input_list: Union[List[int], Tuple[int]],
    connector: str = "-",
    seperator: str = "+",
) -> str:
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
        raise issues.NoInputError("Input list is empty.")

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


def expand_range(
    shortened_str: str, connector: str = "-", seperator: str = "+"
) -> List[int]:
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
        if "-" in rng:
            try:
                start, end = map(int, rng.split(connector))
                expanded_list.extend(range(start, end + 1))
            except ValueError as e:
                raise issues.InvalidInputError(f"Error parsing range '{rng}': {e}\n"
                                               f"Did you mean {rng.strip(connector)} ?") from e
        else:
            expanded_list.append(int(rng))

    return expanded_list


def extract_mutant_from_pymol_object(
    pymol_object: str, sequences: RosettaPyProteinSequence
) -> Mutant:
    """
    Extract mutant info from an existing pymol object.

    Parameters:
    pymol_object (str): object to extract from.
    sequences (dict[str]): Wild-type sequence of design molecule and chain

    Returns:
    Mutant : Mutant object.
    """

    mutant_info = []

    for _, chain in enumerate(sequences.chains):
        sequence = chain.sequence
        for at in cmd.get_model(
            f"{pymol_object} and c. {chain.chain_id} and n. CA"
        ).atom:
            try:
                mutant_info.append(
                    Mutation(
                        chain_id=at.chain,
                        position=int(at.resi),
                        wt_res=sequence[int(at.resi) - 1] if sequence else "X",
                        mut_res=protein_letters_3to1[at.resn],
                    )
                )

            except IndexError:
                warnings.warn(
                    issues.BadDataWarning(
                        f"{at.resn} at {at.resi} (chain {chain.chain_id}) is out of range of sequence length."
                    )
                )
                continue

    mutant_obj = Mutant(mutations=mutant_info, wt_protein_sequence=sequences)
    mutant_score = extract_mutant_score_from_string(pymol_object)
    if mutant_score is not None:
        mutant_obj.mutant_score = mutant_score

    return mutant_obj


def read_customized_indice(custom_indices_from_input="") -> str:
    """
    Reads and processes customized indices based on the provided input.

    Args:
    - custom_indices_from_input (str): String containing customized indices.

    Returns:
    - str: Processed customized indices string.
    """

    if not custom_indices_from_input:
        return ""

    if os.path.isfile(custom_indices_from_input):
        with open(custom_indices_from_input) as f:
            custom_indices_str = f.read().strip()
        return custom_indices_str

    # treat input as a digit
    if custom_indices_from_input.isdigit():
        return custom_indices_from_input

    # direct input of customized indices: 1-20;78-99
    if any(custom_indices_from_input.count(x) >= 1 for x in "-:,;+ "):
        from REvoDesign.tools.utils import count_and_sort_characters

        _guessed_connector = count_and_sort_characters(
            input_string=custom_indices_from_input, characters="-:"
        )

        _guessed_seperator = count_and_sort_characters(
            input_string=custom_indices_from_input, characters=",;+ "
        )

        guessed_connector = (
            list(_guessed_connector.keys())[0] if _guessed_connector else "-"
        )
        guessed_seperator = (
            list(_guessed_seperator.keys())[0] if _guessed_seperator else ","
        )

        custom_indices_str = expand_range(
            shortened_str=custom_indices_from_input,
            connector=guessed_connector,
            seperator=guessed_seperator,
        )

        return ",".join([str(x) for x in custom_indices_str])

    raise issues.InvalidInputError(
        f"Failed in parsing customized indice file/string: {custom_indices_from_input}"
    )


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
    positions = data["indices"]
    mutations = data["mutations"]
    result = []
    for position in positions:
        if str(position) in mutations:
            mutation = mutations[str(position)]
            wt_residue = mutation["wt"]
            wt_profile_score = mutation["wt_profile_score"]
            candidates = mutation["candidates"]
            result.append((position, wt_residue, wt_profile_score, candidates))
    return result


def read_profile_design_mutations(filename):
    data = json.load(open(filename))
    return process_mutations(data)


def existed_mutant_tree(
    sequences: Union[Mapping[str, str], RosettaPyProteinSequence],
    enabled_only: Union[int, bool] = 1,
) -> MutantTree:
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
    if isinstance(sequences, Mapping):
        sequences = RosettaPyProteinSequence.from_dict(dict(sequences))

    group_ids: list[str] = cmd.get_names(
        type="group_objects", enabled_only=enabled_only
    )

    # if the group id starts with any of the disallowed prefixes, filter it out.
    filtered_group_ids = filter(
        lambda group_id: not any(
            group_id.startswith(p) for p in NOT_ALLOWED_GROUP_ID_PREFIX
        ),
        group_ids,
    )

    _mutant_tree = {
        group_id: {
            mutant_id: extract_mutant_from_pymol_object(
                pymol_object=mutant_id, sequences=sequences
            )
            for mutant_id in cmd.get_object_list(f"({group_id})")
            if not enabled_only or not is_hidden_object(selection=mutant_id)
        }
        for group_id in filtered_group_ids
    }
    return MutantTree(_mutant_tree)


def quick_mutagenesis(mutant_tree: MutantTree) -> None:
    """run quick mutagenesis on a given mutation tree.
        Everything else is read from local config bus.

    Args:
        mutant_tree (MutantTree): input mutant tree object.
    """
    from REvoDesign.common.mutant_visualise import MutantVisualizer

    from .pymol_utils import make_temperal_input_pdb
    from .utils import timing

    bus: ConfigBus = ConfigBus()
    sidechain_solver: SidechainSolver = SidechainSolver().refresh()

    molecule = bus.get_value("ui.header_panel.input.molecule")
    chain_id = bus.get_value("ui.header_panel.input.chain_id")
    designable_sequences: RosettaPyProteinSequence = bus.get_value(
        "designable_sequences", RosettaPyProteinSequence.from_dict)

    nproc = bus.get_value("ui.header_panel.nproc")

    if mutant_tree.empty:
        warnings.warn(issues.NoResultsWarning("Mutant tree is empty!"))
        return

    score_list = mutant_tree.all_mutant_scores

    with timing("Quick Mutageneses"):
        input_pdb = make_temperal_input_pdb(molecule=molecule, reload=False)
        visualizer = MutantVisualizer(molecule=molecule, chain_id=chain_id)
        cfg = bus.cfg

        visualizer.designable_sequences = designable_sequences

        visualizer.nproc = nproc
        visualizer.input_session = input_pdb
        # visualizer.sequence = sequence

        visualizer.full = cfg.ui.visualize.full_pdb
        visualizer.cmap = cmap_reverser(
            bus.get_value('ui.header_panel.cmap.default'),
            bus.get_value('ui.header_panel.cmap.reverse_score')
        )
        visualizer.mutate_runner = sidechain_solver.mutate_runner

        visualizer.min_score = min(score_list)
        visualizer.max_score = max(score_list)

        # run mutate

        mutant_tree = mutant_tree.run_mutate_parallel(
            mutate_runner=sidechain_solver.mutate_runner,
            nproc=visualizer.nproc,
        )

        for group_id in mutant_tree.all_mutant_branch_ids:
            visualizer.group_name = group_id

            visualizer.save_session = os.path.join(
                os.path.dirname(input_pdb),
                f'group.{group_id}.{os.path.basename(input_pdb).replace(".pdb", ".pze")}',
            )

            visualizer.mutant_tree = MutantTree(
                {group_id: mutant_tree.get_a_branch(branch_id=group_id)}
            )
            for m in visualizer.mutant_tree.all_mutant_objects:
                color = get_color(
                    visualizer.cmap,
                    m.mutant_score,
                    visualizer.min_score,
                    visualizer.max_score,
                )
                logging.info(f"Visualizing {m.short_mutant_id} ({m.raw_mutant_id}) : {color} with "
                             f"{visualizer.mutate_runner.__class__.__name__}")

                visualizer.create_mutagenesis_objects(
                    mutant_obj=m, color=color, in_place=True
                )
    return


def save_mutant_choices(output_mut_txt_fn: str, mutant_tree: MutantTree):
    if not mutant_tree:
        raise issues.NoInputError("No Mutant tree is given!")

    if mutant_tree.empty:
        warnings.warn(
            issues.NoResultsWarning("mutant tree is empty. save nothing.")
        )
        return

    mutants_to_save = mutant_tree.all_mutant_ids
    logging.info(f"saving: {mutants_to_save}")

    # TODO mutant_choices function
    output_mut_txt_dir = os.path.dirname(output_mut_txt_fn)
    if not os.path.exists(output_mut_txt_dir):
        logging.warning(
            f"Parent dir for mutant table does NOT exist! {output_mut_txt_dir}"
        )
        # os.makedirs(output_mut_txt_dir,exist_ok=True)
        logging.warning("Skip saving mutant file.")
        return

    if os.path.exists(output_mut_txt_fn):
        warnings.warn(
            issues.OverridesWarning(
                f"Mutant table exists and will be overriden! {output_mut_txt_fn}"
            )
        )
        write_input_mutant_table(
            output_mut_txt_fn,
            [mt.raw_mutant_id for mt in mutant_tree.all_mutant_objects],
        )

    else:
        logging.info(f"Mutant table is created at {output_mut_txt_fn}")
        write_input_mutant_table(
            output_mut_txt_fn,
            [mt.raw_mutant_id for mt in mutant_tree.all_mutant_objects],
        )

    output_mut_txt_dir_ckp = os.path.join(output_mut_txt_dir, "./checkpoints/")
    os.makedirs(output_mut_txt_dir_ckp, exist_ok=True)

    _time_stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    output_mut_txt_bn_ckp = f'ckp_{_time_stamp}.{os.path.basename(output_mut_txt_fn)}'
    output_mut_txt_ckp = os.path.join(
        output_mut_txt_dir_ckp, output_mut_txt_bn_ckp
    )

    logging.info(f"Saving checkpoint: {output_mut_txt_ckp}")
    write_input_mutant_table(
        output_mut_txt_ckp, [mt for mt in mutants_to_save]
    )


def write_input_mutant_table(output_mut_txt_fn, mutant_list):
    with open(output_mut_txt_fn, "w") as f:
        f.write("\n".join(mutant_list) if mutant_list else "")


def determine_profile_type(profile_fp: str) -> str:
    profile_type_mapping = {
        ".csv": "CSV",
        ".txt": "TSV",
        ".pssm": "PSSM",
        "ascii_mtx_file": "PSSM",
    }
    if not profile_fp:
        raise issues.NoInputError(f"Invalid {profile_fp=}")

    for ext, pt in profile_type_mapping.items():
        if profile_fp.endswith(ext):
            return pt

    return ""


def get_mutant_table_columns(mutfile: str):
    filename_bn = os.path.basename(mutfile)
    filename_ext = filename_bn.split(".")[-1]

    if not file_extensions.Mutable.match(filename_ext):
        raise issues.InvalidInputError(
            f"Invalid file extention {mutfile=}. \n"
            f"All available: {file_extensions.Mutable.list_dot_ext=}"
        )

    if mutfile.lower().endswith(".txt"):
        return None

    if mutfile.lower().endswith(".csv"):
        mutation_data = pd.read_csv(mutfile)

    elif mutfile.lower().endswith(".tsv"):
        mutation_data = pd.read_fwf(mutfile)

    elif mutfile.lower().endswith((".xlsx",".xls")):
        mutation_data = pd.read_excel(mutfile)
    else:
        raise issues.UnsupportedDataTypeError(f'Unsupported file type for mutant table: {filename_ext}')

    return list(mutation_data.columns)


def pick_design_from_profile(
        profile: str,
        profile_type: str,
        prefer_lower_score: bool = False,
        keep_missing: bool = True,
        residue_range: str = '',
        view_highlight: str = 'orient',
        view_highlight_nbr: int = 6
):
    from RosettaPy.common.mutation import Mutation

    from REvoDesign.Qt import QtCore, QtWidgets

    from ..bootstrap.set_config import ConfigConverter
    from ..common.mutant import Mutant
    from ..common.mutant_visualise import MutantVisualizer
    from ..phylogenetics.revo_designer import REvoDesigner
    from ..sidechain.sidechain_solver import SidechainSolver
    from ..tools.utils import (cmap_reverser, get_color,
                               run_worker_thread_with_progress)

    bus = ConfigBus()
    molecule = bus.get_value('ui.header_panel.input.molecule', str, reject_none=True)
    chain_id = bus.get_value('ui.header_panel.input.chain_id', str, reject_none=True)

    cmap = cmap_reverser(
        cmap=bus.get_value("ui.header_panel.cmap.default"),
        reverse=prefer_lower_score,
    )

    if sequences := bus.get_value('designable_sequences', ConfigConverter.convert, reject_none=True):
        designable_sequences = RosettaPyProteinSequence.from_dict(sequences)
    else:
        raise issues.NoInputError("Failed to get sequence from Config, Session or PDB file!")

    print(designable_sequences)
    sequence = designable_sequences.get_sequence_by_chain(chain_id)
    if not keep_missing:
        sequence = sequence.replace("X", "")
    print(sequence)

    # Get residue range, if none, use full length
    custom_indices_str: str = residue_range if residue_range else shorter_range(
        [i for i, aa in enumerate(sequence) if aa != 'X'])

    custom_indices_str = read_customized_indice(custom_indices_from_input=custom_indices_str.strip())
    logging.debug(f"Read:  {custom_indices_str=}")
    custom_indices_str = ','.join([str(int(resi)) for resi in custom_indices_str.split(',')])
    logging.debug(f"Fixed: {custom_indices_str=}")

    # Parse profile with MutantVisualizer's profile reading
    profile_parser = MutantVisualizer(molecule=molecule, chain_id=chain_id)
    profile_parser.designable_sequences = designable_sequences
    profile_parser.sequence = sequence

    if not os.path.isfile(profile):
        raise issues.NoInputError(f"Not Found: {profile=}")

    df = profile_parser.parse_profile(profile_fp=profile, profile_format=profile_type)

    first_idx: Union[str, int] = df.columns.tolist()[0]
    if first_idx in (0, "0"):
        logging.debug("Input profile is zero-indexed, convert to 1-indexed")
        df.columns = df.columns.map(lambda x: int(x) + 1)
    else:
        df.columns = df.columns.map(int)

    if df is None or df.empty:
        raise issues.NoResultsError(
            f"Error occurs while parsing profile {profile} with format {profile_type}"
        )

    profile_alphabet = "".join(df.T.columns.to_list())
    logging.info(df.head())

    # Call REvoDesigner to setup and plot
    designer = REvoDesigner(profile)
    designer.molecule = molecule
    designer.chain_id = chain_id
    designer.sequence = sequence
    designer.cmap = cmap
    designer.profile_alphabet = profile_alphabet
    designer.pwd = os.getcwd()
    designer.design_case = 'default'
    designer.designable_sequences = designable_sequences

    designer.mutate_runner = SidechainSolver().refresh().mutate_runner
    designer.reject_aa = ''

    max_abs = np.max((np.abs(df.values.min()), df.values.max()))

    cutoff = [
        (bus.get_value("ui.mutate.min_score", float)),
        (bus.get_value("ui.mutate.max_score", float)),
    ]

    try:
        designer.plot_custom_indices_segments(
            df_ori=df,
            custom_indices_str=custom_indices_str,
            cutoff=cutoff,
            preferred_substitutions='',
        )

    except KeyError as e:
        raise issues.InvalidInputError(
            f'A Key Error occurred due to invalid residue range({residue_range} --> {custom_indices_str}): \n{e}'
        ) from e

    custom_indices = expand_range(shortened_str=custom_indices_str, seperator=",", connector="-")
    df_button_matrix = df.loc[:, custom_indices]

    visualizer = MutantVisualizer(molecule=molecule, chain_id=chain_id)
    visualizer.designable_sequences = designable_sequences
    visualizer.cmap = cmap
    visualizer.min_score = -max_abs
    visualizer.max_score = max_abs

    designed_tree = existed_mutant_tree(sequences=designable_sequences, enabled_only=0)

    def mutate_with_gridbuttons(row, col):
        nonlocal button_matrix
        nonlocal designed_tree

        resn: str = button_matrix.alphabet_row[row]
        # one-indexed, int
        resi: int = int(button_matrix.alphabet_col[col])
        wt_res = sequence[resi - 1]

        wt_score = df.loc[wt_res, resi]
        mut_score = df.loc[resn, resi]

        with timing(f"Mutating picked {chain_id}{wt_res}{resi}{resn}"):

            group_id = f'mt_manual_{wt_res}{resi}_{wt_score}'
            mutant = Mutant([Mutation(chain_id=chain_id, position=resi, wt_res=wt_res, mut_res=resn)],
                            wt_protein_sequence=designable_sequences)
            mutant.mutant_score = mut_score
            visualizer.group_name = group_id

            # build the sidechain if not existed
            if designed_tree.has(mutant.full_mutant_id):
                logging.info(f'{mutant} already exists in the tree')
            else:
                sidechain_solver = run_worker_thread_with_progress(
                    SidechainSolver().refresh,
                    progress_bar=bus.ui.progressBar
                )
                if not sidechain_solver:
                    raise issues.InternalError("Sidechain solver failed")

                visualizer.mutate_runner = sidechain_solver.mutate_runner
                score = mutant.mutant_score

                color = get_color(cmap, score, -max_abs, max_abs)
                print(f"Visualizing {mutant.short_mutant_id} ({mutant.raw_mutant_id}) : {color} "
                      f"with {visualizer.mutate_runner.__class__.__name__}")
                run_worker_thread_with_progress(
                    visualizer.create_mutagenesis_objects,
                    mutant_obj=mutant,
                    color=color,
                    in_place=True,
                    progress_bar=bus.ui.progressBar
                )

                designed_tree.add_mutant_to_branch(branch=group_id, mutant=mutant.full_mutant_id, mutant_obj=mutant)

        highlight_method_name = view_highlight
        if highlight_method_name == 'center':
            highlight_method = cmd.center
        elif highlight_method_name == 'zoom':
            highlight_method = cmd.zoom
        elif highlight_method_name == 'orient':
            highlight_method = cmd.orient
        else:
            return

        if view_highlight_nbr > 0:
            highlight_method(f'byres {mutant.full_mutant_id} around {view_highlight_nbr}', animate=1)
        else:
            highlight_method(mutant.full_mutant_id, animate=1)

    # Prepare the data for the button matrix

    print(df_button_matrix.head())
    pix_per_block = 25

    button_matrix = QButtonMatrix(
        df_matrix=df_button_matrix,
        sequence=sequence,
        cmap=cmap,
        flip_cmap=True,
        button_size=12
    )
    button_matrix.setObjectName('ProfileDesignButtonMatrix')
    button_matrix.label_size = [18, 9]
    button_matrix.sequence = sequence
    button_matrix.init_ui()

    button_matrix.active_func = mutate_with_gridbuttons

    # Create a new dialog window for the button matrix
    window = REvoDesignWidget("ProfileDesignButtonMatrixWindow", allow_repeat=True)  # This creates a standalone window.

    window.setWindowTitle(f"Mutant Profile Matrix: {profile_type} ({profile})")

    screen_width = QtWidgets.QApplication.primaryScreen().availableGeometry().width()  # type: ignore
    screen_height = QtWidgets.QApplication.primaryScreen().availableGeometry().height()  # type: ignore

    num_cols = button_matrix.df_matrix.shape[1]  # Assuming the matrix's DataFrame determines the columns

    # Set window size constraints
    # - Adjust height and width to fit available screen size dynamically
    fixed_height = pix_per_block * 21 + 110  # 110 for the banner and spacing
    calculated_width = pix_per_block * (num_cols + 1)
    max_width = min(calculated_width, screen_width - 20)

    # Adjust height and width dynamically to ensure no scrollbars are necessary
    dynamic_width = min(max_width, screen_width)
    dynamic_height = min(fixed_height, screen_height)
    window.setMinimumSize(dynamic_width, dynamic_height)
    window.setMaximumSize(dynamic_width, dynamic_height)
    window.setToolTip(
        f'''Click on a button to mutate the corresponding residue.

Design with Profile:
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-=-=-
Profile: {profile})
Profile Type: {profile_type}
Residue Range: {residue_range}
Prefer Lower Score: {prefer_lower_score}
Keep Missing Residues: {keep_missing}
View Highlight: {view_highlight}
View Highlight Nbr: {view_highlight_nbr}
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-=-=-'''
    )

    # Add a scroll area to the window
    scroll_area = QtWidgets.QScrollArea()
    scroll_area.setWidget(button_matrix)
    scroll_area.setWidgetResizable(True)
    scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)  # Disable vertical scrollbar

    # Remove extra padding or margins to make buttons compact
    button_matrix.setContentsMargins(0, 0, 0, 0)

    # Adjust button size policy for a compact layout
    for button in button_matrix.findChildren(QtWidgets.QPushButton):
        button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        button.setFixedSize(pix_per_block, pix_per_block)

    # Create a layout with a persistent column label row
    main_layout = QtWidgets.QVBoxLayout()

    # Add a label row for column headers
    header_widget = QtWidgets.QWidget()
    header_layout = QtWidgets.QHBoxLayout()
    header_widget.setLayout(header_layout)

    banner_label = QtWidgets.QLabel(
        f"Design with Profiles: {shorter_range(custom_indices)}"
    )
    banner_label.setWordWrap(True)
    banner_label.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)  # type: ignore
    banner_label.setStyleSheet(
        """
        font-size: 14px;
        font-weight: bold;
        color: #333;
        padding: 10px;
        background-color: #f9f9f9;
        border: 1px solid #ccc;
        border-radius: 5px;
        """
    )
    header_layout.addWidget(banner_label)

    main_layout.addWidget(header_widget)
    main_layout.addWidget(scroll_area)

    # Set layout for the main window
    window.setLayout(main_layout)

    # Center the window on the screen
    geometry = window.frameGeometry()
    geometry.moveCenter(QtWidgets.QApplication.primaryScreen().availableGeometry().center())  # type: ignore
    window.move(geometry.topLeft())

    # Show the window
    window.show()

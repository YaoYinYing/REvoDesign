'''
Shortcut functions of results exporting
'''


import os
from typing import List, Mapping, Optional, Union

import Bio
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from pymol import cmd

from REvoDesign import ROOT_LOGGER, issues
from REvoDesign.basic import ThirdPartyModuleAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.pymol_utils import get_all_groups
from REvoDesign.tools.utils import get_cited, require_installed

logging = ROOT_LOGGER.getChild(__name__)


def shortcut_dump_sidechains(
    sele: Union[str, List[str]],
    enabled_only: bool = False,
    save_dir: str = "png/sidechain_dump/",
    height: int = 1280,
    width: int = 1280,
    dpi: int = 150,
    ray: bool = True,
    hide_mesh: bool = True,
    neighborhood: int = 3,
    reorient: bool = True,
    recenter: bool = False,
):
    """
    Dumps sidechain images of selected group to a directory.
    Parameters:
      sele (str|List[str]): Selection string or list of strings to choose the models.
      enabled_only (bool, optional): If True, only dumps enabled models. Defaults to False.
      save_dir (str, optional): Directory path to save the images. Defaults to 'png/sidechain_dump/'.
      height (int, optional): Height of the image in pixels. Defaults to 1280.
      width (int, optional): Width of the image in pixels. Defaults to 1280.
      dpi (int, optional): DPI of the image. Defaults to 150.
      ray (bool, optional): If True, uses ray tracing. Defaults to True.
      hide_mesh (bool, optional): If True, hides the mesh. Defaults to True.
      neighborhood (int, optional): Zoom with neighborhood. Defaults to 3.
      reorient (bool, optional): If True, re-orients the residue. Defaults to True to prevent automatic orientation.
        Useful when user wants to dump the residue they just focused on.
      recenter (bool, optional): If True, re-centers the resiude. Defaults to False.
    Returns:
      None
    """

    os.makedirs(save_dir, exist_ok=True)

    if isinstance(sele, str):
        sele = [sele]

    if hide_mesh:
        cmd.hide("mesh")

    all_groups = get_all_groups(enabled_only=enabled_only)

    # disable all groups
    cmd.disable(' or '.join(all_groups))
    cmd.refresh()

    for sel in sele:
        # ensure the current group selection is enabled
        cmd.enable(sel)

        # get all model names of selected group
        all_models = cmd.get_names("objects", int(enabled_only), sel)
        print(f'Selected group: {sel}: {all_models}')

        cmd.disable(' or '.join(all_models))

        # orient to get pose in the right orientation
        if reorient and neighborhood and neighborhood > 0:
            cmd.orient(f'{sel} or byres {sel} around {neighborhood}')

        for m in all_models:
            cmd.refresh()
            print(f"Dumping PNG for {m} ...")
            cmd.enable(m)
            cmd.show("sticks", m)
            if not hide_mesh:
                cmd.show("mesh", m)
            if recenter:
                cmd.center(f"{m}")
            p = os.path.join(save_dir, f"{m}.png")
            cmd.png(p, height, width, dpi, int(ray))
            cmd.disable(m)

        cmd.disable(sel)


def shortcut_dump_fasta_from_struct(
        format: str = "fasta",
        chain_ids: list[str] = [],
        output_dir: str = 'dumped_sequences',
        drop_missing_residue: bool = False,
        suffix: str = '',
):
    """
    Runs the dump_fasta_from_struct function with parameters collected from the dialog.
    Args:
        format (str): Format of the output file. Defaults to "fasta".
        chain_ids (list[str]): List of chain IDs to dump. Defaults to [].
        output_dir (str): Directory path to save the output file. Defaults to 'dumped_sequences'.
        drop_missing_residue (bool): Whether to drop missing residues. Defaults to False.
        suffix (str): Suffix to add to the output file name. Defaults to ''.
    """

    bus = ConfigBus()
    molecule = bus.get_value('ui.header_panel.input.molecule', str, reject_none=True)
    if not chain_ids:
        logging.warning("No chain selected. Dumping the chain picked on UI.")
        chain_ids = [bus.get_value('ui.header_panel.input.chain_id', str, reject_none=True)]
    designable_sequences: Optional[Mapping] = bus.get_value("designable_sequences", dict, reject_none=True)

    os.makedirs(output_dir, exist_ok=True)
    if suffix:
        suffix = f"_{suffix}"
    output_path = os.path.join(output_dir, f"{molecule}_{''.join(chain_ids)}{suffix}.{format}")
    all_seq_records = []
    for chain_id in chain_ids:
        sequence: Optional[str] = designable_sequences.get(chain_id)
        if sequence is None:
            raise issues.NoResultsError(f"No designable sequence found for chain {chain_id}")
        if drop_missing_residue:
            sequence = sequence.replace('X', '')
        logging.debug(
            f"Molecule: {molecule}\nchain_id: {chain_id}\nsequence: {sequence}"
        )

        all_seq_records.append(
            SeqRecord(
                Seq(sequence),
                id=f"{molecule}_{chain_id}", description=f"{suffix.lstrip('_')}"))

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            SeqIO.write(all_seq_records, f, format)
    except Bio.StreamModeError as e:
        logging.warning(f"Error occurs while dumping sequence: {e} Retry with binary mode.")
        with open(output_path, 'wb') as f:
            SeqIO.write(all_seq_records, f, format)  # type: ignore
    except ValueError as e:
        os.remove(output_path)
        logging.error(f"Error occurs while dumping sequence: {e} Clean up the output file.")
        raise issues.InternalError(f"Error occurs while dumping sequence: {e}.") from e

    logging.info(f"Sequence dumped to {output_path}")


class MolPub(ThirdPartyModuleAbstract):
    name: str = "molpub"
    installed: bool = is_package_installed('molpub')

    def __init__(self):
        super().__init__()

    @get_cited
    def run(self):
        from molpub.windows import (EntryWindow, SelectWindow,
                                    StatisticalWindow, StructureImage1,
                                    StructureImage2, StructureImage3,
                                    StructureImage4)

        entry_window = EntryWindow()
        select_window = SelectWindow()
        statistical_window = StatisticalWindow()
        structure_window_1 = StructureImage1()
        structure_window_2 = StructureImage2()
        structure_window_3 = StructureImage3()
        structure_window_4 = StructureImage4()

        entry_window.show()

        # noinspection PyUnresolvedReferences
        entry_window.implement_combo_box.activated.connect(lambda: entry_window.check_surface(select_window))

        # noinspection PyUnresolvedReferences
        select_window.structure_image_button.clicked.connect(structure_window_1.show)
        # noinspection PyUnresolvedReferences
        select_window.structure_image_button.clicked.connect(select_window.hide)
        # noinspection PyUnresolvedReferences
        select_window.statistical_content_button.clicked.connect(statistical_window.show)
        # noinspection PyUnresolvedReferences
        select_window.statistical_content_button.clicked.connect(select_window.hide)
        # noinspection PyUnresolvedReferences
        select_window.back_button.clicked.connect(select_window.hide)
        # noinspection PyUnresolvedReferences
        select_window.back_button.clicked.connect(entry_window.show)

        # noinspection PyUnresolvedReferences
        statistical_window.back_button.clicked.connect(statistical_window.hide)
        # noinspection PyUnresolvedReferences
        statistical_window.back_button.clicked.connect(select_window.show)
        # noinspection PyUnresolvedReferences
        statistical_window.back_button.clicked.connect(statistical_window.window_clear)
        # noinspection PyUnresolvedReferences
        statistical_window.next_button.clicked.connect(entry_window.show)
        # noinspection PyUnresolvedReferences
        statistical_window.next_button.clicked.connect(statistical_window.hide)
        # noinspection PyUnresolvedReferences
        statistical_window.next_button.clicked.connect(
            lambda: statistical_window.save_image(entry_window.implement_combo_box.currentText(),
                                                  entry_window.targets_combo_box.currentText()))
        # noinspection PyUnresolvedReferences
        statistical_window.next_button.clicked.connect(entry_window.image_set)
        # noinspection PyUnresolvedReferences
        statistical_window.next_button.clicked.connect(statistical_window.window_clear)

        # noinspection PyUnresolvedReferences
        structure_window_1.back_button.clicked.connect(structure_window_1.hide)
        # noinspection PyUnresolvedReferences
        structure_window_1.back_button.clicked.connect(select_window.show)
        # noinspection PyUnresolvedReferences
        structure_window_1.back_button.clicked.connect(structure_window_1.window_clear)
        # noinspection PyUnresolvedReferences
        structure_window_1.next_button.clicked.connect(structure_window_2.show)
        # noinspection PyUnresolvedReferences
        structure_window_1.next_button.clicked.connect(structure_window_1.hide)
        # noinspection PyUnresolvedReferences
        structure_window_1.next_button.clicked.connect(structure_window_2.start_image)

        # noinspection PyUnresolvedReferences
        structure_window_2.back_button.clicked.connect(structure_window_2.hide)
        # noinspection PyUnresolvedReferences
        structure_window_2.back_button.clicked.connect(structure_window_1.show)
        # noinspection PyUnresolvedReferences
        structure_window_2.back_button.clicked.connect(structure_window_2.window_initialization)
        # noinspection PyUnresolvedReferences
        structure_window_2.next_button.clicked.connect(structure_window_3.show)
        # noinspection PyUnresolvedReferences
        structure_window_2.next_button.clicked.connect(structure_window_2.hide)
        # noinspection PyUnresolvedReferences
        structure_window_2.next_button.clicked.connect(structure_window_3.start_image)

        # noinspection PyUnresolvedReferences
        structure_window_3.back_button.clicked.connect(structure_window_3.hide)
        # noinspection PyUnresolvedReferences
        structure_window_3.back_button.clicked.connect(structure_window_2.show)
        # noinspection PyUnresolvedReferences
        structure_window_3.back_button.clicked.connect(structure_window_3.window_initialization)
        # noinspection PyUnresolvedReferences
        structure_window_3.next_button.clicked.connect(structure_window_4.show)
        # noinspection PyUnresolvedReferences
        structure_window_3.next_button.clicked.connect(structure_window_3.hide)
        # noinspection PyUnresolvedReferences
        structure_window_3.next_button.clicked.connect(structure_window_4.start_image)

        # noinspection PyUnresolvedReferences
        structure_window_4.back_button.clicked.connect(structure_window_4.hide)
        # noinspection PyUnresolvedReferences
        structure_window_4.back_button.clicked.connect(structure_window_3.show)
        # noinspection PyUnresolvedReferences
        structure_window_4.back_button.clicked.connect(structure_window_4.window_initialization)
        # noinspection PyUnresolvedReferences
        structure_window_4.next_button.clicked.connect(entry_window.show)
        # noinspection PyUnresolvedReferences
        structure_window_4.next_button.clicked.connect(structure_window_4.hide)
        # noinspection PyUnresolvedReferences
        structure_window_4.next_button.clicked.connect(
            lambda: structure_window_4.save_image(entry_window.implement_combo_box.currentText(),
                                                  entry_window.calculate_image_ratio()))
        # noinspection PyUnresolvedReferences
        structure_window_4.next_button.clicked.connect(entry_window.image_set)
        # noinspection PyUnresolvedReferences
        structure_window_4.next_button.clicked.connect(structure_window_1.window_clear)
        # noinspection PyUnresolvedReferences
        structure_window_4.next_button.clicked.connect(structure_window_2.window_clear)
        # noinspection PyUnresolvedReferences
        structure_window_4.next_button.clicked.connect(structure_window_3.window_clear)
        # noinspection PyUnresolvedReferences
        structure_window_4.next_button.clicked.connect(structure_window_4.window_clear)

    __bibtex__ = {'PyMOL-PUB': """@article{chen2024rapid,
    author = {Chen, Yuting and Zhang, Haoling and Wang, Wen and Shen, Yue and Ping, Zhi},
    title = {Rapid generation of high-quality structure figures for publication with PyMOL-PUB},
    journal = {Bioinformatics},
    volume = {40},
    number = {3},
    pages = {btae139},
    year = {2024},
    month = {03},
    issn = {1367-4811},
    doi = {10.1093/bioinformatics/btae139},
    url = {https://doi.org/10.1093/bioinformatics/btae139},
}"""}


def shortcut_molpub():
    molpub = MolPub()

    molpub.run()

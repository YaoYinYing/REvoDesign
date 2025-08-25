import os
from typing import List, Mapping, Optional, Union
import Bio
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from pymol import cmd
from REvoDesign import ROOT_LOGGER, issues
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.tools.pymol_utils import get_all_groups
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
    os.makedirs(save_dir, exist_ok=True)
    if isinstance(sele, str):
        sele = [sele]
    if hide_mesh:
        cmd.hide("mesh")
    all_groups = get_all_groups(enabled_only=enabled_only)
    cmd.disable(' or '.join(all_groups))
    cmd.refresh()
    for sel in sele:
        cmd.enable(sel)
        all_models = cmd.get_names("objects", int(enabled_only), sel)
        print(f'Selected group: {sel}: {all_models}')
        cmd.disable(' or '.join(all_models))
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
            SeqIO.write(all_seq_records, f, format)  
    except ValueError as e:
        os.remove(output_path)
        logging.error(f"Error occurs while dumping sequence: {e} Clean up the output file.")
        raise issues.InternalError(f"Error occurs while dumping sequence: {e}.") from e
    logging.info(f"Sequence dumped to {output_path}")
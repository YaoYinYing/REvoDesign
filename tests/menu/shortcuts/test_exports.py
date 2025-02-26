import os

import pytest

from REvoDesign.shortcuts.tools.exports import (
    shortcut_dump_fasta_from_struct, shortcut_dump_sidechains)
from tests.conftest import KeyData, TestWorker


@pytest.mark.serial
@pytest.mark.parametrize(
    "format,chain_id,drop_missing_residue,suffix, expected_seq_num",
    [
        ['fasta', ['B', 'C'], False, '', 2],
        ['fasta-2line', ['B', 'C', 'D'], False, 'test_suffix', 3],
        ['fasta', ['B', 'C', 'D', 'E', 'F'], True, 'anther-suffix', 5],
        ['fasta', ['D', 'F', 'i'], True, '', 3],

    ]
)
def test_shortcut_dump_fasta_from_struct(
        format,
        chain_id,
        drop_missing_residue,
        suffix,
        expected_seq_num,
        test_worker: TestWorker):
    test_worker.load_session_and_check(pdb_code='9gbw', from_rcsb=True)
    os.makedirs('dumped_sequences', exist_ok=True)
    shortcut_dump_fasta_from_struct(
        format=format,
        chain_ids=chain_id,
        output_dir='dumped_sequences',
        drop_missing_residue=drop_missing_residue,
        suffix=suffix,
    )
    expected_fasta_file = os.path.join('dumped_sequences',
                                       f'9gbw_{"".join(chain_id)}{f"_{suffix}" if suffix else ""}.{format}')
    assert os.path.isfile(expected_fasta_file), f'{expected_fasta_file} not found'

    fasta_file_contents = open(expected_fasta_file).readlines()
    assert len([l for l in fasta_file_contents if l.startswith(
        '>')]) == expected_seq_num, f'Expected {expected_seq_num} sequences in {expected_fasta_file}, but got: \n {fasta_file_contents}'


def test_shortcut_dump_sidechains(test_worker: TestWorker, KeyDataDuringTests: KeyData):
    test_worker.load_session_and_check(customized_session=KeyDataDuringTests.evaluate_pse_path)

    sele = 'mt_Q239_3.0'
    save_dir = f'png/sidechain_dump_{sele}/'
    shortcut_dump_sidechains(
        sele=[sele],
        enabled_only=False,
        save_dir=save_dir,
        height=1280,
        width=1280,
        dpi=150,
        ray=True,
        hide_mesh=True,
        neighborhood=3,
        reorient=True,
        recenter=False,
    )
    pngs = [f for f in os.listdir(save_dir) if f.endswith('.png')]
    assert len(pngs) == 3, f'Expected 3 pngs in {save_dir}, but got: {pngs}'

# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Content validators for uploaded scientific inputs.

Legitimate files pass, pathological files are rejected, and the caps are
generous enough that no plausible real file can trip them.
"""

from __future__ import annotations

import gzip
import io
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import _load_pssm_module, _test_client_auth
from revocompute.input_validators import (
    MAX_CIF_ATOMS,  # noqa: F401
    MAX_CIF_RECORD_LENGTH,
    MAX_FASTA_SEQUENCES,
    MAX_FASTA_TOTAL_RESIDUES,
    MAX_JSON_DEPTH,
    MAX_JSON_NODES,
    MAX_PDB_LINES,
    MAX_PDB_RECORD_LENGTH,
    validate_a3m,
    validate_fasta,
    validate_input_file,
    validate_json,
    validate_mmcif,
    validate_pdb,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(tmp_path: Path, content: bytes, name: str = "input") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


# ── real fixtures must pass ────────────────────────────────────────────────────


def test_real_fasta_fixtures_pass():
    for path in (
        REPO_ROOT / "tests/data/msa/2KL8.fasta",
        REPO_ROOT / "tests/data/msa/2KL8_blast.fasta",
        Path(__file__).parent / "data/test_esm.fasta",
    ):
        assert validate_fasta(str(path)) is None, path


def test_plugin_backends_run_before_builtin(tmp_path, monkeypatch):
    """register_plugin prepends a backend; its error wins over the built-in
    validator, proving the pluggable contract."""
    from revocompute.input_validators import register_plugin, validate_input_file

    calls = []

    def fake_backend(path):
        calls.append(path)
        return "plugin rejected this file"

    register_plugin(".fasta", fake_backend)
    path = tmp_path / "x.fasta"
    path.write_text(">t\nACDE\n", encoding="utf-8")
    try:
        assert validate_input_file(str(path), "x.fasta") == "plugin rejected this file"
    finally:
        from revocompute.input_validators import _PLUGINS

        _PLUGINS.pop(".fasta", None)
    assert calls == [str(path)]


def test_pdb_geometry_rejects_cross_element_overlap(tmp_path):
    """A carbon and an oxygen at the same position are a broken structure
    regardless of element — the overlap check must not require same elements."""
    atoms = [
        _pdb_line(1, "CA", "ALA", "A", 1, 2.5, 0.0, 0.0, "C"),
        _pdb_line(2, "N", "ALA", "A", 1, 2.5, 0.0, 0.0, "N"),
    ]
    path = _write_pdb(tmp_path, "cross.pdb", atoms)
    error = validate_pdb(str(path))
    assert error is not None and "overlapping" in error


def test_pdb_plugin_backends_run_with_dotted_kind(tmp_path, monkeypatch):
    """register_plugin('.pdb', ...) must run inside validate_pdb (kind parity
    with the registry keys)."""
    from revocompute.input_validators import register_plugin

    calls = []

    def fake_backend(path):
        calls.append(path)
        return "plugin rejected this PDB"

    register_plugin(".pdb", fake_backend)
    path = tmp_path / "x.pdb"
    path.write_text(
        "ATOM      1  CA  ALA A   1       2.500   0.000   0.000  1.00  0.00           C\nEND\n", encoding="utf-8"
    )
    try:
        assert validate_pdb(str(path)) == "plugin rejected this PDB"
    finally:
        from revocompute.input_validators import _PLUGINS

        _PLUGINS.pop(".pdb", None)
    assert calls == [str(path)]


@pytest.mark.parametrize(
    "relative",
    [
        "tests/data/pdb/1SUO.pdb",
        "tests/data/pdb/5an7.pdb",
        "tests/data/pdb/2KL8.pdb",
        "tests/data/pdb/3fap_hf3_A_short_lig.pdb",
        "tests/data/pdb/3fap_hf3_A_short_00001.pdb",
        "tests/data/3fap_hf3_A_short.pdb",
        "tests/data/6zcy_lig.pdb",
        "tests/data/lig/lig.fa.pdb",
        "tests/data/lig/lig.cen_conformers.pdb",
    ],
)
def test_real_pdb_fixtures_pass(relative):
    assert validate_pdb(str(REPO_ROOT / relative)) is None


@pytest.mark.parametrize(
    "relative",
    [
        "tests/data/json/sm_input/12968814160.json",
        "tests/data/ddg_csv.json",
        "tests/data/kinetics/openkinetics_1SUO/manifest.json",
        "tests/data/kinetics/openkinetics_1SUO/substrate.json",
        "tests/data/kinetics/openkinetics_1SUO/submit_response.json",
    ],
)
def test_real_json_fixtures_pass(relative):
    assert validate_json(str(REPO_ROOT / relative)) is None


# ── FASTA / A3M ────────────────────────────────────────────────────────────────


def test_fasta_requires_header(tmp_path):
    path = _write(tmp_path, b"ACDEFGHIK\n")
    assert "'>' header" in validate_fasta(str(path))


def test_fasta_rejects_sequence_before_header(tmp_path):
    path = _write(tmp_path, b"ACDE\n>h\nACDE\n")
    assert "start with a '>' header" in validate_fasta(str(path))


def test_fasta_rejects_non_alphabet_characters(tmp_path):
    path = _write(tmp_path, b">h\nACD2EF\n")
    assert "invalid character '2'" in validate_fasta(str(path))


def test_fasta_rejects_lowercase_but_a3m_allows_it(tmp_path):
    lower = _write(tmp_path, b">h\nACDEfghi\n")
    assert "invalid character" in validate_fasta(str(lower))
    assert validate_a3m(str(lower)) is None


def test_fasta_accepts_full_alphabet_and_gaps(tmp_path):
    path = _write(
        tmp_path,
        b">h\nACDEFGHIKLMNPQRSTVWYXBZJOU*-. ACDE\n",  # interior space tolerated
    )
    assert validate_fasta(str(path)) is None


def test_fasta_rejects_nul_byte_deep_in_file(tmp_path):
    # The HTTP-layer sniff only reads 4096 bytes, so the NUL must be caught here.
    path = _write(tmp_path, b">h\n" + b"A" * 8192 + b"\0ACDE\n")
    assert "NUL byte" in validate_fasta(str(path))


def test_fasta_rejects_too_many_sequences(tmp_path):
    path = _write(tmp_path, b">s\nA\n" * (MAX_FASTA_SEQUENCES + 1))
    assert f"more than {MAX_FASTA_SEQUENCES} sequences" in validate_fasta(str(path))


def test_fasta_residue_cap_cannot_be_reached_within_upload_limit():
    # 16 MiB upload cap / 1 byte per residue — the cap is a safety valve that
    # cannot fire on any file that fits in MAX_CONTENT_LENGTH.
    assert MAX_FASTA_TOTAL_RESIDUES > 16 * 1024 * 1024


# ── PDB ────────────────────────────────────────────────────────────────────────


def test_pdb_accepts_long_remark_preamble(tmp_path):
    preamble = b"REMARK 999 long preamble\n" * 200
    body = (
        b"CRYST1  100.0 100.0 100.0  90 90 90 P 1\n"
        b"ATOM      1  CA  ALA A   1      0.000   0.000   0.000  1.00  0.00           C\n"
        b"END\n"
    )
    path = _write(tmp_path, preamble + body)
    assert validate_pdb(str(path)) is None


def test_pdb_accepts_single_atom_line_without_end(tmp_path):
    # Mirrors the minimal PDB used by existing route tests.
    path = _write(tmp_path, b"ATOM      1  CA  ALA A   1\n")
    assert validate_pdb(str(path)) is None


def test_pdb_rejects_gzip_binary(tmp_path):
    # Compressed bytes are rejected by either the NUL check or the record
    # sniff — what matters is that no gzip stream passes for a PDB.
    path = _write(tmp_path, gzip.compress(b"ATOM      1  CA  ALA A   1\n" * 100), "model.pdb")
    assert validate_pdb(str(path)) is not None


def test_pdb_rejects_plain_text_without_records(tmp_path):
    path = _write(tmp_path, b"this is not a pdb\n" * 50)
    assert "ATOM, HETATM, or END" in validate_pdb(str(path))


def test_pdb_rejects_too_many_lines(tmp_path):
    path = _write(tmp_path, b"END\n" * (MAX_PDB_LINES + 1))
    assert f"more than {MAX_PDB_LINES} lines" in validate_pdb(str(path))


def test_pdb_rejects_overlong_record(tmp_path):
    path = _write(tmp_path, b"ATOM  " + b"X" * MAX_PDB_RECORD_LENGTH + b"\n")
    assert "longer than" in validate_pdb(str(path))


def test_pdb_rejects_nul_byte(tmp_path):
    path = _write(tmp_path, b"ATOM      1  CA  ALA A   1\n\0ACDE\n")
    assert "NUL byte" in validate_pdb(str(path))


# ── mmCIF ──────────────────────────────────────────────────────────────────────


def _mmcif(atom_rows: int) -> bytes:
    head = (
        "data_1SUO\n"
        "#\n"
        "_cell.length_a 100.0\n"
        "_cell.length_b 100.0\n"
        "loop_\n"
        "_atom_site.group_PDB\n"
        "_atom_site.id\n"
        "_atom_site.type_symbol\n"
        "_atom_site.label_atom_id\n"
        "_atom_site.label_comp_id\n"
    )
    rows = "".join(f"ATOM {i} N N ALA\n" for i in range(1, atom_rows + 1))
    return (head + rows + "#\nloop_\n_entity.id\n1\n").encode()


def test_mmcif_realistic_file_passes(tmp_path):
    path = _write(tmp_path, _mmcif(100))
    assert validate_mmcif(str(path)) is None


def test_mmcif_accepts_second_data_block_without_atoms(tmp_path):
    # A .cif used for restraints/topology may have no _atom_site loop at all.
    path = _write(tmp_path, b"data_restraints\n_chem_comp.id 'ALA'\n")
    assert validate_mmcif(str(path)) is None


def test_mmcif_rejects_plain_text(tmp_path):
    path = _write(tmp_path, b"this is not a cif\n" * 50)
    assert "data_ block or _atom_site." in validate_mmcif(str(path))


def test_mmcif_rejects_too_many_atoms(tmp_path):
    path = _write(tmp_path, _mmcif(MAX_CIF_ATOMS + 1))
    assert f"more than {MAX_CIF_ATOMS} atoms" in validate_mmcif(str(path))


def test_mmcif_rejects_overlong_record(tmp_path):
    path = _write(tmp_path, b"data_x\n" + b"_atom_site.id " + b"Y" * MAX_CIF_RECORD_LENGTH + b"\n")
    assert "longer than" in validate_mmcif(str(path))


def test_mmcif_rejects_nul_byte(tmp_path):
    path = _write(tmp_path, b"data_x\n\x00")
    assert "NUL byte" in validate_mmcif(str(path))


# ── JSON ───────────────────────────────────────────────────────────────────────


def test_json_accepts_valid_documents(tmp_path):
    for doc in ("{}", "[]", '"plain string"', "42", '[{"a": [1, 2, {"b": null}]}]'):
        path = _write(tmp_path, doc.encode())
        assert validate_json(str(path)) is None, doc


def test_json_rejects_invalid_json(tmp_path):
    path = _write(tmp_path, b'{"contigs": ["A1-10", }')
    assert "not appear to be valid JSON" in validate_json(str(path))


# -- PDB geometry sanity -------------------------------------------------------


def _pdb_line(serial, name, res, chain, seq, x, y, z, element, altloc=" "):
    return (
        f"ATOM  {serial:5d} {name:>4s}{altloc}{res:>3s} {chain}{seq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}"
    )


def _write_pdb(tmp_path, name, atoms):
    path = tmp_path / name
    path.write_text("\n".join(atoms) + "\nTER\nEND\n", encoding="utf-8")
    return path


def test_pdb_geometry_rejects_misplaced_terminal_oxygen(tmp_path):
    # A carbonyl carbon with its own O plus a colliding OXT from another
    # residue — the exact failure class of real-world tophit PDBs that
    # RDKit rejects with "Explicit valence ... greater than permitted".
    atoms = [
        _pdb_line(1, "N", "ALA", "A", 1, 1.5, 0.0, 0.0, "N"),
        _pdb_line(2, "CA", "ALA", "A", 1, 2.5, 0.0, 0.0, "C"),
        _pdb_line(3, "C", "ALA", "A", 1, 3.5, 0.0, 0.0, "C"),
        _pdb_line(4, "O", "ALA", "A", 1, 3.9, -1.0, 0.0, "O"),
        # OXT nominally belongs to a distant residue but collides with C
        _pdb_line(5, "OXT", "GLY", "A", 9, 3.9, 1.0, 0.0, "O"),
        # neighbor to complete the C's environment
        _pdb_line(6, "N", "GLY", "A", 9, 4.4, 0.0, 0.0, "N"),
    ]
    path = _write_pdb(tmp_path, "bad_oxt.pdb", atoms)
    error = validate_pdb(str(path))
    assert error is not None and "ALA1 C" in error and "OXT" in error


def test_pdb_geometry_rejects_duplicate_atoms(tmp_path):
    atoms = [
        _pdb_line(1, "N", "ALA", "A", 1, 1.5, 0.0, 0.0, "N"),
        _pdb_line(2, "CA", "ALA", "A", 1, 2.5, 0.0, 0.0, "C"),
        _pdb_line(3, "CB", "ALA", "A", 1, 2.5, 0.0, 0.0, "C"),  # same coords
    ]
    path = _write_pdb(tmp_path, "dup.pdb", atoms)
    error = validate_pdb(str(path))
    assert error is not None and "overlapping" in error


def test_pdb_geometry_accepts_altloc_records(tmp_path):
    atoms = [
        _pdb_line(1, "N", "SER", "A", 1, 1.5, 0.0, 0.0, "N"),
        _pdb_line(2, "CA", "SER", "A", 1, 2.5, 0.0, 0.0, "C"),
        _pdb_line(3, "CB", "SER", "A", 1, 2.5, 1.0, 0.0, "C"),
        _pdb_line(4, "OG", "SER", "A", 1, 2.5, 1.9, 0.0, "O"),
    ]
    # duplicate the OG with an alternate location indicator (col 17 = 'B')
    alt = _pdb_line(4, "OG", "SER", "A", 1, 2.6, 1.9, 0.0, "O", altloc="B")
    path = _write_pdb(tmp_path, "altloc.pdb", atoms + [alt])
    assert validate_pdb(str(path)) is None


def test_json_rejects_oversized_input_before_parsing(tmp_path):
    # A flat list of MAX_JSON_NODES + 1 elements is well-formed JSON but
    # exceeds the pre-parse byte ceiling, which rejects it before the full
    # object graph is allocated (the node-count cap is the second line of
    # defence and stays for future ceiling changes).
    path = _write(tmp_path, ("[" + "0," * MAX_JSON_NODES + "0]").encode())
    assert "MiB input limit" in validate_json(str(path))


def test_json_rejects_deep_nesting(tmp_path):
    # The leaf sits at depth MAX_JSON_DEPTH + 1 — one level past the cap.
    doc = "[" * MAX_JSON_DEPTH + "0" + "]" * MAX_JSON_DEPTH
    path = _write(tmp_path, doc.encode())
    assert f"nested deeper than {MAX_JSON_DEPTH}" in validate_json(str(path))


def test_json_accepts_nesting_at_the_cap(tmp_path):
    # The deepest value of MAX_JSON_DEPTH containers sits at depth
    # MAX_JSON_DEPTH and must pass.
    doc = "[" * (MAX_JSON_DEPTH - 1) + "0" + "]" * (MAX_JSON_DEPTH - 1)
    path = _write(tmp_path, doc.encode())
    assert validate_json(str(path)) is None


def test_json_rejects_non_utf8(tmp_path):
    path = _write(tmp_path, b'{"name": "\xff\xfe"}')
    assert "not valid UTF-8" in validate_json(str(path))


def test_json_rejects_nul_byte(tmp_path):
    path = _write(tmp_path, b'{"a": 1}\x00')
    assert "NUL byte" in validate_json(str(path))


# ── extension dispatch ─────────────────────────────────────────────────────────


def test_dispatch_routes_by_extension(tmp_path):
    pdb = _write(tmp_path, b"ATOM      1  CA  ALA A   1\n", "model.pdb")
    assert validate_input_file(str(pdb), "model.pdb") is None
    assert validate_input_file(str(pdb), "sub/dir/model.pdb") is None
    fasta = _write(tmp_path, b"not fasta\n", "seqs.fasta")
    assert validate_input_file(str(fasta), "seqs.fasta") is not None
    assert validate_input_file(str(pdb), "model.txt") is None  # no validator -> pass


def test_a3m_dispatched_by_extension(tmp_path):
    path = _write(tmp_path, b">h\nACDEfghi\n", "msa.a3m")
    assert validate_input_file(str(path), "msa.a3m") is None


# ── route level: the security fix ──────────────────────────────────────────────


def _pdb_task_module(monkeypatch, tmp_path):
    """Load the app with a registered non-GREMLIN .pdb task type."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    base_type, runner = module.task_runtime._get_task_type("gremlin")
    module.task_runtime._register_tt(
        replace(
            base_type,
            name="pdb_only",
            display_name="PDB Only",
            input_extension=".pdb",
            input_extensions=(".pdb",),
            primary_input_extensions=(".pdb",),
            input_label="PDB file",
            params=(),
        ),
        runner,
    )
    return module


def test_upload_gzip_disguised_as_pdb_rejected(monkeypatch, tmp_path):
    """Non-GREMLIN inputs are content-checked: a gzip bomb named .pdb is refused."""
    module = _pdb_task_module(monkeypatch, tmp_path)
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    payload = gzip.compress(b"ATOM      1  CA  ALA A   1\n" * 100)

    response = client.post(
        "/compute/api/post",
        data={"task_type": "pdb_only", "file": (io.BytesIO(payload), "model.pdb")},
        headers=auth_header,
    )
    assert response.status_code == 400, response.get_data(as_text=True)


def test_upload_text_without_pdb_records_rejected(monkeypatch, tmp_path):
    """Plain text (not caught by the binary sniff) named .pdb is refused."""
    module = _pdb_task_module(monkeypatch, tmp_path)
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    response = client.post(
        "/compute/api/post",
        data={"task_type": "pdb_only", "file": (io.BytesIO(b"this is not a pdb\n" * 50), "model.pdb")},
        headers=auth_header,
    )
    assert response.status_code == 400, response.get_data(as_text=True)
    assert "ATOM, HETATM, or END" in response.json["error"]


def test_upload_bad_fasta_for_gremlin_rejected(monkeypatch, tmp_path):
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    response = client.post(
        "/compute/api/post",
        data={"file": (io.BytesIO(b"ACDE\n>h\nACDE\n"), "seqs.fasta")},
        headers=auth_header,
    )
    assert response.status_code == 400, response.get_data(as_text=True)
    assert "start with a '>' header" in response.json["error"]


def test_upload_valid_pdb_accepted(monkeypatch, tmp_path):
    module = _pdb_task_module(monkeypatch, tmp_path)
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    class _Queued:
        id = "queued-pdb"

    monkeypatch.setattr(module.run_compute_task, "apply_async", lambda *args, **kwargs: _Queued())
    response = client.post(
        "/compute/api/post",
        data={"task_type": "pdb_only", "file": (io.BytesIO(b"ATOM      1  CA  ALA A   1\n"), "model.pdb")},
        headers=auth_header,
    )
    assert response.status_code == 302, response.get_json()

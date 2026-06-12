# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for ``REvoDesign.tools.measure_utils``.

Covers:
  - ``MeasureInfo`` parsing for distance / angle / dihedral types
  - ``DistSet`` parsing with all coordinate arrays
  - ``Measurement`` from session names entries
  - atom resolution via unique_id and coordinate fallback
  - measurement type identification
  - value computation (distance, angle, dihedral)
  - ``read_measurement`` command
"""

from __future__ import annotations

import math

import pymol
import pytest
from pymol import cmd

from REvoDesign.tools.measure_utils import (
    AtomDescriptor,
    DistSet,
    MeasureInfo,
    Measurement,
    MeasureType,
    build_scene_atom_list,
    build_unique_id_map,
    read_measurement,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _pymol_startup():
    """Launch PyMOL once per test session."""
    pymol.finish_launching(["pymol", "-qc"])


@pytest.fixture(autouse=True)
def _pymol_session(_pymol_startup):
    """Fresh PyMOL state for each test function."""
    cmd.reinitialize()
    cmd.fab("ACDEFGHIKL", "test_protein")
    yield
    cmd.reinitialize()


@pytest.fixture
def protein_atoms() -> list[AtomDescriptor]:
    """Return the scene atom list for the test structure."""
    return build_scene_atom_list(cmd)


# ---------------------------------------------------------------------------
# MeasureInfo tests
# ---------------------------------------------------------------------------


class TestMeasureInfo:
    def test_from_pylist_distance(self):
        """Distance MeasureInfo: 2 ids → DISTANCE type."""
        mi = MeasureInfo.from_pylist([0, [100, 200], [0, 0]])
        assert mi.offset == 0
        assert mi.ids == [100, 200]
        assert mi.states == [0, 0]
        assert mi.measure_type == MeasureType.DISTANCE
        assert mi.is_distance
        assert not mi.is_angle
        assert not mi.is_dihedral

    def test_from_pylist_angle(self):
        """Angle MeasureInfo: 3 ids → ANGLE type."""
        mi = MeasureInfo.from_pylist([1, [300, 400, 500], [0, 0, 0]])
        assert mi.offset == 1
        assert mi.ids == [300, 400, 500]
        assert mi.states == [0, 0, 0]
        assert mi.measure_type == MeasureType.ANGLE
        assert not mi.is_distance
        assert mi.is_angle
        assert not mi.is_dihedral

    def test_from_pylist_dihedral(self):
        """Dihedral MeasureInfo: 4 ids → DIHEDRAL type."""
        mi = MeasureInfo.from_pylist([2, [10, 20, 30, 40], [1, 1, 1, 1]])
        assert mi.offset == 2
        assert mi.ids == [10, 20, 30, 40]
        assert mi.states == [1, 1, 1, 1]
        assert mi.measure_type == MeasureType.DIHEDRAL
        assert not mi.is_distance
        assert not mi.is_angle
        assert mi.is_dihedral

    def test_measure_type_from_atom_count(self):
        assert MeasureType.from_atom_count(2) == MeasureType.DISTANCE
        assert MeasureType.from_atom_count(3) == MeasureType.ANGLE
        assert MeasureType.from_atom_count(4) == MeasureType.DIHEDRAL
        # any other count defaults to DIHEDRAL (matching C++ behavior)
        assert MeasureType.from_atom_count(1) == MeasureType.DIHEDRAL
        assert MeasureType.from_atom_count(5) == MeasureType.DIHEDRAL


# ---------------------------------------------------------------------------
# DistSet tests
# ---------------------------------------------------------------------------


class TestDistSet:
    def test_from_pylist_empty(self):
        """Minimal DistSet (padded with None → defaults)."""
        ds = DistSet.from_pylist([0])
        assert ds.nindex == 0
        assert ds.nangleindex == 0
        assert ds.ndihedralindex == 0
        assert ds.coord is None
        assert ds.anglecoord is None
        assert ds.dihedralcoord is None
        assert ds.measure_info == []

    def test_from_pylist_distance_only(self):
        """DistSet with one distance measurement."""
        raw = [
            2,  # NIndex = 2 vertices (1 distance)
            [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],  # Coord
            None,  # LabCoord
            0,  # NAngleIndex
            None,  # AngleCoord
            0,  # NDihedralIndex
            None,  # DihedralCoord
            None,  # Setting
            None,  # LabPos
            [[0, [101, 102], [0, 0]]],  # MeasureInfo
        ]
        ds = DistSet.from_pylist(raw)
        assert ds.nindex == 2
        assert ds.coord == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
        assert ds.nangleindex == 0
        assert ds.ndihedralindex == 0
        assert len(ds.measure_info) == 1
        assert ds.measure_info[0].measure_type == MeasureType.DISTANCE
        assert ds.has_distances
        assert not ds.has_angles
        assert not ds.has_dihedrals
        assert ds.num_distances == 1
        assert ds.num_angles == 0
        assert ds.num_dihedrals == 0

    def test_from_pylist_angle_only(self):
        """DistSet with one angle measurement."""
        raw = [
            0,  # NIndex
            None,  # Coord
            None,  # LabCoord
            3,  # NAngleIndex = 3 vertices (1 angle)
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 2.0, 1.0, 0.0],  # AngleCoord
            0,  # NDihedralIndex
            None,  # DihedralCoord
            None,  # Setting
            None,  # LabPos
            [[0, [201, 202, 203], [0, 0, 0]]],  # MeasureInfo
        ]
        ds = DistSet.from_pylist(raw)
        assert ds.nangleindex == 3
        assert ds.anglecoord == [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 2.0, 1.0, 0.0]
        assert not ds.has_distances
        assert ds.has_angles
        assert not ds.has_dihedrals
        assert ds.num_angles == 1

    def test_from_pylist_dihedral_only(self):
        """DistSet with one dihedral measurement."""
        raw = [
            0,  # NIndex
            None,  # Coord
            None,  # LabCoord
            0,  # NAngleIndex
            None,  # AngleCoord
            4,  # NDihedralIndex = 4 vertices (1 dihedral)
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 2.0, 1.0, 1.0],  # DihedralCoord
            None,  # Setting
            None,  # LabPos
            [[0, [301, 302, 303, 304], [0, 0, 0, 0]]],  # MeasureInfo
        ]
        ds = DistSet.from_pylist(raw)
        assert ds.ndihedralindex == 4
        assert len(ds.dihedralcoord) == 12
        assert not ds.has_distances
        assert not ds.has_angles
        assert ds.has_dihedrals
        assert ds.num_dihedrals == 1

    def test_from_pylist_mixed(self):
        """DistSet with distance + angle + dihedral in one frame."""
        raw = [
            2,  # NIndex
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],  # Coord
            None,
            3,  # NAngleIndex
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],  # AngleCoord
            4,  # NDihedralIndex
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0],  # DihedralCoord
            None,
            None,
            [
                [0, [101, 102], [0, 0]],
                [0, [201, 202, 203], [0, 0, 0]],
                [0, [301, 302, 303, 304], [0, 0, 0, 0]],
            ],
        ]
        ds = DistSet.from_pylist(raw)
        assert ds.has_distances
        assert ds.has_angles
        assert ds.has_dihedrals
        assert ds.num_distances == 1
        assert ds.num_angles == 1
        assert ds.num_dihedrals == 1

    def test_get_vertex_coords_distance(self):
        """Vertex coordinate extraction for a distance measurement."""
        raw = [
            2,
            [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],  # 2 vertices
            None,
            0,
            None,
            0,
            None,
            None,
            None,
            [[0, [101, 102], [0, 0]]],
        ]
        ds = DistSet.from_pylist(raw)
        coords = ds.get_vertex_coords_for_measure(ds.measure_info[0])
        assert len(coords) == 2
        assert coords[0] == (0.0, 1.0, 2.0)
        assert coords[1] == (3.0, 4.0, 5.0)

    def test_get_vertex_coords_angle(self):
        """Vertex coordinate extraction for an angle measurement."""
        raw = [
            0,
            None,
            None,
            3,  # 3 vertices
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            0,
            None,
            None,
            None,
            [[0, [201, 202, 203], [0, 0, 0]]],
        ]
        ds = DistSet.from_pylist(raw)
        coords = ds.get_vertex_coords_for_measure(ds.measure_info[0])
        assert len(coords) == 3
        assert coords[0] == (0.0, 0.0, 0.0)
        assert coords[1] == (1.0, 0.0, 0.0)
        assert coords[2] == (0.0, 1.0, 0.0)

    def test_get_vertex_coords_dihedral(self):
        """Vertex coordinate extraction for a dihedral measurement."""
        raw = [
            0,
            None,
            None,
            0,
            None,
            4,  # 4 vertices
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0],
            None,
            None,
            [[0, [301, 302, 303, 304], [0, 0, 0, 0]]],
        ]
        ds = DistSet.from_pylist(raw)
        coords = ds.get_vertex_coords_for_measure(ds.measure_info[0])
        assert len(coords) == 4
        assert coords[0] == (0.0, 0.0, 0.0)
        assert coords[3] == (0.0, 1.0, 1.0)

    def test_get_vertex_coords_offset(self):
        """Offset indexing: second measurement starts at vertex 2."""
        raw = [
            4,  # 4 distance vertices = 2 measurements
            [
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,  # meas 0 (offset 0)
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,  # meas 1 (offset 2)
            ],
            None,
            0,
            None,
            0,
            None,
            None,
            None,
            [
                [0, [101, 102], [0, 0]],
                [2, [201, 202], [0, 0]],
            ],
        ]
        ds = DistSet.from_pylist(raw)
        coords0 = ds.get_vertex_coords_for_measure(ds.measure_info[0])
        coords1 = ds.get_vertex_coords_for_measure(ds.measure_info[1])
        assert coords0[0] == (0.0, 0.0, 0.0)
        assert coords0[1] == (1.0, 0.0, 0.0)
        assert coords1[0] == (0.0, 0.0, 0.0)
        assert coords1[1] == (0.0, 1.0, 0.0)


# ---------------------------------------------------------------------------
# Measurement (top-level) tests
# ---------------------------------------------------------------------------


class TestMeasurement:
    @staticmethod
    def _make_names_entry(
        name: str,
        nindex: int = 2,
        coord: list[float] | None = None,
        measure_info_list: list[list] | None = None,
    ) -> list:
        """Build a minimal ``get_session()['names']`` entry for a distance measurement."""
        if coord is None:
            coord = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        if measure_info_list is None:
            measure_info_list = [[0, [101, 102], [0, 0]]]

        object_dist_pylist = [
            # ObjectAsPyList header (minimal: [type_info, name, ...])
            [object(), name],
            1,  # DSet count
            [[nindex, coord, None, 0, None, 0, None, None, None, measure_info_list]],  # DistSet list
            0,
        ]
        return [name, 1, 0, None, 4, object_dist_pylist, ""]

    def test_from_names_entry_distance(self):
        entry = self._make_names_entry("dist1")
        m = Measurement.from_names_entry(entry)
        assert m is not None
        assert m.name == "dist1"
        assert m.is_distance
        assert not m.is_angle
        assert not m.is_dihedral
        assert m.measurement_type == MeasureType.DISTANCE
        assert m.num_measurements == 1

    def test_from_names_entry_angle(self):
        entry = self._make_names_entry(
            "angle1",
            nindex=0,
            coord=None,
            measure_info_list=[[0, [201, 202, 203], [0, 0, 0]]],
        )
        # Patch: set NAngleIndex and AngleCoord in the DistSet
        entry[5][2][0][3] = 3  # NAngleIndex
        entry[5][2][0][4] = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]  # AngleCoord
        m = Measurement.from_names_entry(entry)
        assert m is not None
        assert m.is_angle
        assert m.measurement_type == MeasureType.ANGLE
        assert m.num_measurements == 1

    def test_from_names_entry_dihedral(self):
        entry = self._make_names_entry(
            "dih1",
            nindex=0,
            coord=None,
            measure_info_list=[[0, [301, 302, 303, 304], [0, 0, 0, 0]]],
        )
        entry[5][2][0][5] = 4  # NDihedralIndex
        entry[5][2][0][6] = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0]
        m = Measurement.from_names_entry(entry)
        assert m is not None
        assert m.is_dihedral
        assert m.measurement_type == MeasureType.DIHEDRAL

    def test_from_names_entry_mixed(self):
        """Mixed distance + angle in same measurement object."""
        entry = self._make_names_entry(
            "mixed1",
            nindex=2,
            coord=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            measure_info_list=[[0, [101, 102], [0, 0]]],
        )
        # add angle to same DistSet
        entry[5][2][0][3] = 3  # NAngleIndex
        entry[5][2][0][4] = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        entry[5][2][0][9].append([0, [201, 202, 203], [0, 0, 0]])
        m = Measurement.from_names_entry(entry)
        assert m is not None
        assert m.measurement_type is None  # mixed
        assert not m.is_distance
        assert not m.is_angle
        assert not m.is_dihedral
        assert m.is_mixed
        assert m.num_measurements == 2
        assert m.num_distances == 1
        assert m.num_angles == 1
        assert m.num_dihedrals == 0

    def test_from_session_names_multiple(self):
        entries = [
            self._make_names_entry("d1"),
            self._make_names_entry("d2"),
        ]
        measurements = Measurement.from_session_names(entries)
        assert len(measurements) == 2
        assert measurements[0].name == "d1"
        assert measurements[1].name == "d2"

    def test_from_session_names_skips_non_measurements(self):
        entries = [
            self._make_names_entry("d1"),
            ["molecule", 1, 0, None, 1, None, ""],  # cObjectMolecule, not a measurement
        ]
        measurements = Measurement.from_session_names(entries)
        assert len(measurements) == 1


# ---------------------------------------------------------------------------
# Value computation tests
# ---------------------------------------------------------------------------


class TestValueComputation:
    def test_compute_distance(self):
        """Distance between (0,0,0) and (3,4,0) = 5.0."""
        coords = [(0.0, 0.0, 0.0), (3.0, 4.0, 0.0)]
        result = Measurement._compute_distance(coords)
        assert result == pytest.approx(5.0)

    def test_compute_distance_nan(self):
        """Not enough coords → NaN."""
        assert math.isnan(Measurement._compute_distance([(0.0, 0.0, 0.0)]))

    def test_compute_angle_right(self):
        """90° angle: (1,0,0)-(0,0,0)-(0,1,0)."""
        coords = [(1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        result = Measurement._compute_angle(coords)
        assert result == pytest.approx(90.0)

    def test_compute_angle_straight(self):
        """180° angle: (1,0,0)-(0,0,0)-(-1,0,0)."""
        coords = [(1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0)]
        result = Measurement._compute_angle(coords)
        assert result == pytest.approx(180.0)

    def test_compute_angle_nan(self):
        assert math.isnan(Measurement._compute_angle([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]))

    def test_compute_dihedral_trans(self):
        """Trans (180°) dihedral: planar zigzag."""
        coords = [(1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (2.0, 1.0, 0.0)]
        result = Measurement._compute_dihedral(coords)
        assert abs(result) == pytest.approx(180.0)

    def test_compute_dihedral_gauche_plus(self):
        """Gauche+ (~60°) dihedral in a tetrahedral-like arrangement."""
        # Verified geometry: A=(0,0,0), B=(1,0,0), C=(1,1,0), D=(1.5,1,√3/2)
        coords = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (1.5, 1.0, 0.86602540378)]
        result = Measurement._compute_dihedral(coords)
        assert abs(result) == pytest.approx(60.0)

    def test_compute_dihedral_nan(self):
        assert math.isnan(Measurement._compute_dihedral([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]))

    def test_get_value_distance(self):
        """End-to-end value computation for a distance measurement."""
        entry = TestMeasurement._make_names_entry("d1")
        m = Measurement.from_names_entry(entry)
        assert m is not None
        ds = m.dsets[0]
        mi = ds.measure_info[0]
        val = m.get_value(mi, ds)
        # (0,0,0) → (1,0,0) = 1.0 Å
        assert val == pytest.approx(1.0)

    def test_get_value_angle(self):
        """End-to-end value computation for an angle measurement."""
        entry = TestMeasurement._make_names_entry(
            "a1",
            nindex=0,
            coord=None,
            measure_info_list=[[0, [201, 202, 203], [0, 0, 0]]],
        )
        entry[5][2][0][3] = 3
        entry[5][2][0][4] = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        m = Measurement.from_names_entry(entry)
        assert m is not None
        val = m.get_value(m.dsets[0].measure_info[0], m.dsets[0])
        assert val == pytest.approx(90.0)

    def test_summarize(self):
        entry = TestMeasurement._make_names_entry("d1")
        m = Measurement.from_names_entry(entry)
        assert m is not None
        summary = m.summarize(cmd_module=cmd)
        assert "d1" in summary
        assert "DISTANCE" in summary


# ---------------------------------------------------------------------------
# Scene atom helpers
# ---------------------------------------------------------------------------


class TestSceneAtomHelpers:
    def test_build_scene_atom_list(self):
        atoms = build_scene_atom_list(cmd)
        assert len(atoms) > 0
        assert all(isinstance(a, AtomDescriptor) for a in atoms)
        # Check basic atom properties
        for a in atoms:
            assert a.obj is not None
            assert a.atom_index >= 0

    def test_build_unique_id_map(self):
        """Build unique_id map — populated when atoms expose unique_id."""
        uid_map = build_unique_id_map(cmd)
        # unique_id is an internal PyMOL attribute; it may or may not be
        # populated by cmd.get_model() depending on the PyMOL version and
        # model type.  The function itself must not crash.
        assert isinstance(uid_map, dict)
        if len(uid_map) > 0:
            for uid, atom in uid_map.items():
                assert isinstance(uid, int)
                assert isinstance(atom, AtomDescriptor)
                assert atom.unique_id == uid


# ---------------------------------------------------------------------------
# Real PyMOL measurement integration tests
# ---------------------------------------------------------------------------


class TestRealPyMOLMeasurements:
    """Integration tests that create real PyMOL measurements and parse them."""

    def test_distance_roundtrip(self):
        """Create a distance in PyMOL and verify it's parsed correctly."""
        cmd.distance("test_dist", "test_protein and resi 1 and name CA", "test_protein and resi 3 and name CA")
        session = cmd.get_session()
        measurements = Measurement.from_session_names(session["names"])
        dist_measurements = [m for m in measurements if m.name == "test_dist"]
        assert len(dist_measurements) == 1
        m = dist_measurements[0]
        assert m.is_distance
        assert m.num_measurements >= 1
        # atoms should resolve
        atoms = m.atoms(cmd)
        assert len(atoms) >= 1

    def test_angle_roundtrip(self):
        """Create an angle in PyMOL and verify it's parsed correctly."""
        cmd.angle(
            "test_angle",
            "test_protein and resi 1 and name CA",
            "test_protein and resi 2 and name CA",
            "test_protein and resi 3 and name CA",
        )
        session = cmd.get_session()
        measurements = Measurement.from_session_names(session["names"])
        angle_measurements = [m for m in measurements if m.name == "test_angle"]
        assert len(angle_measurements) == 1
        m = angle_measurements[0]
        assert m.is_angle
        assert m.num_measurements >= 1
        assert m.measurement_type == MeasureType.ANGLE

    def test_dihedral_roundtrip(self):
        """Create a dihedral in PyMOL and verify it's parsed correctly."""
        cmd.dihedral(
            "test_dih",
            "test_protein and resi 1 and name CA",
            "test_protein and resi 2 and name CA",
            "test_protein and resi 3 and name CA",
            "test_protein and resi 4 and name CA",
        )
        session = cmd.get_session()
        measurements = Measurement.from_session_names(session["names"])
        dih_measurements = [m for m in measurements if m.name == "test_dih"]
        assert len(dih_measurements) == 1
        m = dih_measurements[0]
        assert m.is_dihedral
        assert m.num_measurements >= 1
        assert m.measurement_type == MeasureType.DIHEDRAL

    def test_multiple_measurement_types(self):
        """All three measurement types coexist in one session."""
        cmd.distance("m_dist", "test_protein and resi 1 and name CA", "test_protein and resi 3 and name CA")
        cmd.angle(
            "m_angle",
            "test_protein and resi 1 and name CA",
            "test_protein and resi 2 and name CA",
            "test_protein and resi 3 and name CA",
        )
        cmd.dihedral(
            "m_dih",
            "test_protein and resi 1 and name CA",
            "test_protein and resi 2 and name CA",
            "test_protein and resi 3 and name CA",
            "test_protein and resi 4 and name CA",
        )
        session = cmd.get_session()
        measurements = Measurement.from_session_names(session["names"])
        names = {m.name for m in measurements}
        assert "m_dist" in names
        assert "m_angle" in names
        assert "m_dih" in names

        for m in measurements:
            assert m.measurement_type is not None
            atoms = m.atoms(cmd)
            assert (
                len(atoms)
                == {MeasureType.DISTANCE: 2, MeasureType.ANGLE: 3, MeasureType.DIHEDRAL: 4}[m.measurement_type]
            )

    def test_atom_resolution_has_residue_info(self):
        """Resolved atoms contain meaningful residue information."""
        cmd.distance("res_test", "test_protein and resi 1 and name CA", "test_protein and resi 5 and name CA")
        session = cmd.get_session()
        measurements = Measurement.from_session_names(session["names"])
        m = next(m for m in measurements if m.name == "res_test")
        atoms = m.atoms(cmd)
        residues = {a.resi for a in atoms if a.resi is not None}
        assert "1" in residues
        assert "5" in residues

    def test_read_measurement_command(self):
        """The ``read_measurement`` extended command is registered in PyMOL."""
        cmd.distance("cmd_test", "test_protein and resi 1 and name CA", "test_protein and resi 3 and name CA")
        # Should not raise
        result = read_measurement(start=0, debug=0)
        assert isinstance(result, list)
        assert len(result) >= 1

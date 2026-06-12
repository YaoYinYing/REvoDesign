# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""
Read PyMOL measurement objects and produce Gromacs index input strings.

PyMOL stores all measurements (distance, angle, dihedral) in a unified
``ObjectDist`` / ``DistSet`` data structure.  The object type constant is
``cObjectMeasurement == 4`` (see ``layer1/PyMOLObject.h``).  Each
``CMeasureInfo`` records an explicit ``measureType`` which is *inferred*
during session serialization from the number of atom ids:

  - 2 ids → ``cRepDash`` (distance)
  - 3 ids → ``cRepAngle`` (angle)
  - 4 ids → ``cRepDihedral`` (dihedral)

References
----------
- ``layer2/DistSet.h`` — ``CMeasureInfo`` and ``DistSet`` definitions
- ``layer2/ObjectDist.h`` — ``ObjectDist`` (the measurement CObject)
- ``layer2/DistSet.cpp`` — ``MeasureInfoListFromPyList`` / ``AsPyList``
- ``layer3/Executive.cpp`` — ``ExecutiveGetExecObjectAsPyList`` (session format)

Author: Yinying Yao
Date: 2026-02-03 (original), 2026-06-11 (refactored for all measurement types)

Usage
-----
1. run this script in pymol console: ``run /path/to/measure_utils.py``
2. call the extended command: ``read_measurement [start,[debug]]``
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from pymol import cmd

# ---------------------------------------------------------------------------
# Measurement type constants (matching pymol-open-source layer1/Rep.h)
# ---------------------------------------------------------------------------


class MeasureType(IntEnum):
    """Measurement types corresponding to C++ ``cRepDash`` / ``cRepAngle`` / ``cRepDihedral``."""

    DISTANCE = 2  # cRepDash (2 atoms)
    ANGLE = 3  # cRepAngle (3 atoms)
    DIHEDRAL = 4  # cRepDihedral (4 atoms)

    @classmethod
    def from_atom_count(cls, n: int) -> MeasureType:
        """Infer measurement type from the number of atom ids.

        This mirrors the C++ logic in ``MeasureInfoListFromPyList``::

            item->measureType = (N == 2) ? cRepDash :
                                (N == 3) ? cRepAngle : cRepDihedral;
        """
        if n == 2:
            return cls.DISTANCE
        if n == 3:
            return cls.ANGLE
        return cls.DIHEDRAL


# ---------------------------------------------------------------------------
# Atom descriptor
# ---------------------------------------------------------------------------


@dataclass
class AtomDescriptor:
    """Lightweight descriptor for a single atom in the PyMOL scene."""

    obj: str
    atom_index: int  # 0-based index of atom within its object
    chain: str | None
    segi: str | None
    resi: str | None
    resn: str | None
    name: str | None
    unique_id: int | None
    coord: tuple[float, float, float] | None


# ---------------------------------------------------------------------------
# MeasureInfo — a single measurement record within a DistSet
# ---------------------------------------------------------------------------


@dataclass
class MeasureInfo:
    """A single measurement entry inside a ``DistSet``.

    Mirrors the C++ ``CMeasureInfo`` struct (``layer2/DistSet.h``)::

        struct CMeasureInfo {
            int id[4];        // AtomInfoType.unique_id
            int offset;       // offset into this distance set's Coord list
            int state[4];     // save object state
            int measureType;  // distance, angle, or dihedral
        };

    During PyMOL session serialization ``measureType`` is **not** stored
    explicitly — it is reconstructed from ``len(ids)`` on load.  We store it
    explicitly on the Python side for clarity.
    """

    offset: int
    ids: list[int]
    states: list[int]
    measure_type: MeasureType = MeasureType.DIHEDRAL  # default for 4 atoms

    def __post_init__(self) -> None:
        if self.measure_type == MeasureType.DIHEDRAL and len(self.ids) != 4:
            # Auto-detect from ids length if not explicitly set
            self.measure_type = MeasureType.from_atom_count(len(self.ids))

    @classmethod
    def from_pylist(cls, item: Sequence[Any]) -> MeasureInfo:
        """Deserialize a Python list produced by ``MeasureInfoListAsPyList``.

        The PyList format is::

            [offset, [id0, ...], [state0, ...]]

        where the length of the ids list implies the measurement type
        (2 = distance, 3 = angle, 4 = dihedral).

        See ``layer2/DistSet.cpp:MeasureInfoListAsPyList``.
        """
        offset = int(item[0])
        ids = [int(x) for x in item[1]] if item[1] is not None else []
        states = [int(x) for x in item[2]] if item[2] is not None else []
        measure_type = MeasureType.from_atom_count(len(ids))
        return cls(offset=offset, ids=ids, states=states, measure_type=measure_type)

    @property
    def is_distance(self) -> bool:
        return self.measure_type == MeasureType.DISTANCE

    @property
    def is_angle(self) -> bool:
        return self.measure_type == MeasureType.ANGLE

    @property
    def is_dihedral(self) -> bool:
        return self.measure_type == MeasureType.DIHEDRAL


# ---------------------------------------------------------------------------
# DistSet — one "frame" of measurement coordinates
# ---------------------------------------------------------------------------


@dataclass
class DistSet:
    """One state / frame of measurement coordinates.

    **Despite its name, ``DistSet`` holds distances, angles, AND dihedrals**
    (the C++ code itself carries the comment: *"NOTE: 'Dist' names & symbols
    should be updated to 'Measurement'"*).

    Serialized as a 10-element Python list by ``DistSetAsPyList``::

        [0] NIndex            — number of distance vertices (2× num distances)
        [1] Coord             — flattened xyz coords for distance atoms
        [2] LabCoord          — label coords (None; recalculated on load)
        [3] NAngleIndex       — number of angle vertices (3× num angles)
        [4] AngleCoord        — flattened xyz coords for angle atoms
        [5] NDihedralIndex    — number of dihedral vertices (4× num dihedrals)
        [6] DihedralCoord     — flattened xyz coords for dihedral atoms
        [7] Setting           — always None (removed before BB 11/14)
        [8] LabPos            — label positions (list or None)
        [9] MeasureInfo       — list of ``[offset, [ids], [states]]`` sub-lists

    See ``layer2/DistSet.cpp:DistSetAsPyList`` and ``DistSetFromPyList``.
    """

    nindex: int = 0
    coord: list[float] | None = None
    labcoord: Any = None
    nangleindex: int = 0
    anglecoord: list[float] | None = None
    ndihedralindex: int = 0
    dihedralcoord: list[float] | None = None
    setting: Any = None
    labpos: list[Any] | None = None
    measure_info: list[MeasureInfo] = field(default_factory=list)

    # ---- factories ---------------------------------------------------------

    @classmethod
    def from_pylist(cls, py: Sequence[Any]) -> DistSet:
        """Deserialize from the 10-element Python list format."""
        if not isinstance(py, (list, tuple)):
            raise TypeError("DistSet.from_pylist expects a list or tuple")
        # pad with None for backwards-compat with shorter session formats
        py = list(py) + [None] * max(0, 10 - len(py))

        return cls(
            nindex=int(py[0]) if py[0] is not None else 0,
            coord=list(py[1]) if py[1] is not None else None,
            labcoord=py[2],
            nangleindex=int(py[3]) if py[3] is not None else 0,
            anglecoord=list(py[4]) if py[4] is not None else None,
            ndihedralindex=int(py[5]) if py[5] is not None else 0,
            dihedralcoord=list(py[6]) if py[6] is not None else None,
            setting=py[7],
            labpos=list(py[8]) if py[8] is not None else None,
            measure_info=[MeasureInfo.from_pylist(mi) for mi in py[9]] if py[9] is not None else [],
        )

    # ---- coordinate access -------------------------------------------------

    def _coord_array_for(self, measure_type: MeasureType) -> list[float] | None:
        """Return the coordinate array for a given measurement type."""
        if measure_type == MeasureType.DISTANCE:
            return self.coord
        if measure_type == MeasureType.ANGLE:
            return self.anglecoord
        return self.dihedralcoord

    def get_vertex_coords_for_measure(self, mi: MeasureInfo) -> list[tuple[float, float, float]]:
        """Return ``(x, y, z)`` triples for each atom in *mi*.

        Uses the correct coordinate array (distance / angle / dihedral)
        based on ``mi.measure_type``.  The *offset* is in units of
        **vertices** (not floats); each vertex is 3 consecutive floats.
        """
        arr = self._coord_array_for(mi.measure_type)
        if not arr:
            return []

        off = mi.offset
        coords: list[tuple[float, float, float]] = []
        base = off * 3  # convert vertex offset → float offset
        for i in range(len(mi.ids)):
            idx = base + i * 3
            if idx + 2 < len(arr):
                coords.append((float(arr[idx]), float(arr[idx + 1]), float(arr[idx + 2])))
            else:
                coords.append((math.nan, math.nan, math.nan))
        return coords

    # ---- measurement-type queries ------------------------------------------

    @property
    def has_distances(self) -> bool:
        return any(mi.is_distance for mi in self.measure_info)

    @property
    def has_angles(self) -> bool:
        return any(mi.is_angle for mi in self.measure_info)

    @property
    def has_dihedrals(self) -> bool:
        return any(mi.is_dihedral for mi in self.measure_info)

    @property
    def num_distances(self) -> int:
        return sum(1 for mi in self.measure_info if mi.is_distance)

    @property
    def num_angles(self) -> int:
        return sum(1 for mi in self.measure_info if mi.is_angle)

    @property
    def num_dihedrals(self) -> int:
        return sum(1 for mi in self.measure_info if mi.is_dihedral)


# ---------------------------------------------------------------------------
# Scene atom helpers (shared, non-duplicated)
# ---------------------------------------------------------------------------


def _get_object_list(cmd_module) -> list[str]:
    """Return all object names in the session, using the most robust API available."""
    try:
        if hasattr(cmd_module, "get_object_list"):
            return list(cmd_module.get_object_list())
        return list(cmd_module.get_names("objects"))
    except Exception:
        if hasattr(cmd_module, "get_names"):
            return list(cmd_module.get_names("objects"))
        return []


def _get_model_atoms(cmd_module, obj: str, state: int = -1):
    """Safely retrieve all atoms for *obj* via ``cmd.get_model``.

    Returns ``model.atom`` list or an empty list on failure.
    """
    try:
        model = cmd_module.get_model(obj, state=state)
    except Exception:
        try:
            model = cmd_module.get_model(obj)
        except Exception as exc:
            logging.debug("Skipping PyMOL object '%s': %s", obj, exc)
            return []
    return model.atom


def _atom_coord(a) -> tuple[float, float, float] | None:
    """Extract ``(x, y, z)`` from a PyMOL atom object."""
    if hasattr(a, "coord"):
        c = getattr(a, "coord")
        if isinstance(c, (list, tuple)) and len(c) >= 3:
            return (float(c[0]), float(c[1]), float(c[2]))
    if hasattr(a, "x") and hasattr(a, "y") and hasattr(a, "z"):
        try:
            return (float(getattr(a, "x")), float(getattr(a, "y")), float(getattr(a, "z")))
        except Exception:
            pass
    return None


def _atom_unique_id(a) -> int | None:
    """Extract ``unique_id`` from a PyMOL atom (only uses the explicit attribute)."""
    if hasattr(a, "unique_id"):
        try:
            return int(getattr(a, "unique_id"))
        except Exception:
            pass
    return None


def _make_atom_descriptor(obj: str, a) -> AtomDescriptor:
    """Build an ``AtomDescriptor`` from a PyMOL atom object."""
    atom_index = int(getattr(a, "index", -1))
    return AtomDescriptor(
        obj=obj,
        atom_index=atom_index,
        chain=_str_or_none(getattr(a, "chain", None)),
        segi=_str_or_none(getattr(a, "segi", None)),
        resi=_str_or_none(getattr(a, "resi", None)),
        resn=_str_or_none(getattr(a, "resn", None)),
        name=_str_or_none(getattr(a, "name", None)),
        unique_id=_atom_unique_id(a),
        coord=_atom_coord(a),
    )


def _str_or_none(value: Any) -> str | None:
    """Convert *value* to ``str``, returning ``None`` for ``None`` input."""
    return str(value) if value is not None else None


def build_scene_atom_list(cmd_module) -> list[AtomDescriptor]:
    """Return ``AtomDescriptor`` for every atom in the session (all objects)."""
    atom_list: list[AtomDescriptor] = []
    if cmd_module is None:
        return atom_list
    for obj in _get_object_list(cmd_module):
        for a in _get_model_atoms(cmd_module, obj):
            atom_list.append(_make_atom_descriptor(obj, a))
    return atom_list


def build_unique_id_map(cmd_module) -> dict[int, AtomDescriptor]:
    """Build ``{unique_id: AtomDescriptor}`` for all atoms that have a ``unique_id``."""
    mapping: dict[int, AtomDescriptor] = {}
    if cmd_module is None:
        return mapping
    for obj in _get_object_list(cmd_module):
        for a in _get_model_atoms(cmd_module, obj):
            uid = _atom_unique_id(a)
            if uid is not None:
                mapping[uid] = _make_atom_descriptor(obj, a)
    return mapping


def _nearest_atom_by_coord(
    target: tuple[float, float, float],
    atom_list: list[AtomDescriptor],
) -> tuple[AtomDescriptor, float] | None:
    """Return ``(atom, dist_sq)`` for the nearest atom to *target*, or ``None``."""
    best: tuple[AtomDescriptor, float] | None = None
    best_d2 = float("inf")
    tx, ty, tz = target
    for a in atom_list:
        if a.coord is None:
            continue
        dx = a.coord[0] - tx
        dy = a.coord[1] - ty
        dz = a.coord[2] - tz
        d2 = dx * dx + dy * dy + dz * dz
        if d2 < best_d2:
            best_d2 = d2
            best = (a, d2)
    return best


# ---------------------------------------------------------------------------
# Measurement — top-level measurement object
# ---------------------------------------------------------------------------


@dataclass
class Measurement:
    r"""A PyMOL measurement object (distance, angle, dihedral, or mixed).

    Parsed from a ``cmd.get_session()['names']`` entry whose ``obj_type == 4``
    (``cObjectMeasurement``).  Can contain multiple ``DistSet``\ s (one per
    state / frame).
    """

    name: str
    header: Any | None = None
    dsets: list[DistSet] = field(default_factory=list)
    raw_obj_pylist: list[Any] | None = None
    extra: Any | None = None

    _atoms_cache: list[AtomDescriptor] | None = None
    _atoms_cache_key: tuple[int, float] | None = None  # (scene_fingerprint, coord_tol)

    # ---- measurement-type queries ------------------------------------------

    @property
    def measurement_type(self) -> MeasureType | None:
        """Return the measurement type if all ``MeasureInfo`` entries agree.

        Returns ``None`` for mixed-type measurement objects or empty ones.
        """
        types: set[MeasureType] = set()
        for ds in self.dsets:
            for mi in ds.measure_info:
                types.add(mi.measure_type)
        if len(types) == 1:
            return next(iter(types))
        return None

    @property
    def is_distance(self) -> bool:
        return self.measurement_type == MeasureType.DISTANCE

    @property
    def is_angle(self) -> bool:
        return self.measurement_type == MeasureType.ANGLE

    @property
    def is_dihedral(self) -> bool:
        return self.measurement_type == MeasureType.DIHEDRAL

    @property
    def is_mixed(self) -> bool:
        """``True`` when the object contains more than one measurement type."""
        return self.measurement_type is None and self._has_any_measure_info()

    def _has_any_measure_info(self) -> bool:
        return any(ds.measure_info for ds in self.dsets)

    @property
    def num_measurements(self) -> int:
        r"""Total number of ``MeasureInfo`` entries across all ``DistSet``\ s."""
        return sum(len(ds.measure_info) for ds in self.dsets)

    def _count_by_type(self, mt: MeasureType) -> int:
        return sum(1 for ds in self.dsets for mi in ds.measure_info if mi.measure_type == mt)

    @property
    def num_distances(self) -> int:
        return self._count_by_type(MeasureType.DISTANCE)

    @property
    def num_angles(self) -> int:
        return self._count_by_type(MeasureType.ANGLE)

    @property
    def num_dihedrals(self) -> int:
        return self._count_by_type(MeasureType.DIHEDRAL)

    # ---- value computation -------------------------------------------------

    def get_value(self, mi: MeasureInfo, ds: DistSet) -> float:
        """Compute the measurement value for a single ``MeasureInfo``.

        - **distance**: Euclidean distance between the 2 atoms (Å).
        - **angle**: bond angle defined by 3 atoms (degrees).
        - **dihedral**: dihedral (torsion) angle defined by 4 atoms (degrees).
        """
        coords = ds.get_vertex_coords_for_measure(mi)
        if mi.is_distance:
            return self._compute_distance(coords)
        if mi.is_angle:
            return self._compute_angle(coords)
        return self._compute_dihedral(coords)

    @staticmethod
    def _compute_distance(
        coords: list[tuple[float, float, float]],
    ) -> float:
        if len(coords) < 2:
            return math.nan
        a, b = coords[0], coords[1]
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)

    @staticmethod
    def _compute_angle(
        coords: list[tuple[float, float, float]],
    ) -> float:
        """Compute bond angle in degrees (atom1-atom2-atom3)."""
        if len(coords) < 3:
            return math.nan
        a, b, c = coords[0], coords[1], coords[2]
        ba = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
        bc = (c[0] - b[0], c[1] - b[1], c[2] - b[2])
        dot = ba[0] * bc[0] + ba[1] * bc[1] + ba[2] * bc[2]
        norm_ba = math.sqrt(ba[0] ** 2 + ba[1] ** 2 + ba[2] ** 2)
        norm_bc = math.sqrt(bc[0] ** 2 + bc[1] ** 2 + bc[2] ** 2)
        if norm_ba < 1e-10 or norm_bc < 1e-10:
            return math.nan
        cos_theta = max(-1.0, min(1.0, dot / (norm_ba * norm_bc)))
        return math.degrees(math.acos(cos_theta))

    @staticmethod
    def _compute_dihedral(
        coords: list[tuple[float, float, float]],
    ) -> float:
        """Compute dihedral angle in degrees (atom1-atom2-atom3-atom4).

        Uses the standard atan2 formula from computational chemistry.
        """
        if len(coords) < 4:
            return math.nan
        a, b, c, d = coords[0], coords[1], coords[2], coords[3]
        b1 = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
        b2 = (c[0] - b[0], c[1] - b[1], c[2] - b[2])
        b3 = (d[0] - c[0], d[1] - c[1], d[2] - c[2])
        # normals to the planes
        n1 = (
            b1[1] * b2[2] - b1[2] * b2[1],
            b1[2] * b2[0] - b1[0] * b2[2],
            b1[0] * b2[1] - b1[1] * b2[0],
        )
        n2 = (
            b2[1] * b3[2] - b2[2] * b3[1],
            b2[2] * b3[0] - b2[0] * b3[2],
            b2[0] * b3[1] - b2[1] * b3[0],
        )
        norm_n1 = math.sqrt(n1[0] ** 2 + n1[1] ** 2 + n1[2] ** 2)
        norm_n2 = math.sqrt(n2[0] ** 2 + n2[1] ** 2 + n2[2] ** 2)
        if norm_n1 < 1e-10 or norm_n2 < 1e-10:
            return math.nan
        cos_phi = (n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2]) / (norm_n1 * norm_n2)
        cos_phi = max(-1.0, min(1.0, cos_phi))
        # sign via b2·(n1×n2)
        cross = (
            n1[1] * n2[2] - n1[2] * n2[1],
            n1[2] * n2[0] - n1[0] * n2[2],
            n1[0] * n2[1] - n1[1] * n2[0],
        )
        sign = 1.0 if (b2[0] * cross[0] + b2[1] * cross[1] + b2[2] * cross[2]) >= 0 else -1.0
        return math.degrees(sign * math.acos(cos_phi))

    # ---- atom resolution ---------------------------------------------------

    def _collect_unique_ids(self) -> list[int]:
        """Collect all unique atom ids across all measure entries, preserving order."""
        seen: set[int] = set()
        result: list[int] = []
        for ds in self.dsets:
            for mi in ds.measure_info:
                for uid in mi.ids:
                    if uid is not None and uid not in seen:
                        seen.add(uid)
                        result.append(int(uid))
        return result

    @staticmethod
    def _scene_fingerprint(cmd_module) -> int:
        """Cheap scene fingerprint from object names — changes when objects change."""
        try:
            return hash(tuple(sorted(_get_object_list(cmd_module))))
        except Exception:
            return 0

    def atoms(self, cmd_module=None, coord_tol: float = 0.9) -> list[AtomDescriptor]:
        """Resolve measurement atoms to ``AtomDescriptor`` objects.

        Resolution strategy (in order of preference):
          1. Direct ``unique_id`` lookup (fast and unambiguous).
          2. Coordinate-based nearest-neighbor search within *coord_tol* (Å).

        Results are cached and only recomputed when the scene fingerprint or
        *coord_tol* changes.

        Parameters
        ----------
        cmd_module:
            The ``pymol.cmd`` module (defaults to ``pymol.cmd``).
        coord_tol:
            Coordinate tolerance in Å for nearest-neighbor matching.
        """
        if cmd_module is None:
            cmd_module = cmd

        fingerprint = self._scene_fingerprint(cmd_module)
        cache_key = (fingerprint, coord_tol)
        if self._atoms_cache is not None and self._atoms_cache_key == cache_key:
            return self._atoms_cache

        unique_ids = self._collect_unique_ids()
        if not unique_ids:
            self._atoms_cache = []
            self._atoms_cache_key = cache_key
            return []

        # Build lookup structures once
        scene_atoms = build_scene_atom_list(cmd_module)
        unique_map: dict[int, AtomDescriptor] = {a.unique_id: a for a in scene_atoms if a.unique_id is not None}

        # Also build a per-measure-info lookup: uid → vertex coordinate
        uid_to_coord: dict[int, tuple[float, float, float]] = {}
        for ds in self.dsets:
            for mi in ds.measure_info:
                coords = ds.get_vertex_coords_for_measure(mi)
                for j, uid in enumerate(mi.ids):
                    if uid is not None and uid not in uid_to_coord and j < len(coords):
                        uid_to_coord[uid] = coords[j]

        resolved: list[AtomDescriptor] = []
        for uid in unique_ids:
            # 1. Direct unique_id mapping
            if uid in unique_map:
                resolved.append(unique_map[uid])
                continue

            # 2. Coordinate-based fallback
            found_coord = uid_to_coord.get(uid)
            if found_coord is None:
                resolved.append(AtomDescriptor("(unresolved)", -1, None, None, None, None, None, uid, None))
                continue

            best = _nearest_atom_by_coord(found_coord, scene_atoms)
            if best is not None:
                atom_descr, d2 = best
                if math.sqrt(d2) <= coord_tol:
                    if atom_descr.unique_id is None:
                        atom_descr = AtomDescriptor(
                            obj=atom_descr.obj,
                            atom_index=atom_descr.atom_index,
                            chain=atom_descr.chain,
                            segi=atom_descr.segi,
                            resi=atom_descr.resi,
                            resn=atom_descr.resn,
                            name=atom_descr.name,
                            unique_id=uid,
                            coord=atom_descr.coord,
                        )
                    resolved.append(atom_descr)
                    continue

            resolved.append(AtomDescriptor("(unresolved)", -1, None, None, None, None, None, uid, found_coord))

        self._atoms_cache = resolved
        self._atoms_cache_key = cache_key
        return resolved

    def atoms_for_entry(
        self, mi: MeasureInfo, ds: DistSet, cmd_module=None, coord_tol: float = 0.9
    ) -> list[AtomDescriptor]:
        """Resolve atoms for a single ``MeasureInfo`` + ``DistSet`` pair.

        Unlike ``atoms()``, this does not de-duplicate across entries and
        preserves per-entry ordering.  The result is NOT cached.
        """
        if cmd_module is None:
            cmd_module = cmd

        scene_atoms = build_scene_atom_list(cmd_module)
        unique_map: dict[int, AtomDescriptor] = {a.unique_id: a for a in scene_atoms if a.unique_id is not None}
        coords = ds.get_vertex_coords_for_measure(mi)

        resolved: list[AtomDescriptor] = []
        for j, uid in enumerate(mi.ids):
            if uid is not None and uid in unique_map:
                resolved.append(unique_map[uid])
                continue

            # coordinate fallback
            if j < len(coords):
                found_coord = coords[j]
                best = _nearest_atom_by_coord(found_coord, scene_atoms)
                if best is not None:
                    atom_descr, d2 = best
                    if math.sqrt(d2) <= coord_tol:
                        if atom_descr.unique_id is None:
                            atom_descr = AtomDescriptor(
                                obj=atom_descr.obj,
                                atom_index=atom_descr.atom_index,
                                chain=atom_descr.chain,
                                segi=atom_descr.segi,
                                resi=atom_descr.resi,
                                resn=atom_descr.resn,
                                name=atom_descr.name,
                                unique_id=uid,
                                coord=atom_descr.coord,
                            )
                        resolved.append(atom_descr)
                        continue

            resolved.append(AtomDescriptor("(unresolved)", -1, None, None, None, None, None, uid, None))
        return resolved

    # ---- serialization -----------------------------------------------------

    @classmethod
    def from_names_entry(cls, entry: Sequence[Any]) -> Measurement | None:
        """Parse a single entry from ``cmd.get_session()['names']``.

        The entry format (from ``ExecutiveGetExecObjectAsPyList``)::

            [name, cExecObject(=1), visible, None, objType, objectPyList, groupName]

        For measurement objects ``objType == cObjectMeasurement == 4`` and
        ``objectPyList`` is the ``ObjectDistAsPyList`` result (4 elements)::

            [ObjectHeader, DSetCount, [DistSetPyList, ...], 0]
        """
        if not isinstance(entry, (list, tuple)) or len(entry) < 6:
            return None

        name = str(entry[0]) if entry[0] is not None else ""
        obj_type = entry[4] if len(entry) > 4 else None
        obj_pylist = entry[5] if len(entry) > 5 else None

        # cObjectMeasurement == 4
        if obj_type == 4 and isinstance(obj_pylist, (list, tuple)):
            return cls._from_object_dist_pylist(name, list(obj_pylist))

        # Fallback: maybe entry *is* the ObjectDistAsPyList directly
        if len(entry) >= 3 and isinstance(entry[2], (list, tuple)):
            return cls._from_object_dist_pylist("", list(entry))

        return None

    @classmethod
    def _from_object_dist_pylist(cls, name: str, raw: list[Any]) -> Measurement:
        """Parse from the ``ObjectDistAsPyList`` 4-element list."""
        header = raw[0] if len(raw) > 0 else None
        dset_pylist = raw[2] if len(raw) > 2 else None

        dsets: list[DistSet] = []
        if isinstance(dset_pylist, (list, tuple)):
            for ds_item in dset_pylist:
                if ds_item is None:
                    continue
                dsets.append(DistSet.from_pylist(ds_item))

        # Try to derive name from header if not provided
        if not name:
            try:
                if isinstance(header, (list, tuple)) and len(header) > 1 and isinstance(header[1], str):
                    name = header[1]
            except Exception as exc:
                logging.debug("Could not derive name from header %r: %s", header, exc)

        return cls(name=name, header=header, dsets=dsets, raw_obj_pylist=raw)

    @classmethod
    def from_session_names(cls, names: Iterable[Sequence[Any]]) -> list[Measurement]:
        """Parse all measurement objects from a ``get_session()['names']`` list."""
        out: list[Measurement] = []
        for entry in names:
            try:
                m = cls.from_names_entry(entry)
            except Exception as e:
                logging.warning("Failed to load measurement entry %r: %s", entry, e)
                continue
            if m is not None:
                out.append(m)
        return out

    # ---- display -----------------------------------------------------------

    def summarize(self, cmd_module=None) -> str:
        """Human-readable summary of the measurement object."""
        mt = self.measurement_type
        type_label = mt.name if mt else "mixed"
        lines = [
            f"Measurement: {self.name!r}",
            f"  Type: {type_label}",
            f"  DistSets (frames): {len(self.dsets)}",
            f"  Total entries: {self.num_measurements}",
        ]
        if self.num_distances:
            lines.append(f"    distances: {self.num_distances}")
        if self.num_angles:
            lines.append(f"    angles: {self.num_angles}")
        if self.num_dihedrals:
            lines.append(f"    dihedrals: {self.num_dihedrals}")

        atoms = self.atoms(cmd_module=cmd_module)
        if atoms:
            lines.append("  Atoms:")
            for a in atoms:
                lines.append(
                    f"    uid={a.unique_id}, obj={a.obj}, idx={a.atom_index}, "
                    f"chain={a.chain}, segi={a.segi}, "
                    f"resi={a.resi}, resn={a.resn}, name={a.name}"
                )

        for i, ds in enumerate(self.dsets):
            lines.append(
                f"  DistSet[{i}]: nDist={ds.nindex}, nAngle={ds.nangleindex}, " f"nDihedral={ds.ndihedralindex}"
            )
            for mi in ds.measure_info:
                mtype = mi.measure_type.name
                val = self.get_value(mi, ds)
                val_str = f"{val:.3f}" if not math.isnan(val) else "N/A"
                lines.append(f"    [{mtype}] offset={mi.offset}, ids={mi.ids}, " f"states={mi.states}, value={val_str}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Extended PyMOL command: read_measurement
# ---------------------------------------------------------------------------

# Gromacs index group documentation:
#
#  0 System              : 113812 atoms
#  1 Protein             :  8773 atoms
#  2 Protein-H           :  4414 atoms
#  3 C-alpha             :   594 atoms
#  4 Backbone            :  1782 atoms
#  5 MainChain           :  2375 atoms
#  6 MainChain+Cb        :  2902 atoms
#  7 MainChain+H         :  2941 atoms
#  8 SideChain           :  5832 atoms
#  9 SideChain-H         :  2039 atoms
# 10 Prot-Masses         :  8773 atoms
# 11 non-Protein         : 105039 atoms
# 12 Other               :   140 atoms
# 13 FAD                 :    84 atoms ; case by case
# 14 C18                 :    56 atoms ; case by case
# 15 NA                  :     4 atoms ; according to system
# 16 Water               : 104895 atoms
# 17 SOL                 : 104895 atoms
# 18 non-Water           :  8917 atoms
# 19 Ion                 :     4 atoms
# 20 Water_and_ions      : 104899 atoms
# 21 Protein_FAD_C18     :  8913 atoms ; case by case


def _gmx_group_for_resn(resn: str | None) -> str:
    """Return the Gromacs index group number string for a residue name.

    ``4`` = Backbone (used for GLY), ``8`` = SideChain (all other residues).
    """
    if resn == "GLY":
        return "4"
    return "8"


def read_measurement(start: str | int = 0, debug: int = 0) -> list[Measurement]:
    """Read measurement objects from the PyMOL session and print Gromacs index strings.

    For each measurement atom, this prints a Gromacs ``make_ndx``-style
    selection and ``name`` command, following the convention:

    - ``4 & r <resi>`` for glycine backbone atoms
    - ``8 & r <resi>`` for non-glycine sidechain atoms

    Works with distance (2 atoms), angle (3 atoms), and dihedral (4 atoms)
    measurements.

    Parameters
    ----------
    start : str or int
        Starting index for Gromacs group numbering.
    debug : int
        If non-zero, print debug summaries for each measurement.

    Returns
    -------
    list[Measurement]
        All parsed measurement objects.
    """
    DEBUG = bool(int(debug))
    start_idx = int(start)

    session = cmd.get_session()
    measurements = Measurement.from_session_names(session["names"])

    if not measurements:
        raise ValueError("No measurement objects found in session")

    seen_labels: set[str] = set()
    all_entries: list[tuple[str, tuple[str, ...]]] = []  # (meas_name, (label0, label1, ...))

    for m in measurements:
        if DEBUG:
            print("-=" * 30)
            print(f"[DEBUG] {m.summarize(cmd)}")

        for ds in m.dsets:
            for mi in ds.measure_info:
                entry_atoms = m.atoms_for_entry(mi, ds, cmd)
                labels_tuple = tuple(f"r{a.resi}" for a in entry_atoms)
                all_entries.append((m.name, labels_tuple))

                for a in entry_atoms:
                    label = f"r{a.resi}"
                    if label in seen_labels:
                        if DEBUG:
                            print(f"[DEBUG] skipping {a.resi} to avoid duplicates")
                        continue
                    seen_labels.add(label)

                    start_idx += 1
                    group = _gmx_group_for_resn(a.resn)
                    print(f"{group} & r {a.resi}")
                    print(f"name {start_idx} {label}")

        if DEBUG:
            m_entries = [e for name, e in all_entries if name == m.name]
            print(f"[DEBUG] {m.name} {m_entries}")
            print("-=" * 30)

    if DEBUG:
        print(f"[DEBUG] all_entries: {all_entries}")
        print("-=" * 30)

    # Print Gromacs-style summary labels (one per entry)
    names = [f"'{name}'" for name, _ in all_entries]
    print(f"labels=({' '.join(names)})")

    # Print atom group lists for each position across all entries
    max_atoms = max((len(entry) for _, entry in all_entries), default=2)
    for pos in range(max_atoms):
        grp_values = []
        for _, entry in all_entries:
            grp_values.append(f"'{entry[pos]}'" if pos < len(entry) else "''")
        suffix = chr(ord("a") + pos) if pos < 26 else f"_{pos}"
        print(f"grp_{suffix}s=({' '.join(grp_values)})")

    return measurements


cmd.extend("read_measurement", read_measurement)

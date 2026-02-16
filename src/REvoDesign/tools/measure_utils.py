"""
# Read Measurement from a PyMOL session and print Gromacs index input strings.

**Author: Yinying Yao**
**Date: 2026-02-03**

Github Copilot was prompted to generate all the contents below based on the codebase of the pymol-open-source repository.
- ref: https://github.com/schrodinger/pymol-open-source/blob/462dd320b8db5e4bed300a068edd1555b7accd5b/layer2/ObjectDist.cpp#L321

# Original Prompts:
- explain the cObjectMeasurement object structure and it's representation at cmd.get_session()['names'] list.
- create a python  dataclass `Measurement` to represent the object. create a classmethod to serialize measurement objects from the cmd.get_session()['names'] list
- a property like `atoms` (a list of atoms) would be nice for `Measurement` object, if one need to find the atoms (object/chain/segment/resi/resn/atom-index, etc.)

# Known Issues:
1. The code is not well commented.
2. The code currently only works on distance measurements.
3. The code is currently an experimental prototype and lacks comprehensive testing.


# Usage:
1. run this script in pymol console: `run /path/to/measure.py`
2. call the extended command: `read_measurement [start,[debug]]`
"""

# TODO:
# 1. refactor the code to make it more readable and maintainable, simple and clean
# 2. read non-distance measurements
# 3. Tests and cases.
# 4. add regex measurement object name filter: `read_measurement  <filter-string>,[start,[debug]]`, default is '(all)'


"""
# Code for Gromacs indexing system

  0 System              : 113812 atoms
  1 Protein             :  8773 atoms
  2 Protein-H           :  4414 atoms
  3 C-alpha             :   594 atoms
  4 Backbone            :  1782 atoms
  5 MainChain           :  2375 atoms
  6 MainChain+Cb        :  2902 atoms
  7 MainChain+H         :  2941 atoms
  8 SideChain           :  5832 atoms
  9 SideChain-H         :  2039 atoms
 10 Prot-Masses         :  8773 atoms
 11 non-Protein         : 105039 atoms
 12 Other               :   140 atoms
 13 FAD                 :    84 atoms ; case by case
 14 C18                 :    56 atoms ; case by case
 15 NA                  :     4 atoms ; according to system
 16 Water               : 104895 atoms
 17 SOL                 : 104895 atoms
 18 non-Water           :  8917 atoms
 19 Ion                 :     4 atoms
 20 Water_and_ions      : 104899 atoms
 21 Protein_FAD_C18     :  8913 atoms ; case by case

 nr : group      '!': not  'name' nr name   'splitch' nr    Enter: list groups
 'a': atom       '&': and  'del' nr         'splitres' nr   'l': list residues
 't': atom type  '|': or   'keep' nr        'splitat' nr    'h': help
 'r': residue              'res' nr         'chain' char
 "name": group             'case': case sensitive           'q': save and quit
 'ri': residue index


"""


import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from pymol import cmd

"""
A proper measure object looks like this:


m=[
    'measure1', 0, 1, None, 4, 
    [
        [
            4, 
            'measure1', 
            7, 
            2060287, 
            [-25.08300018310547, 68.54199981689453, -9.894000053405762], # a2 coords
            [-8.956000328063965, 78.06800079345703, -7.281000137329102], # a1 coords
            1, 0, None, 1, 0, 
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            , 0, None
        ], 1, 
        [
            [
                4, 
                [
                    -8.956000328063965, 
                    68.54199981689453, 
                    -7.281000137329102, 
                    
                    -25.08300018310547, 
                    78.06800079345703, 
                    -9.894000053405762, 

                    -8.956000328063965, 
                    68.54199981689453, 
                    -7.281000137329102, 
                    
                    -25.08300018310547, 
                    78.06800079345703, 
                    -9.894000053405762
                ], 
                None, 0, None, 0, None, None, None, 
                [
                    [2, [1, 2], [0, 0]], 
                    [0, [1, 2], [0, 0]]
                ]
            ]
        ], 0
    ], 
    ''
] 

"""


@dataclass
class MeasureInfo:
    offset: int
    ids: list[int]
    states: list[int]

    @classmethod
    def from_pylist(cls, item: Sequence[Any]) -> "MeasureInfo":
        offset = int(item[0])
        ids = [int(x) for x in item[1]] if item[1] is not None else []
        states = [int(x) for x in item[2]] if item[2] is not None else []
        return cls(offset=offset, ids=ids, states=states)


# the following case only works w/ distances
#


@dataclass
class DistSet:
    nindex: int
    coord: Optional[list[float]] = None
    labcoord: Optional[Any] = None
    nangleindex: int = 0
    anglecoord: Optional[list[float]] = None
    ndihedralindex: int = 0
    dihedralcoord: Optional[list[float]] = None
    setting: Optional[Any] = None
    labpos: Optional[list[Any]] = None
    measure_info: list[MeasureInfo] = field(default_factory=list)

    @classmethod
    def from_pylist(cls, py: Sequence[Any]) -> "DistSet":
        if not isinstance(py, (list, tuple)):
            raise TypeError("DistSet.from_pylist expects a list or tuple")
        py = list(py) + [None] * max(0, 10 - len(py))
        nindex = int(py[0]) if py[0] is not None else 0
        coord = list(py[1]) if py[1] is not None else None
        labcoord = py[2]
        nangleindex = int(py[3]) if py[3] is not None else 0
        anglecoord = list(py[4]) if py[4] is not None else None
        ndihedralindex = int(py[5]) if py[5] is not None else 0
        dihedralcoord = list(py[6]) if py[6] is not None else None
        setting = py[7]
        labpos = list(py[8]) if py[8] is not None else None
        measure_info_list = []
        if py[9] is not None:
            for mi in py[9]:
                measure_info_list.append(MeasureInfo.from_pylist(mi))
        return cls(
            nindex=nindex,
            coord=coord,
            labcoord=labcoord,
            nangleindex=nangleindex,
            anglecoord=anglecoord,
            ndihedralindex=ndihedralindex,
            dihedralcoord=dihedralcoord,
            setting=setting,
            labpos=labpos,
            measure_info=measure_info_list,
        )

    def get_vertex_coords_for_measure(self, mi: MeasureInfo) -> list[tuple[float, float, float]]:
        """
        Return list of (x,y,z) triples for a given MeasureInfo using measureType implied
        by ids length:
          - 2 => use self.coord
          - 3 => use self.anglecoord
          - 4 => use self.dihedralcoord
        offset is the index into the corresponding flattened array (in units of vertex triples).
        """
        ids_len = len(mi.ids)
        if ids_len == 2:
            arr = self.coord
        elif ids_len == 3:
            arr = self.anglecoord
        else:
            arr = self.dihedralcoord
        if not arr:
            return []
        off = mi.offset
        coords = []
        base = off * 3
        for i in range(ids_len):
            idx = base + i * 3
            if idx + 2 < len(arr):
                coords.append((float(arr[idx]), float(arr[idx + 1]), float(arr[idx + 2])))
            else:
                coords.append((math.nan, math.nan, math.nan))
        return coords


@dataclass
class AtomDescriptor:
    obj: str
    atom_index: int  # index of atom within object (0-based)
    chain: Optional[str]
    segi: Optional[str]
    resi: Optional[str]
    resn: Optional[str]
    name: Optional[str]
    unique_id: Optional[int]
    coord: Optional[tuple[float, float, float]]


# --- helper to build global atom list once ---
def _build_scene_atom_list(cmd_module):
    """
    Return a list of AtomDescriptor for all atoms in the scene (all objects).
    This uses only reliable attributes from cmd.get_model() atom objects.
    """
    atom_list: list[AtomDescriptor] = []
    if cmd_module is None:
        return atom_list

    # get object list robustly
    try:
        if hasattr(cmd_module, "get_object_list"):
            objects = list(cmd_module.get_object_list())
        else:
            objects = list(cmd_module.get_names("objects"))
    except Exception:
        objects = list(cmd_module.get_names("objects")) if hasattr(cmd_module, "get_names") else []

    for obj in objects:
        try:
            model = cmd_module.get_model(obj, state=-1)
        except Exception:
            try:
                model = cmd_module.get_model(obj)
            except Exception:
                continue
        for a in model.atom:
            # coords
            coord = None
            if hasattr(a, "coord"):
                c = getattr(a, "coord")
                if isinstance(c, (list, tuple)) and len(c) >= 3:
                    coord = (float(c[0]), float(c[1]), float(c[2]))
            elif hasattr(a, "x") and hasattr(a, "y") and hasattr(a, "z"):
                try:
                    coord = (float(getattr(a, "x")), float(getattr(a, "y")), float(getattr(a, "z")))
                except Exception:
                    coord = None

            # prefer explicit unique_id attribute; do NOT fall back to 'id' or 'serial'
            unique_id = None
            if hasattr(a, "unique_id"):
                try:
                    unique_id = int(getattr(a, "unique_id"))
                except Exception:
                    unique_id = None

            atom_index = int(getattr(a, "index", -1))
            chain = getattr(a, "chain", None)
            segi = getattr(a, "segi", None)
            resi = getattr(a, "resi", None)
            resn = getattr(a, "resn", None)
            name = getattr(a, "name", None)

            atom_list.append(
                AtomDescriptor(
                    obj=obj,
                    atom_index=atom_index,
                    chain=str(chain) if chain is not None else None,
                    segi=str(segi) if segi is not None else None,
                    resi=str(resi) if resi is not None else None,
                    resn=str(resn) if resn is not None else None,
                    name=str(name) if name is not None else None,
                    unique_id=unique_id,
                    coord=coord,
                )
            )

    return atom_list


# --- nearest neighbor helper ---
def _nearest_atom_by_coord(target: tuple[float, float, float], atom_list: list[AtomDescriptor]):
    best = None
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
    return best  # (AtomDescriptor, d2) or None


@dataclass
class Measurement:
    name: str
    header: Optional[Any] = None
    dsets: list[DistSet] = field(default_factory=list)
    raw_obj_pylist: Optional[list[Any]] = None
    extra: Optional[Any] = None

    _atoms_cache: Optional[list[AtomDescriptor]] = None

    def _collect_unique_ids(self) -> list[int]:
        unique_ids = []
        for ds in self.dsets:
            for mi in ds.measure_info:
                for uid in mi.ids:
                    if uid is not None:
                        unique_ids.append(int(uid))
        seen = set()
        result = []
        for u in unique_ids:
            if u not in seen:
                seen.add(u)
                result.append(u)
        return result

    def atoms(self, cmd_module=None, coord_tol=0.9) -> list[AtomDescriptor]:
        """
        Resolve measurement atoms to AtomDescriptor objects.
        - cmd_module: the pymol.cmd module (optional; uses global cmd)
        - coord_tol: coordinate tolerance (Å) for matching measurement vertex to scene atom
        """
        if self._atoms_cache is not None:
            return self._atoms_cache

        if cmd_module is None:
            cmd_module = cmd

        unique_ids = self._collect_unique_ids()
        # Build scene atom list once
        scene_atoms = _build_scene_atom_list(cmd_module)

        # Build a map unique_id -> AtomDescriptor only when atom.unique_id is present
        unique_map: dict[int, AtomDescriptor] = {}
        for a in scene_atoms:
            if a.unique_id is not None:
                unique_map[a.unique_id] = a

        resolved: list[AtomDescriptor] = []
        for uid in unique_ids:
            # prefer direct mapping (only uses a.unique_id, no ambiguous fallbacks)
            if uid in unique_map:
                resolved.append(unique_map[uid])
                continue

            # coordinate-based fallback: find a vertex coordinate for this uid from DistSets
            found_coord = None
            for ds in self.dsets:
                for mi in ds.measure_info:
                    if uid in mi.ids:
                        coords = ds.get_vertex_coords_for_measure(mi)
                        if coords:
                            # position in ids order -> corresponding coords index
                            try:
                                pos_idx = mi.ids.index(uid)
                                if pos_idx < len(coords):
                                    found_coord = coords[pos_idx]
                                    break
                            except ValueError:
                                continue
                if found_coord is not None:
                    break

            if found_coord is None:
                # can't resolve at all
                resolved.append(AtomDescriptor("(unresolved)", -1, None, None, None, None, None, uid, None))
                continue

            # nearest atom in scene
            best = _nearest_atom_by_coord(found_coord, scene_atoms)
            if best:
                atom_descr, d2 = best
                dist = math.sqrt(d2)
                if dist <= coord_tol:
                    # good match
                    # ensure returned descriptor includes the unique_id we expected (if absent, set it)
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
            # nothing matched within tolerance
            resolved.append(AtomDescriptor("(unresolved)", -1, None, None, None, None, None, uid, found_coord))

        self._atoms_cache = resolved
        return resolved

    @classmethod
    def from_names_entry(cls, entry: Sequence[Any]) -> Optional["Measurement"]:
        if not isinstance(entry, (list, tuple)):
            return None
        name = entry[0] if len(entry) > 0 and isinstance(entry[0], str) else ""
        obj_type = entry[4] if len(entry) > 4 else None
        obj_pylist = entry[5] if len(entry) > 5 else None
        # measurement type in C++ is cObjectMeasurement == 4
        if obj_type == 4 and isinstance(obj_pylist, (list, tuple)):
            raw_obj_pylist = list(obj_pylist)
            header = raw_obj_pylist[0] if len(raw_obj_pylist) > 0 else None
            dset_pylist = raw_obj_pylist[2] if len(raw_obj_pylist) > 2 else None
            dsets = []
            if isinstance(dset_pylist, (list, tuple)):
                for ds_item in dset_pylist:
                    if ds_item is None:
                        continue
                    dsets.append(DistSet.from_pylist(ds_item))
            return cls(name=name or "", header=header, dsets=dsets, raw_obj_pylist=raw_obj_pylist)
        # fallback: maybe entry is already the ObjectDistAsPyList
        if len(entry) >= 3 and isinstance(entry[2], (list, tuple)):
            raw_obj_pylist = list(entry)
            header = raw_obj_pylist[0]
            dset_pylist = raw_obj_pylist[2]
            dsets = []
            if isinstance(dset_pylist, (list, tuple)):
                for ds_item in dset_pylist:
                    if ds_item is None:
                        continue
                    dsets.append(DistSet.from_pylist(ds_item))
            derived_name = ""
            try:
                if isinstance(header, (list, tuple)) and len(header) > 1 and isinstance(header[1], str):
                    derived_name = header[1]
            except Exception:
                pass
            return cls(name=derived_name, header=header, dsets=dsets, raw_obj_pylist=raw_obj_pylist)
        return None

    @classmethod
    def from_session_names(cls, names: Iterable[Sequence[Any]]) -> list["Measurement"]:
        out = []
        for entry in names:
            try:
                m = cls.from_names_entry(entry)
            except Exception as e:
                print(f"Failed to load measurement {entry}: {e}")
                m = None
            if m:
                out.append(m)
        return out

    def _build_uniqueid_to_atom_map(self, cmd_module) -> dict[int, AtomDescriptor]:
        """
        Build mapping unique_id -> AtomDescriptor by iterating over all objects & atoms.
        Uses cmd.get_model(obj, state=-1) to collect object atoms.
        This depends on the PyMOL Atomic object exposing attributes that include 'unique_id' or similar.
        """
        mapping: dict[int, AtomDescriptor] = {}
        if cmd_module is None:
            return mapping

        # Get all object names in the session
        try:
            # cmd.get_object_list() is available in newer PyMOL; fallback to cmd.get_names for 'objects'
            if hasattr(cmd_module, "get_object_list"):
                obj_list = list(cmd_module.get_object_list())
            else:
                obj_list = list(cmd_module.get_names("objects"))
        except Exception:
            obj_list = list(cmd_module.get_names("objects")) if hasattr(cmd_module, "get_names") else []

        for obj in obj_list:
            try:
                model = cmd_module.get_model(obj, state=-1)  # full model, all atoms
            except Exception:
                # fallback: try without state arg
                try:
                    model = cmd_module.get_model(obj)
                except Exception:
                    continue
            # model.atom is list of Atom objects; attributes vary with PyMOL version.
            for a in model.atom:
                # try several attribute names for unique id and coords
                unique_id = None
                coord = None
                atom_index = getattr(a, "index", None)
                # Common names that may exist: 'unique_id', 'uniq', 'id', 'serial' - check them
                for attr in ("unique_id", "uniq", "id", "serial"):
                    if hasattr(a, attr):
                        try:
                            unique_id = int(getattr(a, attr))
                            break
                        except Exception:
                            pass
                # coords
                if hasattr(a, "coord"):
                    try:
                        c = getattr(a, "coord")
                        if isinstance(c, (list, tuple)) and len(c) >= 3:
                            coord = (float(c[0]), float(c[1]), float(c[2]))
                    except Exception:
                        coord = None
                elif hasattr(a, "x") and hasattr(a, "y") and hasattr(a, "z"):
                    try:
                        coord = (float(getattr(a, "x")), float(getattr(a, "y")), float(getattr(a, "z")))
                    except Exception:
                        coord = None

                chain = getattr(a, "chain", None)
                segi = getattr(a, "segi", None)
                resi = getattr(a, "resi", None)
                resn = getattr(a, "resn", None)
                name = getattr(a, "name", None)

                if unique_id is not None:
                    mapping[unique_id] = AtomDescriptor(
                        obj=obj,
                        atom_index=int(atom_index) if atom_index is not None else -1,
                        chain=str(chain) if chain is not None else None,
                        segi=str(segi) if segi is not None else None,
                        resi=str(resi) if resi is not None else None,
                        resn=str(resn) if resn is not None else None,
                        name=str(name) if name is not None else None,
                        unique_id=unique_id,
                        coord=coord,
                    )
        return mapping

    @staticmethod
    def _distance_sq(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2

    def _resolve_by_coords(
        self, uid: int, target_coord: tuple[float, float, float], cmd_module
    ) -> Optional[AtomDescriptor]:
        """
        Fallback: find the nearest atom in the entire scene to target_coord.
        Returns AtomDescriptor or None.
        """
        if cmd_module is None:
            return None

        best = None
        best_d2 = float("inf")
        try:
            # iterate all objects and atoms (similar to map building above)
            if hasattr(cmd_module, "get_object_list"):
                obj_list = list(cmd_module.get_object_list())
            else:
                obj_list = list(cmd_module.get_names("objects"))
        except Exception:
            obj_list = list(cmd_module.get_names("objects")) if hasattr(cmd_module, "get_names") else []

        for obj in obj_list:
            try:
                model = cmd_module.get_model(obj, state=-1)
            except Exception:
                try:
                    model = cmd_module.get_model(obj)
                except Exception:
                    continue
            for a in model.atom:
                # get atom coords
                coord = None
                if hasattr(a, "coord"):
                    c = getattr(a, "coord")
                    if isinstance(c, (list, tuple)) and len(c) >= 3:
                        coord = (float(c[0]), float(c[1]), float(c[2]))
                elif hasattr(a, "x") and hasattr(a, "y") and hasattr(a, "z"):
                    coord = (float(getattr(a, "x")), float(getattr(a, "y")), float(getattr(a, "z")))
                if coord is None:
                    continue
                d2 = self._distance_sq(coord, target_coord)
                if d2 < best_d2:
                    best_d2 = d2
                    best = AtomDescriptor(
                        obj=obj,
                        atom_index=int(getattr(a, "index", -1)),
                        chain=str(getattr(a, "chain", None)) if getattr(a, "chain", None) is not None else None,
                        segi=str(getattr(a, "segi", None)) if getattr(a, "segi", None) is not None else None,
                        resi=str(getattr(a, "resi", None)) if getattr(a, "resi", None) is not None else None,
                        resn=str(getattr(a, "resn", None)) if getattr(a, "resn", None) is not None else None,
                        name=str(getattr(a, "name", None)) if getattr(a, "name", None) is not None else None,
                        unique_id=None,
                        coord=coord,
                    )
        # Optionally: ignore matches that are far away (very large distance)
        if best is not None:
            return best
        return None

    def summarize(self, cmd_module=None) -> str:
        lines = [f"Measurement: {self.name} ({len(self.dsets)} DistSet(s))"]
        atoms = self.atoms(cmd_module=cmd_module)
        lines.append("Atoms:")
        for a in atoms:
            lines.append(
                f"  unique_id={a.unique_id}, object={a.obj}, atom_index={a.atom_index}, "
                f"chain={a.chain}, segi={a.segi}, resi={a.resi}, resn={a.resn}, name={a.name}, coord={a.coord}"
            )
        # per-distset summary
        for i, ds in enumerate(self.dsets):
            lines.append(f"DistSet {i}: nindex={ds.nindex}, nangle={ds.nangleindex}, ndihedral={ds.ndihedralindex}")
            for mi in ds.measure_info:
                mtype = {2: "distance", 3: "angle", 4: "dihedral"}.get(len(mi.ids), "unknown")
                lines.append(f"  {mtype}: ids={mi.ids}, states={mi.states}, offset={mi.offset}")
        return "\n".join(lines)


#


def read_measurement(start: str | int, debug: int = 0) -> Measurement:
    """
    This function reads the measurement from the PyMOL session and prints atoms as gromacs index strings.

    Parameters
    start : str or int
        The starting atom index.
    debug : bool int, optional
        If non-zero, prints debug information. The default is 0.


    ```
    9 & r 111 ; select the non-glycine residue sidechain group at 111
    name 2 r111 ; rename it from 2 to r111
    8 & r 514 ; select the glycine residue backbone group at 514
    name 3 r514 ; rename it from 3 to r514
    ```
    """
    DEBUG = bool(int(debug))

    start = int(start)
    from pymol import cmd

    atoms: dict[int, str] = {}
    pairs: dict = {}

    session = cmd.get_session()
    hits = Measurement.from_session_names(session["names"])

    if not hits:
        raise ValueError(
            f"measurement not found in session {[m.name for m in hits]}",
        )

    for hit in hits:
        if DEBUG:
            print("-=" * 30)
            print(f"[DEBUG] {hit.summarize(cmd)}")
        pair = []
        for a in hit.atoms(cmd):
            #
            pair.append(f"r{a.resi}")

            if f"r{a.resi}" in atoms.values():
                if DEBUG:
                    print(f"[DEBUG] skiping {a.resi} to avoid duplicates")
                continue

            start += 1

            print(f'{"8" if a.resn == "GLY" else "9"} & r {a.resi}')
            print(f"name {start} r{a.resi}")

            atoms[start] = f"r{a.resi}"

        pairs[hit.name] = pair
        if DEBUG:
            print(f"[DEBUG] {hit.name} {pair}")
            print("-=" * 30)

    if DEBUG:
        print(pairs)
        print("-=" * 30)
    # re-organize the strings
    names = [f"'{x}'" for x in pairs.keys()]
    atom_a = [f"'{x[0]}'" for x in pairs.values()]
    atom_b = [f"'{x[1]}'" for x in pairs.values()]

    print(f'labels=({" ".join(names)})')
    print(f'grp_as=({" ".join(atom_a)})')
    print(f'grp_bs=({" ".join(atom_b)})')

    return hits


cmd.extend("read_measurement", read_measurement)

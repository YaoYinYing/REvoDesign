# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Authoritative normalization for stateful scientific workspaces."""

from __future__ import annotations

import re
from typing import Any

_FIXED = re.compile(r"^([A-Za-z])(-?\d+)-(-?\d+)$")
_GENERATED = re.compile(r"^(\d+)-(\d+)$")
_HOTSPOT = re.compile(r"^([A-Za-z])(-?\d+)$")
_MODES = {"unconditional", "motif_scaffolding", "binder", "expert"}


class WorkspaceValidationError(ValueError):
    """A user-correctable workspace normalization failure."""


def _segment(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkspaceValidationError("Every contig segment must be an object")
    kind = value.get("kind")
    if kind == "chain_break":
        return {"kind": "chain_break"}
    if kind == "generated":
        minimum = value.get("min_length")
        maximum = value.get("max_length")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or not isinstance(maximum, int):
            raise WorkspaceValidationError("Generated segment lengths must be integers")
        if minimum < 1 or maximum < minimum or maximum > 10000:
            raise WorkspaceValidationError("Generated segment length range is invalid")
        return {"kind": "generated", "min_length": minimum, "max_length": maximum}
    if kind == "fixed":
        chain = str(value.get("chain") or "")
        start = value.get("start")
        end = value.get("end")
        if len(chain) != 1 or not chain.isalpha() or not isinstance(start, int) or not isinstance(end, int):
            raise WorkspaceValidationError("Fixed segments require a one-letter chain and integer range")
        if end < start:
            raise WorkspaceValidationError("Fixed segment end must not precede its start")
        if end - start + 1 > 10000:
            raise WorkspaceValidationError("Fixed segment range must not exceed 10000 residues")
        return {"kind": "fixed", "chain": chain, "start": start, "end": end}
    raise WorkspaceValidationError(f"Unknown contig segment kind: {kind!r}")


def parse_contig(raw: str) -> list[dict[str, Any]]:
    """Parse the pinned RFdiffusion contig subset used by the guided editor."""
    text = str(raw or "").strip().strip("[]")
    if not text:
        raise WorkspaceValidationError("Contig must not be blank")
    segments: list[dict[str, Any]] = []
    tokens = re.split(r"(/0(?:\s+|$)|/)", text)
    for token in tokens:
        token = token.strip()
        if not token or token == "/":
            continue
        if token == "/0":
            segments.append({"kind": "chain_break"})
            continue
        generated = _GENERATED.fullmatch(token)
        fixed = _FIXED.fullmatch(token)
        if generated:
            segments.append(
                _segment({"kind": "generated", "min_length": int(generated[1]), "max_length": int(generated[2])})
            )
        elif fixed:
            segments.append(
                _segment({"kind": "fixed", "chain": fixed[1], "start": int(fixed[2]), "end": int(fixed[3])})
            )
        else:
            raise WorkspaceValidationError(f"Unsupported contig token: {token!r}")
    return segments


def serialize_contig(segments: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for segment in segments:
        normalized = _segment(segment)
        if normalized["kind"] == "chain_break":
            if not parts or parts[-1] == "/0":
                raise WorkspaceValidationError("Chain breaks must separate contig segments")
            parts.append("/0")
        elif normalized["kind"] == "generated":
            parts.append(f"{normalized['min_length']}-{normalized['max_length']}")
        else:
            parts.append(f"{normalized['chain']}{normalized['start']}-{normalized['end']}")
    if not parts or parts[-1] == "/0":
        raise WorkspaceValidationError("Contig must contain a segment after each chain break")
    return "/".join(parts).replace("//0/", "/0 ")


def normalize_rfdiffusion(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkspaceValidationError("RFdiffusion workspace state must be an object")
    mode = value.get("mode")
    if mode not in _MODES:
        raise WorkspaceValidationError(f"Unknown RFdiffusion mode: {mode!r}")
    segments = (
        parse_contig(value.get("raw_contig", ""))
        if mode == "expert"
        else [_segment(v) for v in value.get("segments", [])]
    )
    hotspots: list[dict[str, Any]] = []
    for item in value.get("hotspots", []):
        if isinstance(item, str):
            match = _HOTSPOT.fullmatch(item)
            if not match:
                raise WorkspaceValidationError(f"Invalid hotspot: {item!r}")
            item = {"chain": match[1], "residue": int(match[2])}
        if (
            not isinstance(item, dict)
            or len(str(item.get("chain") or "")) != 1
            or not isinstance(item.get("residue"), int)
        ):
            raise WorkspaceValidationError("Hotspots require a chain and integer residue")
        hotspots.append({"chain": str(item["chain"]), "residue": item["residue"]})
    kinds = [item["kind"] for item in segments]
    if mode == "unconditional" and hotspots:
        raise WorkspaceValidationError("Hotspots are not supported in unconditional mode")
    if mode == "unconditional" and kinds != ["generated"]:
        raise WorkspaceValidationError("Unconditional mode requires exactly one generated segment")
    if mode == "motif_scaffolding" and "fixed" not in kinds:
        raise WorkspaceValidationError("Motif scaffolding requires at least one fixed segment")
    if mode == "binder":
        if "fixed" not in kinds or "chain_break" not in kinds or "generated" not in kinds or not hotspots:
            missing = []
            if "fixed" not in kinds:
                missing.append('target residues — select them in the viewer and press "Use selection as target"')
            if not hotspots:
                missing.append('hotspot residues — select them in the viewer and press "Use selection as hotspots"')
            if "chain_break" not in kinds or "generated" not in kinds:
                missing.append("a binder length")
            raise WorkspaceValidationError("Binder design needs " + " and ".join(missing))
    contig = serialize_contig(segments)
    return {
        "state": {
            "version": 1,
            "mode": mode,
            "segments": segments,
            "hotspots": hotspots,
            "raw_contig": contig if mode == "expert" else None,
        },
        "params": {
            "design_mode": mode,
            "contig": contig,
            "hotspot_res": "[" + ",".join(f"{h['chain']}{h['residue']}" for h in hotspots) + "]" if hotspots else "",
        },
        "summary": f"{mode.replace('_', ' ').title()}: {contig}",
    }


def normalize_capability(task_type: str, syntax: str, value: Any) -> dict[str, Any]:
    if task_type == "rfdiffusion" and syntax == "rfdiffusion":
        return normalize_rfdiffusion(value)
    raise WorkspaceValidationError("This workspace capability has no server normalizer")


def validate_rfdiffusion_structure(normalized: dict[str, Any], primary_path: str | None) -> None:
    """Cross-check guided residue references against the validated PDB."""
    state = normalized["state"]
    if state["mode"] == "unconditional":
        return
    references = {
        (item["chain"], residue)
        for item in state["segments"]
        if item["kind"] == "fixed"
        for residue in range(item["start"], item["end"] + 1)
    }
    references.update((item["chain"], item["residue"]) for item in state["hotspots"])
    if not references:
        return
    if not primary_path:
        raise WorkspaceValidationError("This RFdiffusion mode requires a primary PDB")
    present: set[tuple[str, int]] = set()
    with open(primary_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            try:
                present.add(((line[21:22].strip() or "_"), int(line[22:26].strip())))
            except ValueError:
                continue
    missing = sorted(references - present)
    if missing:
        preview = ", ".join(f"{chain}{residue}" for chain, residue in missing[:8])
        raise WorkspaceValidationError(f"Selected residues are absent from the primary PDB: {preview}")

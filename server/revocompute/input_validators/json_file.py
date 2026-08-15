# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""JSON content validator (DoS caps only, no schema checks)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from revocompute.input_validators.common import MAX_JSON_BYTES, MAX_JSON_DEPTH, MAX_JSON_NODES


def _json_stats(root: Any) -> tuple[int, int]:
    """Return ``(node_count, max_depth)`` with an iterative stack walk."""
    nodes = 0
    depth = 0
    stack: list[tuple[Any, int]] = [(root, 1)]
    while stack:
        node, level = stack.pop()
        nodes += 1
        if level > depth:
            depth = level
        if isinstance(node, dict):
            stack.extend((child, level + 1) for child in node.values())
        elif isinstance(node, list):
            stack.extend((child, level + 1) for child in node)
    return nodes, depth


def validate_json(path: str) -> str | None:
    """Return an error message if *path* is not parseable JSON within caps.

    Complexity caps only — no schema checks; any well-formed JSON document
    passes.
    """
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return f"Could not read uploaded JSON file: {exc}"
    if b"\0" in data:
        return "Uploaded JSON file contains binary content (NUL byte)"
    if len(data) > MAX_JSON_BYTES:
        return f"JSON file exceeds the {MAX_JSON_BYTES // (1024 * 1024)} MiB input limit"
    try:
        value = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return "Uploaded JSON file is not valid UTF-8 text"
    except (json.JSONDecodeError, ValueError, RecursionError):
        return "Uploaded file does not appear to be valid JSON"
    nodes, depth = _json_stats(value)
    if nodes > MAX_JSON_NODES:
        return f"JSON file contains more than {MAX_JSON_NODES} values"
    if depth > MAX_JSON_DEPTH:
        return f"JSON file is nested deeper than {MAX_JSON_DEPTH} levels"
    return None

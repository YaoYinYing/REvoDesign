# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Generate the HMAC manifest for the PyMOL installer Gist."""

from __future__ import annotations

import argparse
import hmac
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANAGER_PATH = REPO_ROOT / "src" / "REvoDesign" / "tools" / "package_manager.py"
ASSET_PATHS = {
    "REvoDesign_PyMOL.py": MANAGER_PATH,
    "REvoDesign-PyMOL-entry.ui": REPO_ROOT / "src" / "REvoDesign" / "UI" / "REvoDesign-PyMOL-entry.ui",
    "REvoDesignExtrasTableRich.json": REPO_ROOT / "jsons" / "REvoDesignExtrasTableRich.json",
}
HMAC_KEY_PATTERN = re.compile(r"_MANAGER_HMAC_KEY\s*=\s*bytes\.fromhex\(\s*['\"]([a-fA-F0-9]+)['\"]\s*\)")


def extract_hmac_key(manager_path: Path = MANAGER_PATH) -> bytes:
    """Extract the public installer HMAC key without importing PyMOL dependencies."""
    match = HMAC_KEY_PATTERN.search(manager_path.read_text())
    if match is None:
        raise ValueError(f"_MANAGER_HMAC_KEY not found in {manager_path}")
    return bytes.fromhex(match.group(1))


def generate_manifest() -> dict[str, str]:
    """Return installer asset names mapped to their HMAC-SHA256 digests."""
    key = extract_hmac_key()
    return {name: hmac.new(key, path.read_bytes(), "sha256").hexdigest() for name, path in ASSET_PATHS.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Path to the generated JSON manifest")
    args = parser.parse_args(argv)

    manifest = generate_manifest()
    rendered_manifest = json.dumps(manifest, indent=2)
    args.output.write_text(rendered_manifest + "\n")
    print(f"Manifest: {rendered_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

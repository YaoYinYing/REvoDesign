#!/usr/bin/env python3
# stage_translate.py — shared stderr->stage translator for runner wrappers.
#
# Rewrites tool stderr lines into the existing stdout stage protocol:
# every input line is passed through to stderr unchanged, and lines matching
# a family's pattern file emit "REVODESIGN_STAGE:<marker>" on stdout.
#
# Usage:  tool ... 2> >(python3 /app/revocompute/stage_translate.py \
#                       /app/revocompute/<family>.stages >&1)
#
# Pattern file format: "marker:regex" per line; # comments and blank lines
# ignored.
#
# Python, not awk: mawk (Debian's default) holds pipe input until EOF no
# matter how it is configured, which froze every stage marker until the
# scientific tool exited.

from __future__ import annotations

import re
import sys

patterns = []
with open(sys.argv[1], encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        marker, regex = line.split(":", 1)
        try:
            patterns.append((marker, re.compile(regex)))
        except re.error:
            continue

for line in sys.stdin:
    sys.stderr.write(line)
    sys.stderr.flush()
    for marker, regex in patterns:
        if regex.search(line):
            print(f"REVODESIGN_STAGE:{marker}", flush=True)

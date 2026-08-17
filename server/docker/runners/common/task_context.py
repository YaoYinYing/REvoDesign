# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Runner protocol v2 — read the task manifest (TASK_MANIFEST env path).

Usage: task_context.py param <name> [default]   # prints one param value
       task_context.py primary                  # prints files[0]["path"]
       task_context.py files                    # prints the files list as JSON

Kept old-Python compatible: the GREMLIN runner's conda environment is
Python 3.6, so no annotations, f-strings, or newer py3 syntax here.
"""

import json
import os
import sys

manifest = json.load(open(os.environ["TASK_MANIFEST"]))
command = sys.argv[1] if len(sys.argv) > 1 else ""

if command == "param":
    key = sys.argv[2] if len(sys.argv) > 2 else ""
    default = sys.argv[3] if len(sys.argv) > 3 else ""
    value = manifest.get("params", {}).get(key, default)
    print(str(value).lower() if isinstance(value, bool) else value)
elif command == "primary":
    print(manifest["files"][0]["path"])
elif command == "files":
    print(json.dumps(manifest["files"]))
else:
    sys.stderr.write(f"task_context.py: unknown command {command!r}\n")
    sys.exit(2)

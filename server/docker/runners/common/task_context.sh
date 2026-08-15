#!/usr/bin/env bash
# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only
#
# Runner protocol v2 — shared task-manifest helpers.
# Copied next to run.sh in every runner image and sourced by run.sh:
#   source /app/revocompute/task_context.sh
# (Tests may point at the repo copies via TASK_CONTEXT_SRC.)

if [[ -z "${TASK_MANIFEST:-}" ]]; then
  echo "task_context.sh: TASK_MANIFEST is not set" >&2
  exit 1
fi

_task_context_dir="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

_parse_param() {
  python3 "$_task_context_dir/task_context.py" param "$1" "${2:-}"
}

primary_input() {
  python3 "$_task_context_dir/task_context.py" primary
}

task_input_files() {
  python3 "$_task_context_dir/task_context.py" files
}

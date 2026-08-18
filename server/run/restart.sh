#!/usr/bin/env bash

# Thin entry over the Python control module.  All logic lives in
# revocompute_ctl/ — run `bash server/run/restart.sh --help` for usage.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

exec python3 -m revocompute_ctl "$@"

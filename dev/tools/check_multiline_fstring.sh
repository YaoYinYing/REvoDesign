#!/usr/bin/env bash
# Reject PEP 701 multi-line f-strings — project targets Python 3.10+.
# Black reformats long f-strings by splitting them at {expr} boundaries,
# creating f-strings where the opening f" is on one line and the closing
# " on the next. This is Python 3.12+ only.

set -euo pipefail

DIR="$(cd "$(dirname "$0")/../.." && pwd)"
VIOLATIONS=0

while IFS= read -r line; do
    echo "$line"
    VIOLATIONS=$((VIOLATIONS + 1))
done < <(grep -rn 'f"[^"]*{$' "$DIR"/src "$DIR"/tests --include='*.py' 2>/dev/null || true)

while IFS= read -r line; do
    echo "$line"
    VIOLATIONS=$((VIOLATIONS + 1))
done < <(grep -rn "f'[^']*{$" "$DIR"/src "$DIR"/tests --include='*.py' 2>/dev/null || true)

if [ "$VIOLATIONS" -gt 0 ]; then
    echo ""
    echo "Multi-line f-strings (PEP 701) require Python 3.12+. Project targets 3.10+."
    echo "Split into implicit concatenation: f\"prefix {\" f\"expr} suffix\""
    exit 1
fi

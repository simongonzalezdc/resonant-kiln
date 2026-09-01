#!/bin/sh
# Canonical Kiln extraction runner (A4 pipeline fix).
# Rerun rule: regenerate via these scripts, diff vs previous, never hand-edit.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
for script in extract_machine_wall.py extract_hands_on.py extract_throughput.py; do
    [ -f "$script" ] || { echo "missing $script"; exit 1; }
done
for f in ../kiln-extract-20260901.json ../kiln-hands-on-extract-20260901.json ../kiln-throughput-extract.json; do
    [ -f "$f" ] && cp "$f" "$f.prev"
done
python3 extract_machine_wall.py
python3 extract_hands_on.py
python3 extract_throughput.py
echo "--- diffs vs previous (empty = identical):"
for f in ../kiln-extract-20260901.json ../kiln-hands-on-extract-20260901.json ../kiln-throughput-extract.json; do
    if [ -f "$f.prev" ]; then
        diff "$f.prev" "$f" >/dev/null && echo "  $(basename $f): identical" || echo "  $(basename $f): CHANGED (review diff: diff $f.prev $f)"
    fi
done

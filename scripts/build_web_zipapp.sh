#!/usr/bin/env bash
# Build docs/spl-run.pyz for the browser webapp (Pyodide loads this zipapp).
# Requires: Python >= 3.9

set -euo pipefail

# --- sanity ---
command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
python3 - <<'PY' >/dev/null || { echo "Python 3.9+ required" >&2; exit 1; }
import sys; assert (sys.version_info.major, sys.version_info.minor) >= (3,9)
PY

ROOT="$(pwd)"
DIST_STAGING="dist_spl"
OUT_DIR="docs"
OUT_ZIP="${OUT_DIR}/spl-run.pyz"

# --- clean staging ---
rm -rf "$DIST_STAGING"
mkdir -p "$DIST_STAGING"/spl/src/{parser,interpreter,relations}

# --- ensure packages in staging ---
touch "$DIST_STAGING/spl/__init__.py"
touch "$DIST_STAGING/spl/src/__init__.py"

# --- copy required modules (edit if you add dependencies) ---
cp -f spl/src/parser/parser.py                              "$DIST_STAGING/spl/src/parser/parser.py"

cp -f spl/src/interpreter/interpret_spl.py                  "$DIST_STAGING/spl/src/interpreter/"
cp -f spl/src/interpreter/interpret_spl_functions.py        "$DIST_STAGING/spl/src/interpreter/"
cp -f spl/src/interpreter/interpret_spl_affine.py           "$DIST_STAGING/spl/src/interpreter/"
cp -f spl/src/interpreter/interpret_spl_sets.py             "$DIST_STAGING/spl/src/interpreter/"

cp -f spl/src/relations/"affine_relations.py"               "$DIST_STAGING/spl/src/relations/"
cp -f spl/src/relations/"set_relations.py"                  "$DIST_STAGING/spl/src/relations/"
cp -f spl/src/relations/"set_functions.py"                  "$DIST_STAGING/spl/src/relations/"

# --- optional: minimal __main__ (zipapp runnable on desktop; ignored by web) ---
cat > "$DIST_STAGING/__main__.py" <<'PYZ'
print("SPL zipapp for the web. Import via sys.path and call runner.run_spl(src).")
PYZ

# --- build zipapp into docs/ ---
mkdir -p "$OUT_DIR"
python3 -m zipapp "$DIST_STAGING" -o "$OUT_ZIP" -p "/usr/bin/env python3"

# --- make Pages serve nested paths cleanly ---
: > "$OUT_DIR/.nojekyll"

# --- copy example next to webapp if desired (comment out if you manage separately) ---
if [ -f spl/programs/teleportation.spl ]; then
  cp -f spl/programs/teleportation.spl "$OUT_DIR/teleportation.spl"
fi

# --- report ---
echo "Built: $OUT_ZIP"
python3 - <<PY
import zipfile, sys
z = zipfile.ZipFile("$OUT_ZIP")
mods = sorted(p for p in z.namelist() if p.endswith(".py"))
print("Contents (py files):")
for m in mods: print("  ", m)
PY


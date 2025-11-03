#!/usr/bin/env bash
# Build docs/spl-run.pyz with embedded runner and vendored lark for the web app.
# Usage: bash scripts/build_web_zipapp.sh
set -euo pipefail

# Verbose mode: set VERBOSE=1 to enable 'set -x'
if [[ "${VERBOSE:-0}" == "1" ]]; then set -x; fi

# --- locate repo root ---
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
if ROOT="$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
cd "$ROOT"

echo "[info] repo root: $ROOT"

# --- sanity checks ---
command -v python3 >/dev/null || { echo "[error] python3 not found"; exit 1; }
python3 - <<'PY' >/dev/null || { echo "[error] Python 3.9+ required"; exit 1; }
import sys; assert (sys.version_info.major, sys.version_info.minor) >= (3,9)
PY

# Source files we expect (edit here if your layout changes)
SRC_FILES=(
  "spl/src/parser/parser.py"
  "spl/src/interpreter/interpret_spl.py"
  "spl/src/interpreter/interpret_spl_functions.py"
  "spl/src/interpreter/interpret_spl_affine.py"
  "spl/src/interpreter/interpret_spl_sets.py"
  "spl/src/relations/affine_relations.py"
  "spl/src/relations/set_relations.py"
  "spl/src/relations/set_functions.py"
)
EXAMPLE_FILE="spl/programs/teleportation.spl"

missing=0
for f in "${SRC_FILES[@]}"; do
  if [[ ! -f "$f" ]]; then echo "[error] missing source: $f"; missing=1; fi
done
if [[ ! -f "$EXAMPLE_FILE" ]]; then echo "[warn] example not found: $EXAMPLE_FILE (the page will still work, but the load button will be empty)"; fi
if [[ "$missing" == "1" ]]; then exit 1; fi

DIST_STAGING="$ROOT/dist_spl"
OUT_DIR="$ROOT/docs"
OUT_ZIP="$OUT_DIR/spl-run.pyz"

echo "[step] clean staging"
rm -rf "$DIST_STAGING"
mkdir -p "$DIST_STAGING"/spl/src/{parser,interpreter,relations}

echo "[step] ensure packages"
: > "$DIST_STAGING/spl/__init__.py"
: > "$DIST_STAGING/spl/src/__init__.py"

echo "[step] copy interpreter tree"
cp -f spl/src/parser/parser.py                              "$DIST_STAGING/spl/src/parser/parser.py"
cp -f spl/src/interpreter/interpret_spl.py                  "$DIST_STAGING/spl/src/interpreter/"
cp -f spl/src/interpreter/interpret_spl_functions.py        "$DIST_STAGING/spl/src/interpreter/"
cp -f spl/src/interpreter/interpret_spl_affine.py           "$DIST_STAGING/spl/src/interpreter/"
cp -f spl/src/interpreter/interpret_spl_sets.py             "$DIST_STAGING/spl/src/interpreter/"
cp -f spl/src/relations/affine_relations.py                 "$DIST_STAGING/spl/src/relations/"
cp -f spl/src/relations/set_relations.py                    "$DIST_STAGING/spl/src/relations/"
cp -f spl/src/relations/set_functions.py                    "$DIST_STAGING/spl/src/relations/"

echo "[step] vendor pure-Python deps"
# Pin to 1.x (pure python). If you need a specific version, change below.
python3 -m pip install --upgrade --target "$DIST_STAGING" "lark>=1.1,<2"

# Verify lark is present
python3 - <<PY "$DIST_STAGING"
import os, sys
root = sys.argv[1]
ok = os.path.isfile(os.path.join(root,'lark','__init__.py'))
print("[check] lark present:", ok)
assert ok, "lark not vendored into staging"
PY

echo "[step] embed runner and __main__"
cat > "$DIST_STAGING/runner.py" <<'PY'
# Internal runner module: importable as 'runner' from inside the zipapp
def run_spl(src: str) -> str:
    from spl.src.parser.parser import parse_spl
    from spl.src.interpreter.interpret_spl import interpret_spl
    prog = parse_spl(src)
    out = interpret_spl(prog)
    return out if isinstance(out, str) else str(out)
PY

cat > "$DIST_STAGING/__main__.py" <<'PY'
# Optional desktop entry (not used by the browser)
import sys
from runner import run_spl
def _read(p):
    return sys.stdin.read() if p == "-" else open(p, "r", encoding="utf-8").read()
if __name__ == "__main__":
    if len(sys.argv) > 1: print(run_spl(_read(sys.argv[1])))
    else: print("SPL zipapp for the web; Pyodide adds '/spl-run.pyz' to sys.path and calls runner.run_spl(src).")
PY

echo "[step] build zipapp"
mkdir -p "$OUT_DIR"
python3 -m zipapp "$DIST_STAGING" -o "$OUT_ZIP" -p "/usr/bin/env python3"

echo "[step] stage website extras"
: > "$OUT_DIR/.nojekyll"
if [[ -f "$EXAMPLE_FILE" ]]; then
  cp -f "$EXAMPLE_FILE" "$OUT_DIR/teleportation.spl"
fi

echo "[step] sanity-list zip contents"
python3 - <<'PY' "$OUT_ZIP"
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = set(z.namelist())
req = {
  "runner.py",
  "spl/src/parser/parser.py",
  "spl/src/interpreter/interpret_spl.py",
  "lark/__init__.py",
}
missing = [r for r in req if r not in names]
print("[check] missing in zip:", missing)
assert not missing, "required files missing in zipapp"
print("[ok]", sys.argv[1], "ready")
PY

echo "[done] Built $OUT_ZIP"


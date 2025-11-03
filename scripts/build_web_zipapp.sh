#!/usr/bin/env bash
# Build docs/spl-run.pyz with an internal runner module for the web app.
# Run from anywhere: bash scripts/build_web_zipapp.sh

set -euo pipefail

# --- locate repo root ---
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
if ROOT="$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null)"; then :; else ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"; fi
cd "$ROOT"

# --- sanity ---
command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
python3 - <<'PY' >/dev/null || { echo "Python 3.9+ required" >&2; exit 1; }
import sys; assert (sys.version_info.major, sys.version_info.minor) >= (3,9)
PY

DIST_STAGING="$ROOT/dist_spl"
OUT_DIR="$ROOT/docs"
OUT_ZIP="$OUT_DIR/spl-run.pyz"

echo "[1/5] Clean staging"
rm -rf "$DIST_STAGING"
mkdir -p "$DIST_STAGING"/spl/src/{parser,interpreter,relations}

echo "[2/5] Ensure packages"
: > "$DIST_STAGING/spl/__init__.py"
: > "$DIST_STAGING/spl/src/__init__.py"

echo "[3/5] Copy interpreter tree"
cp -f spl/src/parser/parser.py                              "$DIST_STAGING/spl/src/parser/parser.py"
cp -f spl/src/interpreter/interpret_spl.py                  "$DIST_STAGING/spl/src/interpreter/"
cp -f spl/src/interpreter/interpret_spl_functions.py        "$DIST_STAGING/spl/src/interpreter/"
cp -f spl/src/interpreter/interpret_spl_affine.py           "$DIST_STAGING/spl/src/interpreter/"
cp -f spl/src/interpreter/interpret_spl_sets.py             "$DIST_STAGING/spl/src/interpreter/"
cp -f spl/src/relations/affine_relations.py                 "$DIST_STAGING/spl/src/relations/"
cp -f spl/src/relations/set_relations.py                    "$DIST_STAGING/spl/src/relations/"
cp -f spl/src/relations/set_functions.py                    "$DIST_STAGING/spl/src/relations/"

echo "[4/5] Add internal runner and optional __main__"
cat > "$DIST_STAGING/runner.py" <<'PY'
# Internal web runner: importable as 'runner' from inside the zipapp
def run_spl(src: str) -> str:
    # Import inside to surface errors to the UI
    from spl.src.parser.parser import parse_spl
    from spl.src.interpreter.interpret_spl import interpret_spl
    prog = parse_spl(src)
    out = interpret_spl(prog)
    return out if isinstance(out, str) else str(out)
PY

cat > "$DIST_STAGING/__main__.py" <<'PY'
# Optional: desktop usage for the zipapp (not used by the browser)
import sys
from runner import run_spl
def _read(p): 
    return sys.stdin.read() if p == "-" else open(p, "r", encoding="utf-8").read()
if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(run_spl(_read(sys.argv[1])))
    else:
        print("SPL zipapp. In the browser, Pyodide imports '/spl-run.pyz' and uses runner.run_spl(src).")
PY

echo "[5/5] Build zipapp and stage web assets"
mkdir -p "$OUT_DIR"
python3 -m zipapp "$DIST_STAGING" -o "$OUT_ZIP" -p "/usr/bin/env python3"
: > "$OUT_DIR/.nojekyll"

# keep example next to the web UI for convenience
if [ -f spl/programs/teleportation.spl ]; then
  cp -f spl/programs/teleportation.spl "$OUT_DIR/teleportation.spl"
fi

echo "Built: $OUT_ZIP"


#!/usr/bin/env bash
# Build docs/spl-run.pyz with embedded runner and vendored lark for the web app.
set -euo pipefail

# --- locate repo root ---
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
if ROOT="$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null)"; then :; else ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"; fi
cd "$ROOT"

command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
python3 - <<'PY' >/dev/null || { echo "Python 3.9+ required" >&2; exit 1; }
import sys; assert (sys.version_info.major, sys.version_info.minor) >= (3,9)
PY

DIST_STAGING="$ROOT/dist_spl"
OUT_DIR="$ROOT/docs"
OUT_ZIP="$OUT_DIR/spl-run.pyz"

echo "[1/7] Clean staging"
rm -rf "$DIST_STAGING"
mkdir -p "$DIST_STAGING"/spl/src/{parser,interpreter,relations}

echo "[2/7] Ensure packages"
: > "$DIST_STAGING/spl/__init__.py"
: > "$DIST_STAGING/spl/src/__init__.py"

echo "[3/7] Copy interpreter tree"
cp -f spl/src/parser/parser.py                              "$DIST_STAGING/spl/src/parser/parser.py"
cp -f spl/src/interpreter/interpret_spl.py                  "$DIST_STAGING/spl/src/interpreter/" || true
cp -f spl/src/interpreter/interpret_spl_functions.py        "$DIST_STAGING/spl/src/interpreter/" || true
cp -f spl/src/interpreter/interpret_spl_affine.py           "$DIST_STAGING/spl/src/interpreter/" || true
cp -f spl/src/interpreter/interpret_spl_sets.py             "$DIST_STAGING/spl/src/interpreter/" || true
cp -f spl/src/interpreter/__init__.py                       "$DIST_STAGING/spl/src/interpreter/" || : > "$DIST_STAGING/spl/src/interpreter/__init__.py"
cp -f spl/src/relations/affine_relations.py                 "$DIST_STAGING/spl/src/relations/" || true
cp -f spl/src/relations/set_relations.py                    "$DIST_STAGING/spl/src/relations/" || true
cp -f spl/src/relations/set_functions.py                    "$DIST_STAGING/spl/src/relations/" || true

echo "[4/7] Vendor lark (pure Python)"
python3 -m pip install --upgrade --target "$DIST_STAGING" "lark>=1.1,<2"

echo "[5/7] Embed robust runner and minimal __main__"
cat > "$DIST_STAGING/runner.py" <<'PY'
# Auto-discover parser & interpreter entry points at runtime.

from __future__ import annotations
import importlib
from types import ModuleType
from typing import Callable, Optional, Tuple

_PARSER_CANDIDATES = [
    ("spl.src.parser.parser",         ["parse_spl", "parse"]),
]

_INTERP_CANDIDATES = [
    # most likely
    ("spl.src.interpreter.interpret_spl",        ["interpret_spl", "interpret_program", "interpret_to_text", "interpret", "run"]),
    # fallbacks
    ("spl.src.interpreter",                      ["interpret_spl", "interpret_program", "interpret_to_text", "interpret", "run"]),
    ("spl.interpreter",                          ["interpret_spl", "interpret_program", "interpret_to_text", "interpret", "run"]),
]

def _first_callable(modname: str, names: list[str]) -> Optional[Tuple[ModuleType, str, Callable]]:
    try:
        m = importlib.import_module(modname)
    except Exception:
        return None
    for n in names:
        fn = getattr(m, n, None)
        if callable(fn):
            return (m, n, fn)
    return None

def _resolve() -> Tuple[Callable[[str], object], Callable[[object], object], str, str]:
    parser_fn = None
    parser_where = ""
    for mod, names in _PARSER_CANDIDATES:
        hit = _first_callable(mod, names)
        if hit:
            _, n, fn = hit
            parser_fn = fn
            parser_where = f"{mod}.{n}"
            break
    if parser_fn is None:
        raise ImportError(f"Could not find parser; tried: " + "; ".join(f"{m}.{names}" for m,names in _PARSER_CANDIDATES))

    interp_fn = None
    interp_where = ""
    for mod, names in _INTERP_CANDIDATES:
        hit = _first_callable(mod, names)
        if hit:
            _, n, fn = hit
            interp_fn = fn
            interp_where = f"{mod}.{n}"
            break
    if interp_fn is None:
        raise ImportError(f"Could not find interpreter; tried: " + "; ".join(f"{m}.{names}" for m,names in _INTERP_CANDIDATES))

    return parser_fn, interp_fn, parser_where, interp_where

# Resolve once and cache
try:
    _PARSER, _INTERP, _PW, _IW = _resolve()
except Exception as e:
    _PARSER = _INTERP = None
    _ERR = e
else:
    _ERR = None

def run_spl(src: str) -> str:
    if _ERR is not None:
        raise _ERR
    prog = _PARSER(src)
    out = _INTERP(prog)
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

echo "[6/7] Build zipapp and stage example"
mkdir -p "$OUT_DIR"
python3 -m zipapp "$DIST_STAGING" -o "$OUT_ZIP" -p "/usr/bin/env python3"
: > "$OUT_DIR/.nojekyll"
[ -f spl/programs/teleportation.spl ] && cp -f spl/programs/teleportation.spl "$OUT_DIR/teleportation.spl" || true

echo "[7/7] Sanity check contents"
python3 - <<'PY' "$OUT_ZIP"
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = set(z.namelist())
req = {"runner.py","spl/src/parser/parser.py","lark/__init__.py"}
missing = [r for r in req if r not in names]
print("[check] missing in zip:", missing)
assert not missing, "required files missing in zipapp"
print("[ok]", sys.argv[1])
PY

echo "[done] Built $OUT_ZIP"


#!/usr/bin/env bash
# build_spl_binary.sh — robust: creates missing __init__.py in staging
set -euo pipefail

# tools
command -v python3 >/dev/null || { echo "python3 not found"; exit 1; }
python3 - <<'PY' >/dev/null || { echo "Python 3.9+ required"; exit 1; }
import sys; assert (sys.version_info.major, sys.version_info.minor) >= (3,9)
PY
python3 - <<'PY' >/dev/null 2>&1 || python3 -m pip install --user -U pyinstaller >/dev/null
import PyInstaller
PY

# reset staging
rm -rf dist_spl dist build
mkdir -p dist_spl/spl/src/parser dist_spl/spl/src/interpreter dist_spl/spl/src/relations dist_spl/spl/programs

# helper to ensure a package
ensure_pkg() { [ -f "$1/__init__.py" ] || printf "" > "$1/__init__.py"; }

# copy sources
cp -f spl/__init__.py                               dist_spl/spl/__init__.py || printf "" > dist_spl/spl/__init__.py
cp -f spl/src/parser/parser.py                      dist_spl/spl/src/parser/parser.py
cp -f spl/src/interpreter/interpret_spl.py          dist_spl/spl/src/interpreter/
cp -f spl/src/interpreter/interpret_spl_functions.py dist_spl/spl/src/interpreter/
cp -f spl/src/interpreter/interpret_spl_affine.py   dist_spl/spl/src/interpreter/
cp -f spl/src/interpreter/interpret_spl_sets.py     dist_spl/spl/src/interpreter/
cp -f spl/src/relations/*.py                        dist_spl/spl/src/relations/
cp -f spl/programs/teleportation.spl                dist_spl/spl/programs/teleportation.spl

# make staged dirs packages
ensure_pkg dist_spl/spl
ensure_pkg dist_spl/spl/src
ensure_pkg dist_spl/spl/src/parser
ensure_pkg dist_spl/spl/src/interpreter
ensure_pkg dist_spl/spl/src/relations
ensure_pkg dist_spl/spl/programs

# entrypoint
cat > dist_spl/__main__.py <<'PYZ'
import sys
from importlib.resources import files
from spl.src.parser.parser import parse_spl
from spl.src.interpreter.interpret_spl import interpret_spl

USAGE = "Usage:\n  spl-run <file.spl>\n  spl-run -\n  spl-run  # runs bundled teleportation\n"

def _read(p: str) -> str:
    with open(p, "r", encoding="utf-8") as f: return f.read()

def _read_example() -> str:
    # works because spl/programs is a package in the zip
    return files("spl.programs").joinpath("teleportation.spl").read_text(encoding="utf-8")

def main():
    argv = sys.argv[1:]
    if argv and argv[0] in {"-h","--help"}:
        print(USAGE, end=""); return 0
    try:
        if not argv: src = _read_example()
        elif argv[0] == "-": src = sys.stdin.read()
        else: src = _read(argv[0])
        prog = parse_spl(src)
        out = interpret_spl(prog)
        print(out if isinstance(out,str) else str(out))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__": raise SystemExit(main())
PYZ

# build
python3 -m PyInstaller --onefile --name spl-run \
  --paths dist_spl \
  --add-data "dist_spl/spl/programs/teleportation.spl:spl/programs" \
  dist_spl/__main__.py >/dev/null

test -f dist/spl-run || { echo "Build failed"; exit 1; }
chmod +x dist/spl-run
echo "Built dist/spl-run"


#!/usr/bin/env bash
set -euo pipefail

# Build layout expected by your site:
#   dist_spl/spl/src/{parser,interpreter,relations,dispatch}
# and also produce dist_spl/spl-run.pyz

# Run from anywhere: bash scripts/build_web_zipapp.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist_spl"             # <- matches your expectation
STAGING="${DIST_DIR}/spl"                     # we stage directly into dist_spl/spl
PYZ="${DIST_DIR}/spl-run.pyz"

echo "[0/9] Clean dist_spl"
rm -rf "${DIST_DIR}"
mkdir -p "${STAGING}/src/"

echo "[1/9] Create package directories"
mkdir -p "${STAGING}/src/parser"
mkdir -p "${STAGING}/src/interpreter"
mkdir -p "${STAGING}/src/relations"
mkdir -p "${STAGING}/src/dispatch"
: > "${DIST_DIR}/__init__.py"           # root of spl package if someone imports 'spl' from dist_spl
: > "${STAGING}/__init__.py"
: > "${STAGING}/src/__init__.py"
: > "${STAGING}/src/parser/__init__.py"
: > "${STAGING}/src/interpreter/__init__.py"
: > "${STAGING}/src/relations/__init__.py"
: > "${STAGING}/src/dispatch/__init__.py"

echo "[2/9] Copy parser"
cp -f "${REPO_ROOT}/spl/src/parser/parser.py" "${STAGING}/src/parser/parser.py"

echo "[3/9] Copy interpreter"
rsync -a --include='*/' --include='*.py' --exclude='*' "${REPO_ROOT}/spl/src/interpreter/" "${STAGING}/src/interpreter/"

echo "[4/9] Copy relations"
rsync -a --include='*/' --include='*.py' --exclude='*' "${REPO_ROOT}/spl/src/relations/" "${STAGING}/src/relations/"

echo "[5/9] Copy dispatch"
rsync -a --include='*/' --include='*.py' --exclude='*' "${REPO_ROOT}/spl/src/dispatch/" "${STAGING}/src/dispatch/"

echo "[6/9] Verify required files exist"
need=( \
  "${STAGING}/src/parser/parser.py" \
  "${STAGING}/src/interpreter/interpret_spl.py" \
  "${STAGING}/src/relations/affine_relations.py" \
  "${STAGING}/src/dispatch/chunker.py" \
)
missing=0
for f in "${need[@]}"; do
  if [[ ! -f "$f" ]]; then echo "MISSING: $f"; missing=1; fi
done
if [[ $missing -ne 0 ]]; then
  echo "Error: required files missing in dist layout" >&2
  find "${DIST_DIR}" -maxdepth 4 -type d -print | sed 's/^/DIR: /'
  exit 1
fi

echo "[7/9] Vendor pure-Python deps (optional)"
if [[ "${VENDOR_DEPS:-true}" == "true" ]]; then
  SITE_PKGS="${DIST_DIR}/site-packages"
  mkdir -p "${SITE_PKGS}"
  python3 -m pip install --upgrade --target "${SITE_PKGS}" --no-deps lark-parser || true
  python3 -m pip install --upgrade --target "${SITE_PKGS}" --no-deps lark || true
  [[ -d "${SITE_PKGS}/lark_parser" && ! -d "${SITE_PKGS}/lark" ]] && mv "${SITE_PKGS}/lark_parser" "${SITE_PKGS}/lark"
fi

echo "[8/9] Build zipapp at ${PYZ}"
(
  cd "${DIST_DIR}"
  # Create pyz with 'spl/' at top-level so imports use 'from spl.src....'
  if command -v zip >/dev/null 2>&1; then
    zip -qr "$(basename "${PYZ}")" spl site-packages || zip -qr "$(basename "${PYZ}")" spl
  else
    python3 - <<'PY'
import os, zipfile, sys
out = sys.argv[1]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk('spl'):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, p)
    if os.path.isdir('site-packages'):
        for root, dirs, files in os.walk('site-packages'):
            for f in files:
                p = os.path.join(root, f)
                z.write(p, p)
PY
  fi
)

echo "[9/9] List key files inside zip"
python3 - <<'PY'
import zipfile, pathlib
z = zipfile.ZipFile(pathlib.Path("dist_spl")/"spl-run.pyz")
want = ("spl/src/parser/parser.py",
        "spl/src/interpreter/interpret_spl.py",
        "spl/src/dispatch/chunker.py")
names = set(z.namelist())
for w in want:
    print(("OK   " if w in names else "MISS ") + w)
print("Total entries:", len(names))
PY

echo "Done. Deploy dist_spl/spl-run.pyz and dist_spl/spl/ for loose overlay if desired."

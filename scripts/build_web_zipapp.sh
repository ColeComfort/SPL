#!/usr/bin/env bash
set -euo pipefail

# Build SPL browser zipapp with namespace-friendly packages so FS overlay can merge.
# Run: bash scripts/build_web_zipapp.sh
# Out: dist_spl/spl-run.pyz and dist_spl/spl/src/... for optional loose overlay

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist_spl"
STAGING="${DIST_DIR}/spl"              # stage under dist_spl/spl so zip has 'spl/' at root
PYZ="${DIST_DIR}/spl-run.pyz"

echo "[0/8] Clean"
rm -rf "${DIST_DIR}"
mkdir -p "${STAGING}/src"/{parser,interpreter,relations,dispatch}

echo "[1/8] Create __init__.py only for concrete subpackages"
# Do NOT create __init__.py in 'spl/' or 'spl/src/' -> PEP 420 namespace to allow overlay
: > "${STAGING}/src/parser/__init__.py"
: > "${STAGING}/src/interpreter/__init__.py"
: > "${STAGING}/src/relations/__init__.py"
: > "${STAGING}/src/dispatch/__init__.py"

echo "[2/8] Copy parser"
cp -f "${REPO_ROOT}/spl/src/parser/parser.py" "${STAGING}/src/parser/parser.py"

echo "[3/8] Copy interpreter"
rsync -a --include='*/' --include='*.py' --exclude='*' "${REPO_ROOT}/spl/src/interpreter/" "${STAGING}/src/interpreter/"

echo "[4/8] Copy relations"
rsync -a --include='*/' --include='*.py' --exclude='*' "${REPO_ROOT}/spl/src/relations/"   "${STAGING}/src/relations/"

echo "[5/8] Copy dispatch"
rsync -a --include='*/' --include='*.py' --exclude='*' "${REPO_ROOT}/spl/src/dispatch/"    "${STAGING}/src/dispatch/"

echo "[6/8] Optional: vendor pure-Python deps"
if [[ "${VENDOR_DEPS:-true}" == "true" ]]; then
  SITE_PKGS="${DIST_DIR}/site-packages"
  mkdir -p "${SITE_PKGS}"
  python3 -m pip install --upgrade --target "${SITE_PKGS}" --no-deps lark-parser || true
  python3 -m pip install --upgrade --target "${SITE_PKGS}" --no-deps lark || true
  [[ -d "${SITE_PKGS}/lark_parser" && ! -d "${SITE_PKGS}/lark" ]] && mv "${SITE_PKGS}/lark_parser" "${SITE_PKGS}/lark"
fi

echo "[7/8] Build zipapp"
(
  cd "${DIST_DIR}"
  if command -v zip >/dev/null 2>&1; then
    zip -qr "$(basename "${PYZ}")" spl site-packages || zip -qr "$(basename "${PYZ}")" spl
  else
    python3 - <<'PY'
import os, zipfile, sys
out = sys.argv[1]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk('spl'):
        for f in files:
            p = os.path.join(root, f); z.write(p, p)
    if os.path.isdir('site-packages'):
        for root, _, files in os.walk('site-packages'):
            for f in files:
                p = os.path.join(root, f); z.write(p, p)
PY
  fi
)

echo "[8/8] Verify"
python3 - <<'PY'
import zipfile, pathlib
z = zipfile.ZipFile(pathlib.Path("dist_spl")/"spl-run.pyz")
names = set(z.namelist())
print(("MISS " if "spl/__init__.py" in names else "OK   ") + "no spl/__init__.py")
print(("MISS " if "spl/src/__init__.py" in names else "OK   ") + "no spl/src/__init__.py")
for w in ("spl/src/parser/parser.py","spl/src/interpreter/interpret_spl.py","spl/src/dispatch/chunker.py"):
    print(("OK   " if w in names else "MISS ")+w)
PY

echo "Built ${PYZ}"

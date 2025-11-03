#!/usr/bin/env bash
set -euo pipefail

# Build a browser zipapp for SPL.
# Run from anywhere: bash scripts/build_web_zipapp.sh
# Outputs: web_dist/spl-run.pyz

# Repo root is parent of this script directory.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${REPO_ROOT}/web_dist"
STAGING="${DIST_DIR}/staging"

echo "[0/7] Clean staging"
rm -rf "${STAGING}" "${DIST_DIR}/spl-run.pyz"
mkdir -p "${STAGING}"

echo "[1/7] Create package directories"
mkdir -p "${STAGING}/spl/src/parser"
mkdir -p "${STAGING}/spl/src/interpreter"
mkdir -p "${STAGING}/spl/src/relations"
mkdir -p "${STAGING}/spl/src/dispatch"
: > "${STAGING}/spl/__init__.py"
: > "${STAGING}/spl/src/__init__.py"
: > "${STAGING}/spl/src/parser/__init__.py"
: > "${STAGING}/spl/src/interpreter/__init__.py"
: > "${STAGING}/spl/src/relations/__init__.py"
: > "${STAGING}/spl/src/dispatch/__init__.py"

echo "[2/7] Copy parser"
cp -f "${REPO_ROOT}/spl/src/parser/parser.py" "${STAGING}/spl/src/parser/parser.py"

echo "[3/7] Copy interpreter tree"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --include='*/' --include='*.py' --exclude='*' "${REPO_ROOT}/spl/src/interpreter/" "${STAGING}/spl/src/interpreter/"
else
  find "${REPO_ROOT}/spl/src/interpreter" -type f -name '*.py' -print0 | while IFS= read -r -d '' f; do
    rel="${f#${REPO_ROOT}/}"
    mkdir -p "${STAGING}/$(dirname "${rel}")"
    cp -f "${f}" "${STAGING}/${rel}"
  done
fi

echo "[4/7] Copy relations tree"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --include='*/' --include='*.py' --exclude='*' "${REPO_ROOT}/spl/src/relations/" "${STAGING}/spl/src/relations/"
else
  find "${REPO_ROOT}/spl/src/relations" -type f -name '*.py' -print0 | while IFS= read -r -d '' f; do
    rel="${f#${REPO_ROOT}/}"
    mkdir -p "${STAGING}/$(dirname "${rel}")"
    cp -f "${f}" "${STAGING}/${rel}"
  done
fi

echo "[5/7] Copy dispatch tree"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --include='*/' --include='*.py' --exclude='*' "${REPO_ROOT}/spl/src/dispatch/" "${STAGING}/spl/src/dispatch/"
else
  find "${REPO_ROOT}/spl/src/dispatch" -type f -name '*.py' -print0 | while IFS= read -r -d '' f; do
    rel="${f#${REPO_ROOT}/}"
    mkdir -p "${STAGING}/$(dirname "${rel}")"
    cp -f "${f}" "${STAGING}/${rel}"
  done
fi

# Optional vendoring of pure-Python deps to speed boot in Pyodide.
if [[ "${VENDOR_DEPS:-true}" == "true" ]]; then
  echo "[6/7] Vendor pure-Python dependencies into site-packages"
  SITE_PKGS="${STAGING}/site-packages"
  mkdir -p "${SITE_PKGS}"
  # Try both names: lark-parser and lark
  python3 -m pip install --upgrade --target "${SITE_PKGS}" --no-deps lark-parser || true
  python3 -m pip install --upgrade --target "${SITE_PKGS}" --no-deps lark || true
  [[ -d "${SITE_PKGS}/lark_parser" && ! -d "${SITE_PKGS}/lark" ]] && mv "${SITE_PKGS}/lark_parser" "${SITE_PKGS}/lark"
fi

echo "[7/7] Create zipapp spl-run.pyz"
mkdir -p "${DIST_DIR}"
(
  cd "${STAGING}"
  if command -v zip >/dev/null 2>&1; then
    zip -qr "${DIST_DIR}/spl-run.pyz" .
  else
    python3 - <<'PY'
import os, zipfile, sys
out = sys.argv[1]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk('.'):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, p)
PY
    mv spl-run.pyz "${DIST_DIR}/spl-run.pyz" || true
  fi
)

echo
echo "Built ${DIST_DIR}/spl-run.pyz"
echo "Contents:"
python3 - <<'PY'
import zipfile, pathlib
z = zipfile.ZipFile(pathlib.Path("web_dist")/"spl-run.pyz")
for n in sorted(p for p in z.namelist() if p.endswith(".py") and not p.startswith("site-packages/")):
    print("  " + n)
PY

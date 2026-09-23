#!/usr/bin/env bash
# Regenerate the three environment-fingerprint files spec section 37 requires
# to exist at the project root, without re-running the whole setup script.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -d "${REPO_ROOT}/../AdaMEM/.git" ]; then
  git -C "${REPO_ROOT}/../AdaMEM" rev-parse HEAD | tee "${REPO_ROOT}/ADAMEM_COMMIT.txt"
else
  echo "WARNING: ${REPO_ROOT}/../AdaMEM is not a git checkout; ADAMEM_COMMIT.txt not updated." >&2
fi

python -m pip freeze > "${REPO_ROOT}/requirements_lock.txt"
echo "-> ${REPO_ROOT}/requirements_lock.txt"

npu-smi info > "${REPO_ROOT}/gpu_info.txt"
echo "-> ${REPO_ROOT}/gpu_info.txt"

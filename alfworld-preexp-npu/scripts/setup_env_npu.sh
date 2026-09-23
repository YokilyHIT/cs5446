#!/usr/bin/env bash
# Environment bootstrap for the Ascend NPU host that will actually run this
# pipeline. Run this ON THE NPU MACHINE (not on the Windows dev box this repo
# was authored on -- that machine has no GPU/NPU and only edits code).
#
# Usage:
#   bash scripts/setup_env_npu.sh
#
# Override any of these before running if your host differs:
#   CANN_TOOLKIT_RUN, CANN_KERNELS_RUN : paths to the CANN .run installers
#   ASCEND_TOOLKIT_HOME                : where CANN gets installed
#   CONDA_ENV_NAME, PYTHON_VERSION
#   TORCH_VERSION, TORCH_NPU_VERSION    : must match your CANN version, see
#     https://gitee.com/ascend/pytorch (torch_npu release notes list the
#     compatible torch/CANN triple per release -- pin these explicitly,
#     never "pip install torch_npu" unpinned)
#   MODEL_SOURCE                        : "huggingface" or "modelscope"
#
# What this script does NOT do: download the actual CANN .run installers or
# accept Huawei's license -- those must be obtained from
# https://www.hiascend.com/developer/download/community/result?module=cann
# for your exact NPU model/firmware/driver combination first.

set -euo pipefail

CANN_TOOLKIT_RUN="${CANN_TOOLKIT_RUN:-./Ascend-cann-toolkit_8.0.0_linux-aarch64.run}"
CANN_KERNELS_RUN="${CANN_KERNELS_RUN:-./Ascend-cann-kernels-910b_8.0.0_linux.run}"
ASCEND_TOOLKIT_HOME="${ASCEND_TOOLKIT_HOME:-/usr/local/Ascend/ascend-toolkit}"
CONDA_ENV_NAME="${CONDA_ENV_NAME:-alfworld-preexp-npu}"
PYTHON_VERSION="${PYTHON_VERSION:-3.10}"
TORCH_VERSION="${TORCH_VERSION:-2.5.1}"
TORCH_NPU_VERSION="${TORCH_NPU_VERSION:-2.5.1}"
VLLM_VERSION="${VLLM_VERSION:-0.7.3}"
VLLM_ASCEND_VERSION="${VLLM_ASCEND_VERSION:-0.7.3}"
MODEL_SOURCE="${MODEL_SOURCE:-modelscope}"   # modelscope is usually faster/more reliable from mainland-China NPU hosts
MODEL_NAME="Qwen/Qwen3-4B-Instruct-2507"
MODEL_LOCAL_DIR="${MODEL_LOCAL_DIR:-$HOME/models/Qwen3-4B-Instruct-2507}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== [1/8] Sanity-check NPU visibility =="
if ! command -v npu-smi >/dev/null 2>&1; then
  echo "npu-smi not found. Install the Ascend driver + firmware first" \
       "(this is separate from CANN toolkit -- see your NPU vendor image docs)." >&2
  exit 1
fi
npu-smi info

echo "== [2/8] Install CANN toolkit + kernels (skipped if already sourced) =="
if [ -f "${ASCEND_TOOLKIT_HOME}/set_env.sh" ]; then
  echo "CANN already installed at ${ASCEND_TOOLKIT_HOME}, skipping installers."
else
  chmod +x "$CANN_TOOLKIT_RUN" "$CANN_KERNELS_RUN"
  ./"$CANN_TOOLKIT_RUN" --install --quiet
  ./"$CANN_KERNELS_RUN" --install --quiet
fi
# shellcheck disable=SC1090
source "${ASCEND_TOOLKIT_HOME}/set_env.sh"
echo "Add this line to your shell rc so every new shell has CANN on PATH:"
echo "  source ${ASCEND_TOOLKIT_HOME}/set_env.sh"

echo "== [3/8] Conda env =="
if ! conda env list | grep -q "^${CONDA_ENV_NAME} "; then
  conda create -n "$CONDA_ENV_NAME" "python=${PYTHON_VERSION}" -y
fi
# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV_NAME"
python --version

echo "== [4/8] torch + torch_npu (versions must match your CANN release) =="
pip install "torch==${TORCH_VERSION}" --index-url https://download.pytorch.org/whl/cpu
pip install "torch_npu==${TORCH_NPU_VERSION}"
python -c "import torch, torch_npu; print('torch_npu.npu.is_available():', torch_npu.npu.is_available())"

echo "== [5/8] vLLM + vLLM-Ascend plugin =="
pip install "vllm==${VLLM_VERSION}"
pip install "vllm-ascend==${VLLM_ASCEND_VERSION}"

echo "== [6/8] This repo's own requirements =="
pip install -r "${REPO_ROOT}/requirements.txt"

echo "== [7/8] AdaMEM (agent code base) =="
cd "${REPO_ROOT}/.."
if [ ! -d AdaMEM ]; then
  git clone https://github.com/yunx-z/AdaMEM.git
fi
cd AdaMEM
git rev-parse HEAD | tee "${REPO_ROOT}/ADAMEM_COMMIT.txt"
pip install -e .
pip install -r requirements.txt
echo "Verify these files exist before editing anything (spec section 1.2):"
find . -maxdepth 3 -type f | sort | head -200
test -f examples/prompt_agent/gpt4o_alfworld.py && echo "OK: examples/prompt_agent/gpt4o_alfworld.py"
test -f build_index.py && echo "OK: build_index.py"
test -f requirements.txt && echo "OK: requirements.txt"

echo "== [8/8] ALFWorld =="
pip install "alfworld[full]"
export ALFWORLD_DATA="${ALFWORLD_DATA:-$HOME/.cache/alfworld}"
alfworld-download
python - <<'PY'
import alfworld
print("ALFWorld import OK")
PY

echo "== Model weights =="
if [ "$MODEL_SOURCE" = "modelscope" ]; then
  pip install modelscope
  python - <<PY
from modelscope import snapshot_download
snapshot_download("${MODEL_NAME}", local_dir="${MODEL_LOCAL_DIR}")
PY
else
  pip install "huggingface_hub[cli]"
  huggingface-cli download "$MODEL_NAME" --local-dir "$MODEL_LOCAL_DIR"
fi

echo "== Done. Record the environment =="
python -m pip freeze > "${REPO_ROOT}/requirements_lock.txt"
npu-smi info > "${REPO_ROOT}/gpu_info.txt"

echo ""
echo "Next steps:"
echo "  1. python ${REPO_ROOT}/scripts/inspect_alfworld_api.py # verify ALFWorld field names (see README_NPU_SETUP.md)"
echo "  2. bash ${REPO_ROOT}/scripts/start_vllm_npu.sh          # start the model server"
echo "  3. bash ${REPO_ROOT}/scripts/run_smoke_test.sh          # spec section 6/38 acceptance smoke test"

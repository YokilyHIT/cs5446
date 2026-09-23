#!/usr/bin/env bash
# Start the Qwen3-4B-Instruct-2507 vLLM OpenAI-compatible server on an
# Ascend NPU. This is the NPU-adapted equivalent of the spec's original
# CUDA_VISIBLE_DEVICES invocation (spec section 1.4): swap CUDA_VISIBLE_DEVICES
# for ASCEND_RT_VISIBLE_DEVICES, and let vllm-ascend's platform plugin pick
# the Ascend backend automatically once torch_npu is importable (this is the
# same pattern OpenOneRec-Blue-Zone's benchmarks_green/scripts/ray-vllm/
# utils/generator.py uses: it never passes a "--device npu" flag to vLLM --
# it just sets ASCEND_RT_VISIBLE_DEVICES/NPU_VISIBLE_DEVICES and unsets
# CUDA_VISIBLE_DEVICES before importing vllm).
#
# Usage:
#   NPU_DEVICES=0 bash scripts/start_vllm_npu.sh
#   NPU_DEVICES=0,1 TENSOR_PARALLEL_SIZE=2 bash scripts/start_vllm_npu.sh   # if one 910B card's HBM is tight

set -euo pipefail

MODEL_PATH="${MODEL_PATH:-$HOME/models/Qwen3-4B-Instruct-2507}"
NPU_DEVICES="${NPU_DEVICES:-0}"
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-1}"
PORT="${PORT:-8001}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.85}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"

export ASCEND_RT_VISIBLE_DEVICES="$NPU_DEVICES"
export NPU_VISIBLE_DEVICES="$NPU_DEVICES"
unset CUDA_VISIBLE_DEVICES || true

echo "Starting vLLM on Ascend NPU device(s) ${NPU_DEVICES}, TP=${TENSOR_PARALLEL_SIZE}"

python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_PATH" \
  --served-model-name Qwen/Qwen3-4B-Instruct-2507 \
  --host 0.0.0.0 \
  --port "$PORT" \
  --dtype bfloat16 \
  --max-model-len "$MAX_MODEL_LEN" \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --tensor-parallel-size "$TENSOR_PARALLEL_SIZE" \
  --trust-remote-code

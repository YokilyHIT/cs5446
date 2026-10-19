#!/bin/bash
# Direction E serving: keep the 4B WM on NPU 0-1 (ports 8001-8002), Qwen3-14B planner on NPU 2-7 (ports 8011-8016).
cd /home/ma-user/work/5446/preexp_env; source env.sh
for p in 8003 8004 8005 8006 8007 8008; do P=$(pgrep -f "port $p\b"); [ -n "$P" ] && kill $P; done
sleep 20
for i in 2 3 4 5 6 7; do
  p=$((8009 + i))
  ASCEND_RT_VISIBLE_DEVICES=$i NPU_VISIBLE_DEVICES=$i nohup venv/bin/python -m vllm.entrypoints.openai.api_server \
    --model $PREEXP_BASE/models/Qwen3-14B --served-model-name Qwen/Qwen3-14B --host 0.0.0.0 --port $p \
    --dtype bfloat16 --max-model-len 32768 --gpu-memory-utilization 0.88 --tensor-parallel-size 1 --trust-remote-code \
    > logs/vllm_stage/vllm14b_$p.log 2>&1 &
  sleep 2
done

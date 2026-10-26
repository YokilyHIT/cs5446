#!/bin/bash
# Round 4 serving: Qwen3-4B-Instruct-2507 on NPU 0..N4-1 (ports 8001..), Qwen3-14B on the rest (ports 8011..).
# Usage: N4=4 bash start_servers_r4.sh    (kills any existing vLLM servers first)
N4=${N4:-4}
cd /home/ma-user/work/5446/preexp_env; source env.sh
pkill -f "[v]llm.entrypoints.openai.api_server"; sleep 25
mkdir -p logs/vllm_stage
for i in $(seq 0 7); do
  if [ $i -lt $N4 ]; then
    p=$((8001 + i)); M=$PREEXP_BASE/models/Qwen3-4B-Instruct-2507; N=Qwen/Qwen3-4B-Instruct-2507; L=vllm4b_$p
  else
    p=$((8011 + i - N4)); M=$PREEXP_BASE/models/Qwen3-14B; N=Qwen/Qwen3-14B; L=vllm14b_$p
  fi
  ASCEND_RT_VISIBLE_DEVICES=$i NPU_VISIBLE_DEVICES=$i nohup venv/bin/python -m vllm.entrypoints.openai.api_server \
    --model $M --served-model-name $N --host 0.0.0.0 --port $p \
    --dtype bfloat16 --max-model-len 32768 --gpu-memory-utilization 0.88 --tensor-parallel-size 1 --trust-remote-code \
    > logs/vllm_stage/$L.log 2>&1 &
  sleep 2
done

#!/bin/bash
# Step 2: always + online Episodic Memory on the 600-task dev pool, one process per
# 200-task chunk => one shared bank per chunk (a single 600-task process is GIL-bound).
# ATTEMPT=1 starts empty; ATTEMPT=2 is seeded with the same chunk's attempt-1 bank.
ATTEMPT=${ATTEMPT:-1}
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES=$(for p in $(seq 8001 8008); do echo -n "http://127.0.0.1:$p/v1,"; done)
S0=outputs/react_study/step0_protocol_v2_measurement; S2=outputs/react_study/step2_episodic_memory
for c in ${CHUNKS:-0 1 2}; do
  INIT=""
  [ "$ATTEMPT" = 2 ] && INIT="--memory_init $S2/raw/train/dev_v2_em_c${c}_always__rep0.memory.jsonl"
  nohup $PY -m preexperiments.react_study.run_episodes --stage 12 --split train \
    --games_file $S0/raw/devpool600_chunk$c --arm always --rep $((ATTEMPT-1)) --protocol v2 --variant list \
    --second_call_when_closed --memory online $INIT --prefix dev_v2_em_c${c}_ --workers 24 \
    > $S2/logs/dev_v2_em_c${c}_always_attempt$ATTEMPT.log 2>&1 &
done

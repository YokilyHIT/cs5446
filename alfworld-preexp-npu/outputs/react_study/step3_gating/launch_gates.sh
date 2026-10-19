#!/bin/bash
# Step 3: pre-/post-call gates at ~30% usage on the 460 held-out dev-pool tasks (protocol v2, no memory).
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES=$(for p in $(seq 8001 8008); do echo -n "http://127.0.0.1:$p/v1,"; done)
S3=outputs/react_study/step3_gating
TAU=$(python3 -c "import json;print(json.load(open('$S3/tables/gate_calibration.json'))['tau_usage30'])")
for c in 0 1 2; do for rep in 0 1; do
  for arm in random_pre selective gate_stuck gate_learned; do
    nohup $PY -m preexperiments.react_study.run_episodes --stage 13 --split train --games_file $S3/raw/eval460_chunk$c \
      --arm $arm --rep $rep --protocol v2 --variant list --second_call_when_closed --tau $TAU --p_gate 0.3 \
      --gate_seed 2027 --prefix eval_v2_c${c}_ --workers 12 > $S3/logs/eval_v2_c${c}_${arm}_rep${rep}.log 2>&1 &
  done
done; done

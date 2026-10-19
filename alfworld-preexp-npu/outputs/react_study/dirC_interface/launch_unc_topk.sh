#!/bin/bash
# Exploratory B+C combination on dev460 x 2 reps: uncertainty gate decides WHERE, candidate comparison decides HOW.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES=$(for p in $(seq 8001 8008); do echo -n "http://127.0.0.1:$p/v1,"; done)
S3=outputs/react_study/step3_gating; SC=outputs/react_study/dirC_interface
for c in 0 1 2; do for rep in 0 1; do
  nohup $PY -m preexperiments.react_study.run_episodes --stage 22 --split train --games_file $S3/raw/eval460_chunk$c \
    --arm unc_topk --label unc_topk --rep $rep --protocol v2 --variant list --gate_seed 2027 --prefix unc_topk_c${c}_ \
    --workers 10 > $SC/logs/unc_topk_c${c}_rep${rep}.log 2>&1 &
done; done

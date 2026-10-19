#!/bin/bash
# Direction B online: planner-uncertainty pre-call gate (action logprob < 30%-usage threshold), dev460 x 2 reps.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES=$(for p in $(seq 8001 8008); do echo -n "http://127.0.0.1:$p/v1,"; done)
S3=outputs/react_study/step3_gating; SB=outputs/react_study/dirB_planner_uncertainty
for c in 0 1 2; do for rep in 0 1; do
  nohup $PY -m preexperiments.react_study.run_episodes --stage 21 --split train --games_file $S3/raw/eval460_chunk$c \
    --arm gate_unc --label gate_unc --rep $rep --protocol v2 --variant list --gate_seed 2027 --prefix gate_unc_c${c}_ \
    --workers 8 > $SB/logs/gate_unc_c${c}_rep${rep}.log 2>&1 &
done; done

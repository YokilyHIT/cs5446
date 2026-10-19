#!/bin/bash
# Round 3 batch 1 (directions A, D, C) on the 460 held-out dev tasks, 2 reps, protocol v2,
# NO identical-prompt second call when a gate is closed (that call was the confound).
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES=$(for p in $(seq 8001 8008); do echo -n "http://127.0.0.1:$p/v1,"; done)
S3=outputs/react_study/step3_gating; SA=outputs/react_study/dirA_D_mechanism_dose; SC=outputs/react_study/dirC_interface
mkdir -p $SC/logs
run() { # stage arm label extra...
  local st=$1 arm=$2 lab=$3; shift 3
  for c in 0 1 2; do for rep in 0 1; do
    nohup $PY -m preexperiments.react_study.run_episodes --stage $st --split train --games_file $S3/raw/eval460_chunk$c \
      --arm $arm --label $lab --rep $rep --protocol v2 --variant list --gate_seed 2027 --prefix ${lab}_c${c}_ --workers 8 "$@" \
      > outputs/react_study/$( [ $st = 22 ] && echo dirC_interface || echo dirA_D_mechanism_dose )/logs/${lab}_c${c}_rep${rep}.log 2>&1 &
  done; done
}
run 20 none_resample none_resample
run 20 explore_stuck explore_stuck
for p in 0.1 0.3 0.5 0.7; do run 20 random_pre random_pre_nc_p$p --p_gate $p; done
run 22 fore_topk fore_topk_p0.3 --p_gate 0.3
run 22 fore_surprise fore_surprise

#!/bin/bash
# Phase 3: full-task 2x2 mechanism matrix on dev460 x 2 reps, random 30% (gate_seed 2027, same u as
# random_pre_nc_p0.3), NC when closed. Existing: none / W4 (random_pre_nc_p0.3) for 4B (dirA_D, step0)
# and 14B (dirE). New: RT, R0 (4B only), oracle_pre, W14 (random_pre with --wm_role wm_alt).
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
O=outputs/react_study; S3=$O/step3_gating
run() { # planner(4|14) arm label workers extra...
  local pl=$1 arm=$2 lab=$3 w=$4; shift 4
  for c in 0 1 2; do for rep in 0 1; do
    (if [ $pl = 14 ]; then P14=1; else P14=0; fi; export P14; source $O/r4_common/env_r4.sh
     nohup $PY -m preexperiments.react_study.run_episodes --stage 33 --split train --games_file $S3/raw/eval460_chunk$c \
       --arm $arm --label $lab --rep $rep --protocol v2 --variant list --gate_seed 2027 --p_gate 0.3 \
       --prefix ${lab}_c${c}_ --workers $w "$@" > $O/p3_mechanism_matrix/logs/${lab}_c${c}_rep${rep}.log 2>&1 &)
  done; done
}
run 4 resample_pre p4b_RT_r30 6
run 4 resample0_pre p4b_R0_r30 6
run 4 oracle_pre p4b_oracle_r30 4
run 4 random_pre p4b_W14_r30 6 --wm_role wm_alt
run 14 resample_pre p14b_RT_r30 6
run 14 oracle_pre p14b_oracle_r30 4
run 14 random_pre p14b_W14_r30 6 --wm_role wm_alt

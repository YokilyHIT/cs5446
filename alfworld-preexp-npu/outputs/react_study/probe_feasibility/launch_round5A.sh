#!/bin/bash
# Round 5 stage A (plan: /home/ma-user/work/5446/react_study_round5_plan_20261021.md), dev460 x 2 reps, record_state.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
O=outputs/react_study; S3=$O/step3_gating
run() { # planner arm label workers extra...
  local pl=$1 arm=$2 lab=$3 w=$4; shift 4
  for c in 0 1 2; do for rep in 0 1; do
    (if [ $pl = 14 ]; then P14=1; else P14=0; fi; export P14; source $O/r4_common/env_r4.sh
     nohup $PY -m preexperiments.react_study.run_episodes --stage 38 --split train --games_file $S3/raw/eval460_chunk$c \
       --arm $arm --label $lab --rep $rep --protocol v2 --variant list --gate_seed 2027 --record_state \
       --prefix ${lab}_c${c}_ --workers $w "$@" > $O/probe_feasibility/logs/${lab}_c${c}_rep${rep}.log 2>&1 &)
  done; done
}
run 4 inv_reflect p4b_inv_reflect 6
run 4 inv_sreflect p4b_inv_sreflect 6
run 4 inv_rules p4b_inv_rules 6
run 4 inv_state p4b_inv_state 6
run 4 inv_wmpred p4b_inv_wmpred_wm4 6
run 4 inv_wmpred p4b_inv_wmpred_wm14 6 --wm_role wm_alt
run 4 post_wmrepair p4b_post_wmrepair_wm4 6
run 14 inv_reflect p14b_inv_reflect 6
run 14 inv_sreflect p14b_inv_sreflect 6
run 14 inv_rules p14b_inv_rules 6
run 14 inv_state p14b_inv_state 6
run 14 inv_wmpred p14b_inv_wmpred_wm14 6 --wm_role wm_alt

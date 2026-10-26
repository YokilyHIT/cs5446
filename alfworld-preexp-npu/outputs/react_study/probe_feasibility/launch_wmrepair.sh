#!/bin/bash
# Real-WM repair (no rules): 4B planner x {4B WM, 14B WM}; 14B planner x {none-ref exists, inv_fail, inv_repair, inv_wmrepair(14B WM)}.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
O=outputs/react_study; S3=$O/step3_gating
run() { # planner arm label workers extra...
  local pl=$1 arm=$2 lab=$3 w=$4; shift 4
  for c in 0 1 2; do for rep in 0 1; do
    (if [ $pl = 14 ]; then P14=1; else P14=0; fi; export P14; source $O/r4_common/env_r4.sh
     nohup $PY -m preexperiments.react_study.run_episodes --stage 38 --split train --games_file $S3/raw/eval460_chunk$c \
       --arm $arm --label $lab --rep $rep --protocol v2 --variant list --gate_seed 2027 \
       --prefix ${lab}_c${c}_ --workers $w "$@" > $O/probe_feasibility/logs/${lab}_c${c}_rep${rep}.log 2>&1 &)
  done; done
}
run 4 inv_wmrepair p4b_inv_wmrepair_wm4 6
run 4 inv_wmrepair p4b_inv_wmrepair_wm14 6 --wm_role wm_alt
run 14 inv_fail p14b_inv_fail 6
run 14 inv_repair p14b_inv_repair 6
run 14 inv_wmrepair p14b_inv_wmrepair_wm14 6 --wm_role wm_alt

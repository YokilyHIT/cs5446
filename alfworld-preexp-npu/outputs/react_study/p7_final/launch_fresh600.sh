#!/bin/bash
# Round 5 stage B (frozen, tables/preregistration_round5_final.json): fresh_test600 x 3 reps, both planners.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
O=outputs/react_study; F=$O/p7_final
run() { # planner arm label workers extra...
  local pl=$1 arm=$2 lab=$3 w=$4; shift 4
  for c in 0 1; do for rep in 0 1 2; do
    (if [ $pl = 14 ]; then P14=1; else P14=0; fi; export P14; source $O/r4_common/env_r4.sh
     nohup $PY -m preexperiments.react_study.run_episodes --stage 37 --split train --games_file $F/raw/fresh600_chunk$c \
       --arm $arm --label $lab --rep $rep --protocol v2 --variant list --gate_seed 2027 \
       --prefix fresh_${lab}_c${c}_ --workers $w "$@" > $F/logs/fresh_${lab}_c${c}_rep${rep}.log 2>&1 &)
  done; done
}
for pl in 4 14; do
  p=p${pl}b
  run $pl none ${p}_none 5
  run $pl inv_fail ${p}_inv_fail 5
  run $pl inv_reflect ${p}_inv_reflect 5
  run $pl inv_sreflect ${p}_inv_sreflect 5
  run $pl inv_rules ${p}_inv_rules 5
  run $pl inv_wmrepair ${p}_wmrepair_wm14 5 --wm_role wm_alt
  run $pl inv_repair ${p}_inv_repair 5
done
run 4 inv_wmrepair p4b_wmrepair_wm4 5

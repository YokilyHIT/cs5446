#!/bin/bash
# Round 5 stage B (frozen): unseen134 (eval_out_of_distribution) x 5 reps, both planners -- repeated evaluation.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
O=outputs/react_study; F=$O/p7_final
run() { # planner arm label workers extra...
  local pl=$1 arm=$2 lab=$3 w=$4; shift 4
  for rep in 0 1 2 3 4; do
    (if [ $pl = 14 ]; then P14=1; else P14=0; fi; export P14; source $O/r4_common/env_r4.sh
     nohup $PY -m preexperiments.react_study.run_episodes --stage 37 --split eval_out_of_distribution \
       --arm $arm --label $lab --rep $rep --protocol v2 --variant list --gate_seed 2027 \
       --prefix unseen_${lab}_c0_ --workers $w "$@" > $F/logs/unseen_${lab}_rep${rep}.log 2>&1 &)
  done
}
for pl in 4 14; do
  p=p${pl}b
  run $pl none ${p}_none 8
  run $pl inv_fail ${p}_inv_fail 8
  run $pl inv_reflect ${p}_inv_reflect 8
  run $pl inv_sreflect ${p}_inv_sreflect 8
  run $pl inv_rules ${p}_inv_rules 8
  run $pl inv_wmrepair ${p}_wmrepair_wm14 8 --wm_role wm_alt
  run $pl inv_repair ${p}_inv_repair 8
done
run 4 inv_wmrepair p4b_wmrepair_wm4 8

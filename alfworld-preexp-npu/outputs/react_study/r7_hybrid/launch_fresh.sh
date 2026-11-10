#!/bin/bash
# Round 7 stage B (tables/preregistration_r7.json): selected arm inv_wmverify + concat control on fresh600 x 3,
# both planners. Frozen method and inv_rpms on fresh600 are reused (p7_final, r6_baselines). NPU 0-3 (NDEV=4 N4=1).
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export NDEV=4 N4=1
O=outputs/react_study; H=$O/r7_hybrid; F=$O/p7_final
run() { # planner arm label workers extra...
  local pl=$1 arm=$2 lab=$3 w=$4; shift 4
  for c in 0 1; do for rep in 0 1 2; do
    (if [ $pl = 14 ]; then P14=1; else P14=0; fi; export P14; source $O/r4_common/env_r4.sh
     nohup $PY -m preexperiments.react_study.run_episodes --stage 41 --split train --games_file $F/raw/fresh600_chunk$c \
       --arm $arm --wm_role wm_alt --label $lab --rep $rep --protocol v2 --variant list --gate_seed 2027 \
       --prefix fresh_${lab}_c${c}_ --workers $w "$@" > $H/logs/fresh_${lab}_c${c}_rep${rep}.log 2>&1 &)
  done; done
}
for pl in 4 14; do
  run $pl inv_wmverify p${pl}b_wmverify 6
  run $pl inv_wmrules_concat p${pl}b_wmrules_concat 6
done

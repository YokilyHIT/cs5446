#!/bin/bash
# Round 6 recent-work baselines (tables/preregistration_baselines.json): fresh600 x 3, both planners, 14B for every WM role.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export N4=3   # servers started with N4=3: 4B on ports 8001-8003, 14B on 8011-8015
O=outputs/react_study; B=$O/r6_baselines; F=$O/p7_final
run() { # planner arm label workers extra...
  local pl=$1 arm=$2 lab=$3 w=$4; shift 4
  for c in 0 1; do for rep in 0 1 2; do
    (if [ $pl = 14 ]; then P14=1; else P14=0; fi; export P14; source $O/r4_common/env_r4.sh
     nohup $PY -m preexperiments.react_study.run_episodes --stage 40 --split train --games_file $F/raw/fresh600_chunk$c \
       --arm $arm --wm_role wm_alt --label $lab --rep $rep --protocol v2 --variant list --gate_seed 2027 \
       --prefix fresh_${lab}_c${c}_ --workers $w "$@" > $B/logs/fresh_${lab}_c${c}_rep${rep}.log 2>&1 &)
  done; done
}
for pl in 4 14; do
  p=p${pl}b
  run $pl walle ${p}_walle 4
  run $pl walle ${p}_walle_rules 4 --knowledge $B/raw/walle_rules.json
  run $pl inv_rpms ${p}_inv_rpms 5
  run $pl expel ${p}_expel 5 --knowledge $B/raw/expel_insights_${p}.json
  run $pl inv_expel ${p}_inv_expel 5 --knowledge $B/raw/expel_insights_${p}.json
done

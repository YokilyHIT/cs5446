#!/bin/bash
# WorldEvolver-style confidence-gated foresight (tables/preregistration_selective.json), fresh600 x 3.
# Servers: NDEV=4 N4=1 start_servers_r4.sh -> 4B on NPU 0 (8001), 14B on NPU 1-3 (8011-8013); NPU 4-7 free.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export NDEV=4 N4=1
O=outputs/react_study; B=$O/r6_baselines; F=$O/p7_final
TAU4=$(python3 -c "import json;print(json.load(open('$B/tables/selective_calibration.json'))['p4b']['tau'])")
TAU14=$(python3 -c "import json;print(json.load(open('$B/tables/selective_calibration.json'))['p14b']['tau'])")
run() { # planner label tau workers extra...
  local pl=$1 lab=$2 tau=$3 w=$4; shift 4
  for c in 0 1; do for rep in 0 1 2; do
    (if [ $pl = 14 ]; then P14=1; else P14=0; fi; export P14; source $O/r4_common/env_r4.sh
     nohup $PY -m preexperiments.react_study.run_episodes --stage 40 --split train --games_file $F/raw/fresh600_chunk$c \
       --arm selective --tau $tau --second_call_when_closed --wm_role wm_alt --label $lab --rep $rep --protocol v2 \
       --variant list --gate_seed 2027 --prefix fresh_${lab}_c${c}_ --workers $w "$@" > $B/logs/fresh_${lab}_c${c}_rep${rep}.log 2>&1 &)
  done; done
}
run 4 p4b_selective $TAU4 4
run 4 p4b_selective_em $TAU4 4 --memory online
run 14 p14b_selective $TAU14 4
run 14 p14b_selective_em $TAU14 4 --memory online

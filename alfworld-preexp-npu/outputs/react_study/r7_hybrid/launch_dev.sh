#!/bin/bash
# Round 7 stage A (dev460 x 2): rule-verified WM repair vs concat control vs RPMS-style, 4B and 14B planners.
# Frozen method / rule cards on dev460 are reused from probe_feasibility (same protocol, gate seed, splits).
# Servers: NDEV=4 N4=1 start_servers_r4.sh (NPU 0-3: 1 x 4B, 3 x 14B).
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export NDEV=4 N4=1
O=outputs/react_study; S3=$O/step3_gating; K=$O/r6_baselines/raw/walle_rules.json
run() { # planner arm label workers extra...
  local pl=$1 arm=$2 lab=$3 w=$4; shift 4
  for c in 0 1 2; do for rep in 0 1; do
    (if [ $pl = 14 ]; then P14=1; else P14=0; fi; export P14; source $O/r4_common/env_r4.sh
     nohup $PY -m preexperiments.react_study.run_episodes --stage 41 --split train --games_file $S3/raw/eval460_chunk$c \
       --arm $arm --label $lab --rep $rep --protocol v2 --variant list --gate_seed 2027 \
       --prefix ${lab}_c${c}_ --workers $w "$@" > $O/r7_hybrid/logs/${lab}_c${c}_rep${rep}.log 2>&1 &)
  done; done
}
for pl in 4 14; do
  run $pl inv_wmverify p${pl}b_wmverify 4 --wm_role wm_alt
  run $pl inv_wmverify_learned p${pl}b_wmverify_learned 4 --wm_role wm_alt --knowledge $K
  run $pl inv_wmrules_concat p${pl}b_wmrules_concat 4 --wm_role wm_alt
  run $pl inv_rpms p${pl}b_inv_rpms 4
done

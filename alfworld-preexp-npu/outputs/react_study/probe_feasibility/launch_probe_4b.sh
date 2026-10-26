#!/bin/bash
# Feasibility probes (4B planner, dev460 x 2 reps): intervene only when a_base is not admissible.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh; P14=0 source outputs/react_study/r4_common/env_r4.sh
O=outputs/react_study; S3=$O/step3_gating
for arm in inv_resample inv_fail inv_repair inv_proj; do
  for c in 0 1 2; do for rep in 0 1; do
    nohup $PY -m preexperiments.react_study.run_episodes --stage 38 --split train --games_file $S3/raw/eval460_chunk$c \
      --arm $arm --label p4b_$arm --rep $rep --protocol v2 --variant list --gate_seed 2027 \
      --prefix p4b_${arm}_c${c}_ --workers 6 > $O/probe_feasibility/logs/p4b_${arm}_c${c}_rep${rep}.log 2>&1 &
  done; done
done

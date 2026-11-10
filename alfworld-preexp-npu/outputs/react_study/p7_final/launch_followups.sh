#!/bin/bash
# Follow-ups (tables/preregistration_followups.json): repair executed directly / episode repair memory.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh; P14=0 source outputs/react_study/r4_common/env_r4.sh
O=outputs/react_study; F=$O/p7_final; S3=$O/step3_gating
for arm in inv_wmrepair_exec inv_wmrepair_mem; do
  for c in 0 1 2; do for rep in 0 1; do
    nohup $PY -m preexperiments.react_study.run_episodes --stage 38 --split train --games_file $S3/raw/eval460_chunk$c \
      --arm $arm --wm_role wm_alt --label p4b_${arm}_wm14 --rep $rep --protocol v2 --variant list --gate_seed 2027 \
      --prefix p4b_${arm}_wm14_c${c}_ --workers 6 > $O/probe_feasibility/logs/p4b_${arm}_wm14_c${c}_rep${rep}.log 2>&1 &
  done; done
  for c in 0 1; do for rep in 0 1 2; do
    nohup $PY -m preexperiments.react_study.run_episodes --stage 37 --split train --games_file $F/raw/fresh600_chunk$c \
      --arm $arm --wm_role wm_alt --label p4b_${arm}_wm14 --rep $rep --protocol v2 --variant list --gate_seed 2027 \
      --prefix fresh_p4b_${arm}_wm14_c${c}_ --workers 5 > $F/logs/fresh_p4b_${arm}_wm14_c${c}_rep${rep}.log 2>&1 &
  done; done
done

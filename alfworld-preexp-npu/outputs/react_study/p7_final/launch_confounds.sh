#!/bin/bash
# Confound controls (tables/preregistration_confounds.json): 4B planner, 14B WM / takeover model.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh; P14=0 source outputs/react_study/r4_common/env_r4.sh
O=outputs/react_study; F=$O/p7_final; S3=$O/step3_gating
for arm in inv_takeover inv_wmrepair_reason inv_wmrepair_action inv_wmpred_info; do   # dev460 x 2
  for c in 0 1 2; do for rep in 0 1; do
    nohup $PY -m preexperiments.react_study.run_episodes --stage 38 --split train --games_file $S3/raw/eval460_chunk$c \
      --arm $arm --wm_role wm_alt --label p4b_${arm}_wm14 --rep $rep --protocol v2 --variant list --gate_seed 2027 \
      --prefix p4b_${arm}_wm14_c${c}_ --workers 6 > $O/probe_feasibility/logs/p4b_${arm}_wm14_c${c}_rep${rep}.log 2>&1 &
  done; done
done
for arm in inv_takeover inv_wmpred inv_wmpred_info inv_wmrepair_reason inv_wmrepair_action; do   # fresh600 x 3
  for c in 0 1; do for rep in 0 1 2; do
    nohup $PY -m preexperiments.react_study.run_episodes --stage 37 --split train --games_file $F/raw/fresh600_chunk$c \
      --arm $arm --wm_role wm_alt --label p4b_${arm}_wm14 --rep $rep --protocol v2 --variant list --gate_seed 2027 \
      --prefix fresh_p4b_${arm}_wm14_c${c}_ --workers 5 > $F/logs/fresh_p4b_${arm}_wm14_c${c}_rep${rep}.log 2>&1 &
  done; done
done

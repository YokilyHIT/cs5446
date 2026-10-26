#!/bin/bash
# Phase 2(a) (14B planner, SAME 127 states as 4B): all arms fresh (no prior reuse), K=8, regen=2 on point_id%4==0.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh; P14=1 source outputs/react_study/r4_common/env_r4.sh
O=outputs/react_study
for k in $(seq 0 7); do
  nohup $PY -m preexperiments.react_study.branch_r4 --stage 32 \
    --points $O/step0_protocol_v2_measurement/raw/branch_points.jsonl --only_ids $O/r4_common/raw/unbiased127_point_ids.txt \
    --out p2_14b_same.jsonl --regen 2 --regen_mod 4 --workers 2 --cont_workers 6 --shard $k --n_shards 8 \
    > $O/p2_branch_labels/logs/p2_14b_same_shard$k.log 2>&1 &
done

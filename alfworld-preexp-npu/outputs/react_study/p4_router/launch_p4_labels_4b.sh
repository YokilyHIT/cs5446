#!/bin/bash
# Phase 4 (4B planner): label-pool states (state from rep0 trajectory, group by rep1: 174 solvable + 200 unsolved),
# arms base/RT/W4/W14/oracle, K=8 (reliability 0.82 vs 0.70 at K=4; kept for pooling with the 127 step-0c states).
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh; P14=0 source outputs/react_study/r4_common/env_r4.sh
O=outputs/react_study
for k in $(seq 0 11); do
  nohup $PY -m preexperiments.react_study.branch_r4 --stage 34 --points p4b_label_points.jsonl --out p4_4b_label.jsonl \
    --arms base,RT,W4,W14,oracle --workers 2 --cont_workers 6 --shard $k --n_shards 12 \
    > $O/p4_router/logs/p4_4b_label_shard$k.log 2>&1 &
done

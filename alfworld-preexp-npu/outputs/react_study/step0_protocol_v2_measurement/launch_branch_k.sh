#!/bin/bash
# Step 0c: K=8 continuations per distinct first action, 200 points, 20 shards x 3 workers.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES=$(for p in $(seq 8001 8008); do echo -n "http://127.0.0.1:$p/v1,"; done)
S0=outputs/react_study/step0_protocol_v2_measurement
for k in $(seq 0 19); do
  nohup $PY -m preexperiments.react_study.branch_k --stage 10 --variant list --K 8 --workers 3 \
    --shard $k --n_shards 20 > $S0/logs/branch_k_shard$k.log 2>&1 &
done

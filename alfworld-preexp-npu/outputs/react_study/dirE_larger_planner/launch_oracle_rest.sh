#!/bin/bash
# Direction E oracle: remaining tasks split into 8 parts per rep, 4 threads per process (env lock is per process).
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES="http://127.0.0.1:8001/v1,http://127.0.0.1:8002/v1"
export PREEXP_PLANNER_BASES=$(for p in $(seq 8011 8016); do echo -n "http://127.0.0.1:$p/v1,"; done)
export PREEXP_PLANNER_MODEL="Qwen/Qwen3-14B"
export PREEXP_PLANNER_CHAT_KWARGS='{"enable_thinking": false}'
SE=outputs/react_study/dirE_larger_planner
for rep in 0 1; do for k in 0 1 2 3 4 5 6 7; do
  nohup $PY -m preexperiments.react_study.run_episodes --stage 23 --split train --protocol v2 --variant list --gate_seed 2027 \
    --rep $rep --games_file $SE/raw/oracle_rest_rep${rep}_part$k --arm oracle --label p14b_oracle --prefix p14b_oracle_r${k}_ \
    --workers 4 > $SE/logs/oracle_rest_r${k}_rep$rep.log 2>&1 &
done; done

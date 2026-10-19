#!/bin/bash
# Step 4 (frozen, see tables/frozen_config.json): unseen 134 tasks.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES=$(for p in $(seq 8001 8008); do echo -n "http://127.0.0.1:$p/v1,"; done)
S4=outputs/react_study/step4_unseen_test
COMMON="--stage 14 --split eval_out_of_distribution --protocol v2 --variant list --second_call_when_closed"
for rep in 0 1 2 3 4; do for arm in none always; do
  nohup $PY -m preexperiments.react_study.run_episodes $COMMON --arm $arm --rep $rep --prefix unseen_ --workers 16 \
    > $S4/logs/unseen_${arm}_rep${rep}.log 2>&1 &
done; done
for rep in 0 1 2; do
  for arm in loop_hint gate_stuck; do
    nohup $PY -m preexperiments.react_study.run_episodes $COMMON --arm $arm --rep $rep --prefix unseen_ --workers 16 \
      > $S4/logs/unseen_${arm}_rep${rep}.log 2>&1 &
  done
  for c in 0 1 2 3; do
    nohup $PY -m preexperiments.react_study.run_episodes $COMMON --arm oracle --rep $rep --games_file $S4/raw/unseen134_chunk$c \
      --prefix unseen_o${c}_ --workers 5 > $S4/logs/unseen_o${c}_oracle_rep${rep}.log 2>&1 &
  done
done

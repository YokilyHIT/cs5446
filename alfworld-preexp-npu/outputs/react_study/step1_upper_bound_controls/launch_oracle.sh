#!/bin/bash
# Step 1a oracle arm: 12 chunks x 2 reps, 4 workers each (env lock is per process).
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES=$(for p in $(seq 8001 8008); do echo -n "http://127.0.0.1:$p/v1,"; done)
S0=outputs/react_study/step0_protocol_v2_measurement; S1=outputs/react_study/step1_upper_bound_controls
[ -f $S1/raw/oracle_chunk00 ] || split -n l/12 -d -a 2 $S0/raw/devpool600_games.txt $S1/raw/oracle_chunk
for c in $(seq -w 0 11); do for rep in 0 1; do
  nohup $PY -m preexperiments.react_study.run_episodes --stage 11 --split train --games_file $S1/raw/oracle_chunk$c \
    --arm oracle --rep $rep --protocol v2 --variant list --second_call_when_closed --prefix dev_v2_o${c}_ --workers 4 \
    > $S1/logs/dev_v2_o${c}_oracle_rep${rep}.log 2>&1 &
done; done

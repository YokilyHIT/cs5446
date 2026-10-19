#!/bin/bash
# Direction E: Qwen3-14B planner (thinking disabled) + Qwen3-4B WM; dev460, REP (default 0).
REP=${REP:-0}
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES="http://127.0.0.1:8001/v1,http://127.0.0.1:8002/v1"
export PREEXP_PLANNER_BASES=$(for p in $(seq 8011 8016); do echo -n "http://127.0.0.1:$p/v1,"; done)
export PREEXP_PLANNER_MODEL="Qwen/Qwen3-14B"
export PREEXP_PLANNER_CHAT_KWARGS='{"enable_thinking": false}'
S3=outputs/react_study/step3_gating; SE=outputs/react_study/dirE_larger_planner
C="--stage 23 --split train --protocol v2 --variant list --gate_seed 2027 --rep $REP"
for c in 0 1 2; do
  G="--games_file $S3/raw/eval460_chunk$c"
  nohup $PY -m preexperiments.react_study.run_episodes $C $G --arm none --label p14b_none --prefix p14b_none_c${c}_ --workers 12 > $SE/logs/none_c${c}_rep$REP.log 2>&1 &
  nohup $PY -m preexperiments.react_study.run_episodes $C $G --arm always --label p14b_always --prefix p14b_always_c${c}_ --workers 12 > $SE/logs/always_c${c}_rep$REP.log 2>&1 &
  nohup $PY -m preexperiments.react_study.run_episodes $C $G --arm random_pre --p_gate 0.3 --label p14b_random_pre_nc_p0.3 --prefix p14b_random_c${c}_ --workers 12 > $SE/logs/random_c${c}_rep$REP.log 2>&1 &
done
for c in 0 1 2; do  # oracle: smaller per-process thread count (env-heavy)
  nohup $PY -m preexperiments.react_study.run_episodes $C --games_file $S3/raw/eval460_chunk$c --arm oracle --label p14b_oracle --prefix p14b_oracle_c${c}_ --workers 8 > $SE/logs/oracle_c${c}_rep$REP.log 2>&1 &
done

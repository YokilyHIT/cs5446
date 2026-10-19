#!/bin/bash
# POST-HOC controls (added after seeing step-4 results; not part of the frozen config):
# selective without memory (tau from step 3) and random_pre p=0.3, 3 reps each, unseen 134.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES=$(for p in $(seq 8001 8008); do echo -n "http://127.0.0.1:$p/v1,"; done)
S4=outputs/react_study/step4_unseen_test
TAU=$(python3 -c "import json;print(json.load(open('outputs/react_study/step3_gating/tables/gate_calibration.json'))['tau_usage30'])")
COMMON="--stage 14 --split eval_out_of_distribution --protocol v2 --variant list --second_call_when_closed"
for rep in 0 1 2; do
  nohup $PY -m preexperiments.react_study.run_episodes $COMMON --arm selective --tau $TAU --rep $rep --prefix posthoc_nomem_ --workers 16 > $S4/logs/posthoc_selective_nomem_rep$rep.log 2>&1 &
  nohup $PY -m preexperiments.react_study.run_episodes $COMMON --arm random_pre --p_gate 0.3 --gate_seed 2027 --rep $rep --prefix posthoc_ --workers 16 > $S4/logs/posthoc_random_pre_rep$rep.log 2>&1 &
done

#!/bin/bash
# Step 4: WorldEvolver-style selective foresight + online Episodic Memory, 5 SEQUENTIAL attempts;
# attempt k is seeded with attempt k-1's final bank (memory persists across attempts).
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES=$(for p in $(seq 8001 8008); do echo -n "http://127.0.0.1:$p/v1,"; done)
S4=outputs/react_study/step4_unseen_test
TAU=$(python3 -c "import json;print(json.load(open('$S4/tables/frozen_config.json'))['tau_em'])")
for rep in 0 1 2 3 4; do
  INIT=""
  [ $rep -gt 0 ] && INIT="--memory_init $S4/raw/eval_out_of_distribution/unseen_selective__rep$((rep-1)).memory.jsonl"
  $PY -m preexperiments.react_study.run_episodes --stage 14 --split eval_out_of_distribution --protocol v2 --variant list \
    --second_call_when_closed --arm selective --tau $TAU --memory online $INIT --rep $rep --prefix unseen_ --workers 24 \
    > $S4/logs/unseen_selective_em_attempt$((rep+1)).log 2>&1
done

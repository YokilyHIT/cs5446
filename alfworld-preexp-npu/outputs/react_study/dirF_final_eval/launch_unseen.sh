#!/bin/bash
# Direction F: pre-registered final test (tables/preregistration.json) on unseen 134.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
export PREEXP_API_BASES=$(for p in $(seq 8001 8008); do echo -n "http://127.0.0.1:$p/v1,"; done)
SF=outputs/react_study/dirF_final_eval
C="--stage 24 --split eval_out_of_distribution --protocol v2 --variant list --gate_seed 2027"
for rep in 0 1 2 3 4; do
  nohup $PY -m preexperiments.react_study.run_episodes $C --arm gate_unc --label gate_unc --rep $rep --prefix unseen_gate_unc_ --workers 16 > $SF/logs/gate_unc_rep$rep.log 2>&1 &
  nohup $PY -m preexperiments.react_study.run_episodes $C --arm fore_topk --label fore_topk_p0.3 --p_gate 0.3 --rep $rep --prefix unseen_fore_topk_ --workers 16 > $SF/logs/fore_topk_rep$rep.log 2>&1 &
  nohup $PY -m preexperiments.react_study.run_episodes $C --arm explore_stuck --label explore_stuck --rep $rep --prefix unseen_explore_stuck_ --workers 16 > $SF/logs/explore_stuck_rep$rep.log 2>&1 &
  nohup $PY -m preexperiments.react_study.run_episodes $C --arm random_pre --label random_pre_nc_p0.3 --p_gate 0.3 --rep $rep --prefix unseen_random_pre_nc_ --workers 16 > $SF/logs/random_pre_nc_rep$rep.log 2>&1 &
done

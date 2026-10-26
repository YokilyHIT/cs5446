#!/bin/bash
# Round 4 trajectories for state sampling / difficulty: `none` x 2 reps with record_state.
#   14B on branch140 (the 140 step-0c tasks, disjoint from dev460); 4B and 14B on label_pool448.
cd /home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu
source /home/ma-user/work/5446/preexp_env/env.sh
O=outputs/react_study; R=$O/r4_common/raw
C="--stage 30 --split train --protocol v2 --variant list --gate_seed 2027 --arm none --record_state"
for rep in 0 1; do
  (P14=1 source $O/r4_common/env_r4.sh; nohup $PY -m preexperiments.react_study.run_episodes $C --rep $rep --games_file $R/branch140_games.txt --label p14b_none --prefix p14b_branch140_ --workers 16 > $O/r4_common/logs/p14b_branch140_rep$rep.log 2>&1 &)
  (P14=1 source $O/r4_common/env_r4.sh; nohup $PY -m preexperiments.react_study.run_episodes $C --rep $rep --games_file $R/label_pool500_games.txt --label p14b_none --prefix p14b_label_ --workers 16 > $O/r4_common/logs/p14b_label_rep$rep.log 2>&1 &)
  (P14=0 source $O/r4_common/env_r4.sh; nohup $PY -m preexperiments.react_study.run_episodes $C --rep $rep --games_file $R/label_pool500_games.txt --label none --prefix p4b_label_ --workers 16 > $O/r4_common/logs/p4b_label_rep$rep.log 2>&1 &)
done

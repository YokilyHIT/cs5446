# Round 4 endpoints (source after preexp_env/env.sh). 4B: 8001.., 14B: 8011.. (start_servers_r4.sh)
N4=${N4:-4}
export PREEXP_API_BASES=$(for i in $(seq 1 $N4); do echo -n "http://127.0.0.1:$((8000+i))/v1,"; done)
export PREEXP_WM_ALT_BASES=$(for i in $(seq 1 $((8-N4))); do echo -n "http://127.0.0.1:$((8010+i))/v1,"; done)
export PREEXP_WM_ALT_MODEL="Qwen/Qwen3-14B"
export PREEXP_WM_ALT_CHAT_KWARGS='{"enable_thinking": false}'
# planner = 14B only when P14=1
if [ "${P14:-0}" = "1" ]; then
  export PREEXP_PLANNER_BASES=$PREEXP_WM_ALT_BASES
  export PREEXP_PLANNER_MODEL="Qwen/Qwen3-14B"
  export PREEXP_PLANNER_CHAT_KWARGS='{"enable_thinking": false}'
else
  unset PREEXP_PLANNER_BASES PREEXP_PLANNER_MODEL PREEXP_PLANNER_CHAT_KWARGS
fi

#!/usr/bin/env bash
# TEMPLATE -- edit BASE/DST/the file:size list below for your host and model
# before use. Only needed on hosts where a normal modelscope/huggingface-cli
# download keeps failing (see README_NPU_SETUP.md's troubleshooting
# section); most hosts should just use scripts/setup_env_npu.sh instead.
#
# 多进程 curl 分块下载。两个约束叠加决定了这个形状：
#   1) 单连接传输 ~7MB 后会被中断  -> 每个请求只取 5MB
#   2) Python 多线程受 GIL/SSL 限制只能跑到 ~1.5MB/s -> 用独立 curl 进程绕开
set -u
BASE=https://hf-mirror.com/Qwen/Qwen3-4B-Instruct-2507/resolve/main
DST=/home/ma-user/work/5446/preexp_env/models/Qwen3-4B-Instruct-2507
BLK=$((5*1024*1024)); PAR=24
for f in model-00001-of-00003.safetensors:3957900840 model-00002-of-00003.safetensors:3987450520; do
  NAME=${f%%:*}; SZ=${f##*:}
  BD=$DST/.blocks_$NAME; mkdir -p $BD
  N=$(( (SZ + BLK - 1) / BLK ))
  echo "$NAME size=$SZ blocks=$N"
  for pass in 1 2 3 4 5; do
    MISSING=0
    for i in $(seq 0 $((N-1))); do
      S=$(( i*BLK )); E=$(( S+BLK-1 )); [ $E -ge $SZ ] && E=$((SZ-1))
      WANT=$((E-S+1)); P=$(printf "%s/%05d" $BD $i)
      HAVE=$(stat -c%s "$P" 2>/dev/null || echo 0)
      [ "$HAVE" = "$WANT" ] && continue
      MISSING=$((MISSING+1)); echo "$i $S $E $P"
    done > /tmp/jobs_$NAME.txt
    CNT=$(wc -l < /tmp/jobs_$NAME.txt)
    echo "  pass$pass: $CNT blocks missing"
    [ "$CNT" = "0" ] && break
    awk '{print $2" "$3" "$4}' /tmp/jobs_$NAME.txt | \
      xargs -P $PAR -n 3 bash -c 'curl -sSL --max-time 180 --retry 3 --retry-delay 2 -r "$0-$1" -o "$2" '"$BASE/$NAME"' 2>/dev/null || true'
  done
  cat $(ls $BD/* | sort) > $DST/$NAME
  GOT=$(stat -c%s $DST/$NAME)
  echo "$NAME -> $GOT (expect $SZ) $([ "$GOT" = "$SZ" ] && echo OK && rm -rf $BD || echo MISMATCH)"
done
echo DL_BLOCKS_DONE

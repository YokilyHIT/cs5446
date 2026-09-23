"""TEMPLATE -- edit BASE/DST/FILES below for your host and model before use.
Only needed on hosts where a normal `modelscope`/`huggingface-cli` download
keeps failing (see README_NPU_SETUP.md's troubleshooting section); most
hosts should just use scripts/setup_env_npu.sh's model-download step instead.

Qwen3-4B 权重下载器：小块 + 预分配 + seek 写入 + 断点续传。

为什么是这个形状：这台机器到 hf-mirror 的连接稳定在传输约 7MB 后被中断
（ChunkedEncodingError / IncompleteRead）。用"每个连接负责 ~500MB 大段"的写法时，
几乎每个连接都会在 7MB 处断掉，重连开销把有效带宽吃光。
所以改成每个请求只取 5MB —— 小于中断阈值，请求能干净完成 —— 再用线程池把很多
这样的小请求并发起来。输出文件预分配到最终大小，各 worker 用 seek 写自己的偏移，
块完成情况记在 .blocks 状态文件里，中断后重跑可续传。
"""
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = "https://hf-mirror.com/Qwen/Qwen3-4B-Instruct-2507/resolve/main"
DST = "/home/ma-user/work/5446/preexp_env/models/Qwen3-4B-Instruct-2507"
FILES = ["model-00001-of-00003.safetensors", "model-00002-of-00003.safetensors"]
BLOCK = 5 * 1024 * 1024      # 小于观测到的 ~7MB 中断阈值
WORKERS = 32
MAX_RETRY = 100

lock = threading.Lock()
done_evt = threading.Event()
counter = {"done": 0, "total": 0}


def remote_size(f):
    r = requests.head(f"{BASE}/{f}", allow_redirects=True, timeout=60)
    r.raise_for_status()
    return int(r.headers["content-length"])


def load_state(f, nblocks):
    p = os.path.join(DST, f".{f}.blocks")
    if os.path.exists(p):
        data = open(p, "rb").read()
        if len(data) == nblocks:
            return bytearray(data)
    return bytearray(nblocks)


def save_state(f, state):
    with open(os.path.join(DST, f".{f}.blocks"), "wb") as fh:
        fh.write(bytes(state))


def fetch_block(f, path, state, idx, start, end):
    if state[idx]:
        return True
    for attempt in range(MAX_RETRY):
        try:
            r = requests.get(
                f"{BASE}/{f}",
                headers={"Range": f"bytes={start}-{end}"},
                timeout=(30, 90),
            )
            r.raise_for_status()
            buf = r.content
            if len(buf) != end - start + 1:
                raise IOError(f"short block {len(buf)} != {end - start + 1}")
            with lock:
                with open(path, "r+b") as fh:
                    fh.seek(start)
                    fh.write(buf)
                state[idx] = 1
                counter["done"] += 1
            return True
        except Exception:
            time.sleep(min(1 + attempt * 0.5, 10))
    return False


def progress():
    t0 = time.time()
    last = 0
    while not done_evt.is_set():
        done_evt.wait(30)
        with lock:
            d, t = counter["done"], counter["total"]
        mb = (d - last) * BLOCK / 2**20 / 30
        last = d
        print(
            f"  {d}/{t} blocks ({d * BLOCK / 2**30:.2f} GiB) "
            f"~{mb:.1f} MB/s  elapsed {time.time() - t0:.0f}s",
            flush=True,
        )


def main():
    sizes = {f: remote_size(f) for f in FILES}
    jobs = []
    states = {}
    for f, total in sizes.items():
        path = os.path.join(DST, f)
        nblocks = (total + BLOCK - 1) // BLOCK
        state = load_state(f, nblocks)
        states[f] = state
        # 预分配到最终大小（已存在且大小正确则保留，配合 .blocks 续传）
        if not os.path.exists(path) or os.path.getsize(path) != total:
            with open(path, "wb") as fh:
                fh.truncate(total)
            state[:] = bytearray(nblocks)
        counter["total"] += nblocks
        counter["done"] += sum(state)
        print(f"{f} size={total} blocks={nblocks} already={sum(state)}", flush=True)
        for i in range(nblocks):
            if not state[i]:
                jobs.append((f, path, state, i, i * BLOCK, min((i + 1) * BLOCK - 1, total - 1)))

    threading.Thread(target=progress, daemon=True).start()
    saver = threading.Thread(
        target=lambda: [
            (done_evt.wait(30), [save_state(f, s) for f, s in states.items()])
            for _ in iter(lambda: not done_evt.is_set(), False)
        ],
        daemon=True,
    )
    saver.start()

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(lambda a: fetch_block(*a), jobs))
    done_evt.set()
    for f, s in states.items():
        save_state(f, s)

    if not all(results):
        print(f"FAILED: {results.count(False)} blocks could not be fetched")
        return 1

    for f, total in sizes.items():
        got = os.path.getsize(os.path.join(DST, f))
        print(f"{f} -> {got} (expect {total}) {'OK' if got == total else 'MISMATCH'}", flush=True)
        if got == total:
            sp = os.path.join(DST, f".{f}.blocks")
            if os.path.exists(sp):
                os.remove(sp)
    print("DL_SHARDS_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())

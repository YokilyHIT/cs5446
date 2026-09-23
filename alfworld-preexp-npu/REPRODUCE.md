# 复现指南

从一台干净机器开始，把这两个预实验完整跑起来。

原始需求规范是 `两个方向_预实验设计_ClaudeCode可复现版.md`（本仓库上一级目录）。
本文中提到的 **§N** 都指该规范的章节号。

本流程在 **Ascend 910B3 ×2 / aarch64 / Python 3.11.13 / CANN 8.3.RC2** 上完整验证通过：
体检脚本全绿，`pytest preexperiments/tests` 17/17 通过，§37 要求的 17 个验收文件全部产出。
x86 + NVIDIA 的机器流程相同，只有第 1 步和第 7 步的硬件相关部分不同（各步有注记）。

> **动手跑正式实验之前，请先读 `CHANGES_AND_KNOWN_ISSUES.md` 的「已知未修」一节。**
> 那里列了 7 条已诊断清楚但尚未修复的问题，其中 2 条会直接污染实验 B 的核心指标。

---

## 第 0 步　准备目录

```bash
export BASE=$HOME/preexp_env          # 权重/数据/虚拟环境，约 11GB
export REPO=$(pwd)                    # 本仓库根目录（alfworld-preexp-npu/）
mkdir -p $BASE/{alfworld_data,models,logs,diagnostics}
```

## 第 1 步　Python 环境

```bash
python3 -m venv --system-site-packages $BASE/venv   # 继承镜像自带的 torch/torch_npu/vllm
$BASE/venv/bin/pip install alfworld pytest \
    "sentence-transformers==3.3.1" "transformers==4.57.1"
```

> ⚠️ **版本必须钉死。** `sentence-transformers` 新版会把 `transformers` 拉到 5.x，
> 而 vllm-ascend 0.11.0 要求 `transformers<=4.57.1`，装完之后 vLLM 就起不来了。

> ⚠️ **aarch64 机器额外一步。** TextWorld 的 `setup.py` 会执行 `setup.sh`，后者解压
> `inform7-compilers_6M62_${ARCH}.tar.gz`；Inform7 6M62 只发布了
> i386 / x86_64 / ppc / armv6lhf，**没有 aarch64**，整个 wheel 构建会失败。
> 这些二进制是 Inform7 编译器和 glulx 解释器，只在"从零生成新 TextWorld 游戏"时才需要；
> ALFWorld 跑的是预生成的 `.tw-pddl`，由纯 Python 的 `textworld/envs/pddl` 执行，缺了不影响。
>
> ```bash
> cd /tmp
> $BASE/venv/bin/pip download --no-deps --no-binary :all: textworld==1.7.0
> tar xzf textworld-1.7.0.tar.gz && cd textworld-1.7.0
> # 把 setup.sh 里解压架构包的那两行改成"缺对应架构就警告并跳过"
> python - <<'PY'
> s = open('setup.sh').read()
> old = '''        ARCH=$(uname -m)
>         tar xzf "inform7-compilers_6M62_${ARCH}.tar.gz"
>         tar xzf "inform7-interpreters_6M62_${ARCH}.tar.gz"'''
> new = '''        ARCH=$(uname -m)
>         if [ -e "inform7-compilers_6M62_${ARCH}.tar.gz" ]; then
>             tar xzf "inform7-compilers_6M62_${ARCH}.tar.gz"
>             tar xzf "inform7-interpreters_6M62_${ARCH}.tar.gz"
>         else
>             echo "WARNING: no Inform7 6M62 binaries for ARCH=${ARCH}; skipping."
>         fi'''
> assert old in s
> open('setup.sh','w').write(s.replace(old, new))
> PY
> $BASE/venv/bin/pip install .
> ```
>
> x86_64 机器跳过这一段，`pip install alfworld` 会自动装好 textworld。

## 第 2 步　ALFWorld 数据集（约 1.5GB）

```bash
export ALFWORLD_DATA=$BASE/alfworld_data
$BASE/venv/bin/alfworld-download
```

验证：

```bash
find $ALFWORLD_DATA/json_2.1.1 -name "game.tw-pddl" | wc -l    # 应为 4027
ls $ALFWORLD_DATA/json_2.1.1                                    # train valid_seen valid_train valid_unseen
```

`train` 有 3553 个可解游戏，`valid_seen`（即规范里的 `eval_in_distribution`）有 140 个，
六类任务齐全（`pick_and_place_simple` 35 / `pick_clean_then_place` 27 / `pick_cool_then_place` 25 /
`pick_two_obj_and_place` 24 / `pick_heat_then_place` 16 / `look_at_obj_in_light` 13）。

## 第 3 步　模型权重（7.5GB）+ 词向量模型（90MB）

```bash
# 主模型
$BASE/venv/bin/pip install modelscope
$BASE/venv/bin/python -c "
from modelscope import snapshot_download
snapshot_download('Qwen/Qwen3-4B-Instruct-2507', local_dir='$BASE/models/Qwen3-4B-Instruct-2507')"

# 词向量模型：实验 A 挑相关任务、实验 B 算语义正确性都要用（§10.2 / §24）
export HF_ENDPOINT=https://hf-mirror.com
D=$BASE/models/all-MiniLM-L6-v2; mkdir -p $D/1_Pooling
B=https://hf-mirror.com/sentence-transformers/all-MiniLM-L6-v2/resolve/main
for f in config.json config_sentence_transformers.json modules.json sentence_bert_config.json \
         special_tokens_map.json tokenizer.json tokenizer_config.json vocab.txt \
         model.safetensors 1_Pooling/config.json; do
  curl -sL --retry 5 -o "$D/$f" "$B/$f"; done
```

## 第 4 步　环境变量

```bash
cat > $BASE/env.sh <<EOF
export PREEXP_BASE=$BASE
export ALFWORLD_DATA=\$PREEXP_BASE/alfworld_data
export HF_HOME=\$PREEXP_BASE/hf_home
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_OFFLINE=1
# 必须 APPEND，不能覆盖（见下方警告）
export PYTHONPATH=$REPO\${PYTHONPATH:+:\$PYTHONPATH}
export PY=\$PREEXP_BASE/venv/bin/python
# 路径类覆盖，见 preexperiments/common/logging_utils.py::_ENV_OVERRIDES
export PREEXP_EMBEDDING_MODEL=\$PREEXP_BASE/models/all-MiniLM-L6-v2
export PREEXP_EMBEDDING_DEVICE=cpu
export PREEXP_API_BASE=http://127.0.0.1:8001/v1
EOF
source $BASE/env.sh
```

> ⚠️ **`PYTHONPATH` 必须追加，不能覆盖。** 昇腾容器通常已经把 CANN 的
> `python/site-packages`（里面有 `acl` 模块）放进 `PYTHONPATH` 了。直接
> `export PYTHONPATH=<仓库路径>` 会把它挤掉，vLLM 随后以
> `ModuleNotFoundError: No module named 'acl'` 启动失败，而报错信息完全看不出根因。

## 第 5 步　核对 ALFWorld 接口假设（§38 第 1 步）

```bash
cd $REPO && $PY scripts/inspect_alfworld_api.py
```

期望结尾输出 `All ALFWorld API assumptions in alfworld_runner.py check out for this install.`，
中间应看到 info 的三个 key 都命中：`extra.gamefile` / `admissible_commands` / `won`。

对不上的话脚本会直接告诉你该改 `preexperiments/common/alfworld_runner.py` 里的哪一行。

## 第 6 步　起模型服务

```bash
MODEL_PATH=$BASE/models/Qwen3-4B-Instruct-2507 NPU_DEVICES=0 \
  bash scripts/start_vllm_npu.sh > $BASE/logs/vllm.log 2>&1 &
sleep 300
curl -s http://127.0.0.1:8001/v1/models      # 应返回 Qwen/Qwen3-4B-Instruct-2507，max_model_len 32768
```

> NVIDIA 机器改用规范 §1.4 的原始命令即可
> （`CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server --model ... --dtype bfloat16 --max-model-len 32768`），
> 其余完全不变——实验代码只通过 HTTP 跟服务对话，不关心底层是 GPU 还是 NPU。

## 第 7 步　单元测试

```bash
$PY -m pytest preexperiments/tests -q          # 应 17 passed
```

## 第 8 步　体检（正式实验前必须全绿）

```bash
export PATH=$BASE/venv/bin:$PATH
bash scripts/run_smoke_test.sh 2>&1 | tee $BASE/logs/smoke.log
```

里面有**两道硬闸门。它们失败是好事**，说明闸门在干活：

- **Step 2b 强制动作率 > 20%** —— 模型输出匹配不上合法动作、被 `ground_action()` 的兜底
  逻辑乱选。本机第一次跑就是 **51.3%**，靠约束解码降到 0%（详见
  `CHANGES_AND_KNOWN_ISSUES.md` 的 VALID-1）。
- **重放失败率 > 10%** —— 实验 B 的因果对比不成立，§39 明确禁止继续。
  失败时看 `results/B_restore_failures.jsonl` 里的 expected/got 差异。

## 第 9 步　测准基线成功率（§39 的决策依据，**不能跳过**）

后面要不要动实验设计，完全取决于这一步的数字。

```bash
$PY tools/measure_baseline.py --workers 16 --tag spec30
$PY tools/measure_baseline.py --workers 16 --max_steps 50 --tag spec50
$PY tools/measure_baseline.py --workers 16 --prompt_style adamem_think --tag adamem30
```

本机结果见 `diagnostics/stage0_baseline.md`，摘要：

| | 规范提示词 30 步 | 规范提示词 50 步 | AdaMEM `<think>` 30 步 |
|---|---|---|---|
| 成功率 | 3/30 = 10.0% | 4/30 = 13.3% | **8/30 = 26.7%** |
| 打转 episode | 7/30 (23%) | 8/30 (27%) | 3/30 (10%) |
| 强制动作率 | 0.0% | 0.0% | 0.0% |

判断规则：

- 成功率 **≥ 25%** → 保持 `prompt_style: "spec"`，进第 10 步
- 成功率低**且多数在打转** → §39 第③条：改 `prompt_style: "adamem_think"`，重测
- 成功率低但**不是打转**（动作多样、像在认真搜索）→ §39 第②条：提高 `max_episode_steps`，重测

## 第 10 步　正式实验

```bash
bash scripts/run_experiment_B.sh     # 建议先跑 B：更慢，能更早暴露问题
bash scripts/run_experiment_A.sh
$PY scripts/generate_report.py
$PY -m pytest preexperiments/tests -q
```

产出：`results/*.jsonl|csv`、`figures/*.png`、`reports/preliminary_results.md`。

---

## 本机验证环境（供对照）

| 项 | 值 |
|---|---|
| 硬件 | Ascend 910B3 ×2（64GB HBM/卡），实验只用 1 张 |
| 系统 | Linux aarch64 (HCE2)，Python 3.11.13 |
| CANN | 8.3.RC2 |
| torch / torch_npu | 2.7.1+cpu / 2.7.1 |
| vllm / vllm-ascend | 0.11.0 / 0.11.0 |
| alfworld / textworld | 0.4.2 / 1.7.0（打过 setup.sh 补丁） |
| sentence-transformers / transformers | 3.3.1 / 4.57.1 |
| 模型 | Qwen3-4B-Instruct-2507，bf16，max-model-len 32768 |
| AdaMEM commit | `4ea93e239f8dbec2fa6013a28bc8555419037e12` |

### 实测性能数字（用于估时间）

- vLLM 吞吐：单路 37 tok/s → 8 路 273 tok/s → **16 路 513 tok/s**，单请求延迟几乎不变
- 环境构建：train split 约 15s/次，eval split 约 0.6s/次
- 重放一个决策点：4–6.5s（其中约 3.5s 是重建环境的固定开销）
- 30 个 episode：spec 提示词 16 路并发约 11 分钟；adamem_think 约 16 分钟

---

## 常见问题

| 症状 | 原因 |
|---|---|
| `ModuleNotFoundError: No module named 'acl'` | `PYTHONPATH` 被覆盖了，见第 4 步 |
| `KeyError: 'dagger'` | `alfworld_base_config.yaml` 的 `general.training_method` 不是 `dqn` |
| `ImportError: cannot import name 'AlfredTWEnv'` | alfworld ≥0.4 改了导入路径，本仓库已兼容；确认用的是打过补丁的版本 |
| textworld 装不上，`setup.sh` 报 tar 错 | aarch64 缺 Inform7 二进制，见第 1 步 |
| vLLM 起不来，`transformers` 版本报错 | `transformers` 被 sentence-transformers 拉到 5.x，见第 1 步 |
| 并发跑时 `KeyError: (2, 0)` 或 `IndexError: pop from empty list` | TextWorld 线程不安全，须经 `_ENV_LOCK`；见 PERF-1 |
| 体检 Step 2b 失败（强制率高） | 模型没从合法动作里选；先看原始输出再判断是格式问题还是能力问题 |

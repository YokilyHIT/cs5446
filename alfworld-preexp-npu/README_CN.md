# 项目说明（中文版）：这个仓库到底做了什么

这份文档回答三个问题：**我做了什么、为什么这么做、你怎么把它跑起来**。

原始需求文档是 `cs5446/两个方向_预实验设计_ClaudeCode可复现版.md`，里面定义了两个"预实验"（不是正式实验，目的是快速判断两个研究方向值不值得深入做）。我把这份规范落地成了一套完整的、能在华为昇腾 NPU 上跑的代码。

---

## 1. 背景：这两个预实验到底在验证什么

### 实验 A：Selective Failure Learning（有选择的失败学习）

**问题**：一个 agent 在 ALFWorld（一个文字版家务模拟环境）里失败了，我们从这次失败里提炼出一条"教训"（lesson），把它塞进以后类似任务的 prompt 里。**但是——是不是所有失败教训都有用？** 会不会有些教训其实没用，甚至会误导 agent 让它在新任务上表现更差（负迁移）？

如果答案是"是，教训质量参差不齐"，那么"如何挑选出真正有用的失败经验"就是一个值得研究的方向。如果答案是"教训基本都有用，随便存都行"，那这个方向就没必要做了。

### 实验 B：Prediction Confidence vs Planning Utility（预测置信度 vs 真实决策价值）

**问题**：让模型在做动作之前先"预测"一下这个动作执行后会发生什么（world model 预测），并让模型给这个预测打一个置信度分数。**问题是——这个置信度分数真的能反映"参考这个预测去重新选择动作"是否真的会帮上忙吗？**

如果"置信度高"不等于"参考预测后选的新动作真的更好"，那说明"只用置信度来决定要不要采纳预测"这个做法本身有漏洞，值得研究一个更好的"要不要相信预测"的判断机制（gate）。

两个实验都不要求证明"我们的方法一定行"，只要求老老实实地测出"这个现象是否存在、存在到什么程度"，然后按照规范里定好的数值门槛给出 GO / WEAK-GO / NO-GO 的结论。

---

## 2. 我做了什么（整体交付物）

原始需求文档假设是在**有 NVIDIA GPU 的机器**上跑（用 `CUDA_VISIBLE_DEVICES` 启动 vLLM）。但你的开发机没有显卡，实际要在**另一台华为昇腾 NPU 服务器**上跑模型推理。所以我做的事情分两部分：

1. **把整套预实验代码从头实现了一遍**（原需求文档只给了"应该做什么"，没有给代码），严格照抄文档里规定的所有 prompt 原文、随机种子、超参数、输出文件名。
2. **把"怎么启动模型服务"这一层适配成 NPU 版本**：把 `CUDA_VISIBLE_DEVICES` 换成 `ASCEND_RT_VISIBLE_DEVICES`，参考你给的 `OpenOneRec-Blue-Zone-main` 仓库里 `benchmarks_green` 目录下已经验证过的 NPU 适配写法（`torch_npu` + `vllm-ascend` + 环境变量切换），并且写了一份完整的 NPU 环境和数据集搭建教程。

代码全部写在 `cs5446/alfworld-preexp-npu/` 这个新目录下，已经提交到 git（commit: "Add NPU-runnable ALFWorld pre-experiment pipeline"）。

**重要说明**：你现在这台电脑没有 GPU/NPU，我也没法在这台机器上装 ALFWorld、vLLM、torch_npu 来真跑一遍。所以我做的验证是：**用 Python 的 `py_compile` 把每一个文件都做了语法检查**（全部通过），并且**手动核对了每个脚本 import 的函数名是否真的在我写的公共模块里存在**（也全部对得上）。但代码有没有"逻辑上真的能跑通"，必须拿到真实的 NPU 机器上，按下面的复现步骤实际跑一遍才能确认——这也是为什么第 4 节里专门有一个"先跑体检脚本，别直接跑正式实验"的强制步骤。

---

## 3. 目录结构和每个文件的作用

```
alfworld-preexp-npu/
├── README.md               # 英文版总览（面向以后可能读代码的人）
├── README_NPU_SETUP.md      # NPU 环境+数据集搭建完整教程（英文，最详细）
├── README_CN.md             # 就是你现在在读的这份
├── requirements.txt         # 这个项目自己需要的 Python 依赖（不含 torch/vllm，那些跟 NPU 驱动版本强绑定，单独装）
│
├── preexperiments/
│   ├── configs/
│   │   ├── preexperiment.yaml         # 全局配置：模型名、采样参数、随机种子、split 名字、各种实验规模参数
│   │   └── alfworld_base_config.yaml  # ALFWorld 环境自己要求的配置格式（跟上面那个不是一回事）
│   │
│   ├── common/               # 两个实验共用的"地基"代码
│   │   ├── llm_client.py     # 跟 vLLM 服务器对话的 HTTP 客户端（只走 OpenAI 兼容接口，不碰 NPU/CUDA）
│   │   ├── prompts.py        # 规范里规定的每一句 prompt 原文，一字不改地抄进来
│   │   ├── alfworld_runner.py# 包装 ALFWorld 环境 + 跑一整个 ReAct agent episode 的循环
│   │   ├── replay_state.py   # "状态还原"：把环境精确恢复到某个历史时刻，实验 B 的核心机制
│   │   ├── embeddings.py     # 句子向量模型（算相似度用）
│   │   ├── stats.py          # bootstrap 置信区间、Spearman 相关系数等统计工具
│   │   └── logging_utils.py  # 统一的 JSONL 读写、给每条记录生成唯一 run_id
│   │
│   ├── failure_selection/    # 实验 A 的全部代码，按顺序运行
│   ├── world_model_utility/  # 实验 B 的全部代码，按顺序运行
│   └── tests/                # 规范里要求的 7 类正确性测试
│
├── scripts/                  # 各种运行脚本（下面第 4 节按顺序讲）
├── results/  figures/  reports/   # 运行之后自动生成的产出（现在是空的，只有占位文件）
```

---

## 4. 怎么复现：完整步骤（在昇腾 NPU 服务器上执行）

下面每一步都写明"这一步在做什么"和"为什么需要它"。

### 第 0 步：把代码传到 NPU 服务器上

这台开发机只是用来写代码，不能跑。用 `git clone` 或者 `scp`/`rsync` 把 `alfworld-preexp-npu/` 整个目录搬到有昇腾卡的 Linux 服务器上。

### 第 1 步：搭建环境

```bash
bash scripts/setup_env_npu.sh
```

**这一步做什么**：这是一个一键脚本，按顺序完成：
1. 检查 `npu-smi info` 能不能看到卡（驱动是否装好）；
2. 装 CANN 工具包（华为的"NPU 版 CUDA"）；
3. 建一个 conda 环境（Python 3.10）；
4. 装 `torch` + `torch_npu`（这两个版本必须严格匹配你的 CANN 版本，装错版本的典型症状是 `torch_npu.npu.is_available()` 返回 `False` 但没有任何报错）；
5. 装 `vllm` + `vllm-ascend`（vLLM 的昇腾适配插件）；
6. 装这个项目自己的依赖（`requirements.txt`）；
7. 把 AdaMEM（原需求文档指定的 agent 代码参考基座）clone 下来，记录它的 git commit hash；
8. 装 ALFWorld，下载它的数据集（`alfworld-download`）；
9. 下载 Qwen3-4B-Instruct-2507 模型权重（默认走 ModelScope，国内 NPU 机器上通常比 HuggingFace 快）。

**为什么要这一步**：所有后面的代码都依赖这些环境。没有这一步，什么都跑不了。

**你需要提前准备**：CANN 的 `.run` 安装包（要去华为官网接受协议下载，不能自动化），以及知道你的卡型号（910A/910B）对应的驱动版本。

### 第 2 步：启动模型服务

```bash
MODEL_PATH=$HOME/models/Qwen3-4B-Instruct-2507 NPU_DEVICES=0 bash scripts/start_vllm_npu.sh
```

**这一步做什么**：在后台启动一个 vLLM 的 HTTP 服务，把 Qwen3-4B 模型跑起来，对外暴露一个跟 OpenAI API 长得一样的接口（`/v1/chat/completions`）。这是原需求文档里 `CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server ...` 那一步的 NPU 版本——把 `CUDA_VISIBLE_DEVICES` 换成了 `ASCEND_RT_VISIBLE_DEVICES`，并且显式清掉 `CUDA_VISIBLE_DEVICES` 防止残留环境变量干扰 vLLM 自动识别硬件。

**为什么要这一步**：后面所有的实验代码都不直接调用模型，而是通过 HTTP 请求这个服务（`preexperiments/common/llm_client.py`）。这样实验代码本身完全不关心底层是 GPU 还是 NPU，只关心一个 HTTP 地址。

**怎么确认成功**：另开一个终端跑 `curl http://127.0.0.1:8001/v1/models`，能返回模型信息就说明启动成功。

### 第 3 步：核对 ALFWorld 的接口假设

```bash
python scripts/inspect_alfworld_api.py
```

**这一步做什么**：`alfworld_runner.py` 里写死了几个关于 ALFWorld 库内部结构的假设（比如"环境返回的 info 字典里，游戏文件路径存在哪个 key 下面"）。这些假设是根据 ALFWorld 主流用法（ReAct、Reflexion 等论文的公开代码都是这么用的）写的，但我没办法在这台机器上装 ALFWorld 去实际验证。这个脚本会在真实环境里把这些假设逐条检查一遍，如果哪条对不上，会直接打印出"应该改 `alfworld_runner.py` 里的哪一行"。

**为什么要这一步**：这是规范原文里明确要求的第一步（"Inspect repository"），也是我在这台无 GPU 机器上唯一没法帮你提前做完的验证——**这一步不过，后面全白搭**。

### 第 4 步：跑体检脚本（正式实验前必须通过）

```bash
bash scripts/run_smoke_test.sh
```

**这一步做什么**（按顺序）：
1. 再跑一遍第 3 步的接口检查；
2. 跑几个不需要真实环境的单元测试（vLLM 客户端能不能正常返回文字、ALFWorld 能不能正常 reset/step）；
3. 跑 5 个训练集 episode + 5 个评估集 episode，确认 agent 循环整体能跑通、没有崩溃；
4. **验证"状态还原"功能**（`test_replay.py`）：同一个任务、同一串历史动作，能不能精确恢复到同一个环境状态。**这是实验 B 能不能做的生死线**——如果这个都做不到，实验 B 里"公平对比两种决策"这件事在逻辑上就不成立，规范里明确写了"这一步失败就禁止继续做实验 B"；
5. 用 10 个决策点跑一遍实验 B 的迷你版；
6. 用 3 个失败案例跑一遍实验 A 的迷你版。

**为什么要这一步**：先小规模跑通，再大规模跑，避免在几百个 episode 跑到一半才发现某个环节从一开始就是错的，浪费大量 GPU/NPU 时间和 API 调用。

### 第 5 步：跑正式实验

```bash
bash scripts/run_experiment_B.sh   # 实验 B，建议先跑（更慢，先跑能更早发现问题）
bash scripts/run_experiment_A.sh   # 实验 A
python scripts/generate_report.py  # 生成最终报告
python -m pytest preexperiments/tests -q   # 跑完整测试套件做最终校验
```

或者一行搞定：

```bash
bash scripts/run_all.sh
```

**实验 A 内部按这个顺序执行**（`scripts/run_experiment_A.sh` 已经把顺序写死了）：

| 脚本 | 作用 |
|---|---|
| `collect_failures.py` | 用"无记忆"agent 在训练集上跑，收集失败案例 |
| `extract_lessons.py` | 从每个失败案例里，用 LLM 提炼出一条"教训" |
| `select_related_tasks.py` | 给每条教训自动挑 3 个"相关的"评估任务（同任务类型 + 语义相似度，程序自动选，不许人工挑） |
| `evaluate_single_lessons.py` | 核心对比实验：同一个任务、同一个随机种子，"不给教训" vs "给教训"，各跑一遍，比较成功率 |
| `score_failure_proxies.py` | 计算两个"提前判断这条教训好不好"的简易信号（新颖度、可迁移性） |
| `evaluate_topk_vs_all.py` | 对比"只存最好的一部分教训"vs"教训全存"，哪个实际效果更好 |
| `analyze.py` | 汇总所有原始数据，算出规范要求的所有统计量，画图，给出 GO/WEAK-GO/NO-GO 结论 |

**实验 B 内部顺序**：

| 脚本 | 作用 |
|---|---|
| `collect_decision_points.py` | 在评估集上跑 agent，挑出 150 个"决策点"（当前有多个候选动作可选的时刻） |
| `generate_foresight.py` | 对每个决策点：先让模型选一个"基础动作"，再让模型预测"如果执行这个动作会发生什么"并打置信度分，再让模型"看到预测之后重新选一次动作" |
| `build_counterfactual_pairs.py` | **最关键的一步**：把环境精确还原到决策点当时的状态，分别执行"原始动作"和"参考预测后选的新动作"，各自继续跑到 episode 结束，看哪个真的成功了 |
| `evaluate_planning_gain.py` | 计算"置信度高但其实帮了倒忙""置信度低但其实帮上了忙"的比例（mismatch rate），以及置信度和"真实是否有用"之间的相关系数 |
| `evaluate_oracle_gate.py` | 计算一个"理论上限"：如果我们能完美判断该不该采纳预测（而不是只看置信度），最多能比现在多赢多少 |
| `analyze.py` | 汇总、画图、给出 GO/WEAK-GO/NO-GO 结论 |

**为什么先跑实验 B 再跑实验 A**：单纯是因为 B 更慢（每个决策点要完整跑两遍 episode），先跑能更早暴露问题，不影响两个实验各自独立的结论。

### 第 6 步：查看结果

跑完之后，去看这一份汇总报告：

```
reports/preliminary_results.md
```

这份报告是按规范里固定的模板自动生成的，包含每个实验的核心数字和最终的 GO / WEAK-GO / NO-GO 结论，以及最后给出"该做候选方向 A 还是候选方向 B，还是都别做"的建议。

原始数据在 `results/*.jsonl` 和 `results/*.csv`，图表在 `figures/*.png`——如果对报告里某个数字有疑问，都可以回到这些原始文件里查。

---

## 5. 几个值得知道的设计决定

- **为什么不直接改 AdaMEM 的代码，而是重新写了一套？** 因为 AdaMEM 内部的 API 没有稳定性保证，直接依赖它的内部实现风险比较大。我选择只把 AdaMEM clone 下来做"参考"和记录 commit hash（写进最终报告，满足规范要求），实际的 ALFWorld 交互逻辑在 `preexperiments/common/alfworld_runner.py` 里重新实现，这样即使 AdaMEM 后续改版，也不会影响这套代码。
- **为什么每个实验最后都有一个独立的 `analyze.py`，而不是让前面的脚本直接算出结论？** 因为要满足"分析脚本必须能只凭硬盘上的原始 JSONL 文件重新算出所有统计量"这条硬性要求（方便复查、方便别人复现你的结论，不依赖内存里的中间状态）。`preexperiments/tests/test_analysis_rebuild.py` 就是专门测这件事的：把 `analyze.py` 跑两遍，检查两次结果是不是完全一样。
- **为什么报告里绝对不会出现"我们的假设已经被证明"这种话？** 这是规范原文的硬性要求（第 43 条）：预实验的目的是"要不要往这个方向投入"的筛选，不是发论文级别的结论。所以所有结论只会用"supported by preliminary evidence / weakly supported / not supported under the current setup"这三种措辞之一。

---

## 6. 如果哪一步跑不通，大概率是什么原因

- **`torch_npu.npu.is_available()` 返回 `False`**：几乎总是 torch/torch_npu/CANN 三个版本没对齐，很少是硬件本身的问题。
- **`inspect_alfworld_api.py` 报错**：说明你装的 ALFWorld 版本内部字段名跟我假设的不一样，脚本会直接告诉你该改 `alfworld_runner.py` 里哪一行。
- **`test_replay.py` 挂了**：**绝对不能跳过去直接跑实验 B**，先把这个修好。
- 其他更多细节（vLLM 起不来、bf16 算子不支持、ALFWorld 成功率太高/太低怎么办等）都写在 `README_NPU_SETUP.md` 第 10 节的排错表里。

---

## 7. 方法论审查后的修正记录

代码写完之后又做了一轮方法论审查，发现并修了 5 个问题，都会实际影响最终结论的可信度：

1. **实验 A 没有"运气基准线"**：以前的代码只要算出教训之间成功率有高有低，就直接当成"教训质量确实有差异"的证据。但每条教训只有 3 任务×3种子=9次机会，9 次抛硬币本来就容易看出"假的差异"。现在 `analyze.py` 会额外跑一个"纯抛硬币模拟"（把每条教训的两个条件汇总成一个共同真实成功率，重新模拟 1000 次，看纯噪音能制造出多大的 P(delta<=0)），只有真实数值明显超过这个纯运气基准，才判 GO；否则即使原始数值达标也只判 WEAK-GO，并在报告里写明原因。
2. **实验 B 的决策点全挤在每个任务的开局**：以前"每个 episode 采够 5 个决策点就直接掐断"，而 ALFWorld 几乎每一步都满足"有多个动作可选"，所以 150 个点全是"走去哪个房间"这种开局步骤，成败在中后段才真正见分晓。现在改成整个 episode 跑到底，再从全程决策点里均匀抽样 5 个，同时顺带能统计出 base planner 真实做成过多少个任务。
3. **区分不了"没有关系"和"没测出来"**：以前只要 mismatch rate 和 oracle gain 都接近 0，就直接判"NO-GO / 不支持"。但如果模型本来就几乎全军覆没（两条分支都是 0 分），这两个数字也会自然趋近于 0——这不是"假设被推翻"，而是"这次没测出东西"。现在 `analyze.py` 会先检查"评估集里到底有没有任何一条分支成功过""变道的决策点是不是太少"，如果信号不够，会直接给一个新的 `INCONCLUSIVE` 结论并说明原因，而不是冒充 NO-GO。
4. **模型"答非所问"时会被静默兜底**：`ground_action()` 本来就有一个兜底机制——模型输出的动作如果匹配不上任何合法动作，就自动挑一个最接近的或者列表第一个。这个兜底是必要的（不然一次输出格式错误就整个 episode 崩掉），但之前完全没有人统计这个兜底触发了多少次。现在每条 episode 记录都会带上 `forced_action_count`，`scripts/check_forced_action_rate.py` 会在体检脚本里汇总检查，超过 20% 就直接报错退出，不让你在一个其实一直瞎走的 agent 上跑几十小时。
5. **"防重复记录"测试其实是空跑的**：规范要求测试"结果文件里没有重复 ID"，但 `A_pairwise_episodes.jsonl` 和 `A_topk_vs_all_raw.jsonl` 之前根本没写 `run_id` 字段，测试查了一个不存在的字段，永远查不出问题。现在这两个文件都补上了 `run_id`。

这几条里，第 1、3 条直接决定"最终结论有没有意义"，第 2 条决定"实验 B 到底有没有测到该测的东西"，第 4、5 条是几分钟就能修好的正确性 bug。全部已经修完，跑完全流程之后 `results/A_summary.json` 里会多一个 `a6_luck_baseline` 字段，`results/B_summary.json` 的 `verdict` 也可能出现 `INCONCLUSIVE`（不是 GO/WEAK-GO/NO-GO 里的任何一个），报告生成脚本 (`generate_report.py`) 遇到 `INCONCLUSIVE` 会在"Recommendation"部分明确写"这个方向这次没测出来，别当结论用"，而不是硬凑一个 GO/NO-GO。

---

如果你想让我在真机上跑之前先review一遍某个具体脚本的逻辑，或者想让我针对某一部分（比如实验 A 的相关任务挑选逻辑）再详细讲一遍，随时说。

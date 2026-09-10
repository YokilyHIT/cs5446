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

## 8. 真机验证与后续修复（HANDOFF 集成）

这一节记录了在**真实昇腾 910B3 机器**上跑通全流程之后反馈回来的一批修改（通过
`HANDOFF.tar.gz` 交接包），以及我在此基础上又做的几处修复。这是目前为止唯一一批
真正在硬件上跑过、而不是只做过语法检查的代码。

### 8.1 交接包里带来的 16 处修改（真机跑出来的问题）

按严重程度排序，最关键的几个：

- **BUG-1（必须带）**：`collect_decision_points.py` 存的 `observation` 是剥掉了
  "Your task is to: ..." 这句话之后的文本，但 `restore_state()` 重放校验时拿的是
  环境原始输出——**唯独 step 0 必然对不上**，实测 10 个决策点里 2 个在 step 0，
  直接把重放失败率顶到 20%，超过规范 §39 的 10% 硬上限，实验 B 一步都跑不了。
  修法：新增 `restore_observation` 字段单独给重放校验用。
- **ENV-2（必须带）**：`alfworld_base_config.yaml` 里 `training_method` 原来是
  `"dagger"`，会导致 `AlfredTWEnv.init_env()` 报 KeyError，还会在 train split
  上每次 reset 都跑一遍用不到的 PDDL 专家规划器。改成 `"dqn"`。
- **VALID-1（强烈建议带）**：实测强制动作率（模型输出匹配不上任何合法动作、被
  兜底逻辑乱选）高达 **51.3%**——不是格式问题，是模型说的动作语义合理但当前状态下
  不合法，兜底逻辑又把它模糊匹配成了另一个物体的动作，导致死循环到步数耗尽。
  改法：给 vLLM 加 `guided_choice` 约束解码，强制输出只能是合法动作之一。修完后
  强制率降到 **0%**。
- **VALID-2（必须带）**：原来 30 个 episode 是排序后取前 30 个游戏文件，而 ALFWorld
  路径以任务类型开头，导致六类任务只覆盖到两类。改成等距抽样。
- **VALID-3（默认开启）**：规范 §39 规定成功率太低时按顺序排查三件事，前两条
  （提示词是否强制合法动作、步数上限是否太低）已用数据排除，第三条（换用 AdaMEM
  官方提示词）生效——见下面 8.3。
- **PERF-1（强烈建议带）**：并发跑 episode 时 TextWorld 内部两处全局可变状态会
  报出跟并发毫无关系的诡异错误（`KeyError`/`IndexError`）。加一把锁把所有
  TextWorld 调用串行化，环境本身很快（<0.1s/步），真正慢的是等模型（0.5-13s/步），
  串行化几乎不损失并发收益：16 路并发下吞吐从 37 tok/s 提到 513 tok/s，30 个 episode
  从预估 3 小时降到 16 分钟。
- 其余是体检脚本可用性方面的改进（迷你冒烟测试真的迷你、强制动作率闸门提前、
  体检也覆盖分析链路）和一处报告展示 bug（GPU 那一行印成了 ASCII 表格边框）。

完整清单和每一条的诊断过程，见交接包原文（如果你手头还有 `HANDOFF.tar.gz`）。

### 8.2 我在交接包基础上又修的 6 个问题

交接包本身诚实地列出了"已诊断清楚但没来得及修"的 7 个问题，我在这基础上又处理了
其中 6 个（第 7 个纯粹是"模型这次表现出的置信度/歧义度数值本来就很集中"，是数据
现象不是代码 bug，没法靠改代码解决）：

1. **并发会污染实验 B 的核心指标**：如果 foresight 没有改变动作（`action_changed
   =False`），原来仍然会重新 restore 一遍环境、重新执行"同一个"动作再续跑——如果
   两次执行因为并发批次差异得到不同结果，就会凭空制造一个假的"预测有害/有用"信号，
   而这正是 mismatch rate（实验 B 最核心的指标）在测的东西。改法：动作没变就直接
   让 Branch W 的结果等于 Branch 0，不重新跑，既堵住假信号也省了近一半算力。
2. **`action_changed` 混入了"有没有推理"**：如果 base action 走的是 AdaMEM 两段式
   提示词（先 `<think>` 推理再选动作），而 B4 的 foresight 提示词是规范固定的单次
   调用，那"动作变没变"就同时混进了"看没看到预测"和"有没有经过推理"两个变量。
   改法：给 B4 也套上同一个推理脚手架（规范固定文本一字不改，外面包一层 think
   阶段），保证两次调用唯一的差别回到"有没有看到世界模型的预测"。
3. **`prompt_style` 没有真正贯通全部调用点**：`collect_decision_points.py` 和
   `generate_foresight.py` 里直接调用 `choose_action` 的地方漏了传 `prompt_style`，
   会静默退回 `"spec"`，而分支续跑走的 `rollout()` 会正确读配置——同一次实验里
   悄悄混用了两种策略。已在两处都补上。
4. **纯噪声守卫接得不够彻底，而且用错了统计量**：原来的 `simulate_luck_baseline`
   只挡在"GO"这一个分支上，其它分支（比如 P(delta<=0)>0 时判 WEAK-GO）完全没检查
   是不是纯噪声——用合成数据验证（真实教训效果设为完全为零）确认了这一点：代码
   仍然会输出 WEAK-GO。而且原来拿去跟纯运气基准比较的统计量是 P(delta<=0)，我用
   一个"一半教训真的有害、一半真的有用"的合成数据验证发现 P(delta<=0) 对这种
   真实存在的异质性几乎不敏感（纯运气也经常凑出差不多的 P(delta<=0)），而
   Var(delta) 的运气基准检验能干净地把这种情况和纯噪声区分开。改法：（a）纯运气
   检验现在挡在**所有**判定分支前面，过不了就只能是 NO-GO；（b）改用 Var(delta)
   而不是 P(delta<=0) 做运气检验的比较对象。这两处改动都用合成数据重新验证过。
5. **决策点越靠后，两条分支能分出胜负的空间越小**：分支续跑的步数上限原来是
   "全局 30 步减去决策点所在的步数"——如果决策点在第 29 步，两条分支各自只剩 1
   步，必然双双失败，Δ 恒为 0，这不是"预测没用"而是"根本没机会证明有没有用"。
   改法：两条分支都从决策点起改为一个固定的、全新的步数预算（等于
   `max_episode_steps`），不再从全局步数里扣减。
6. **`mcnemar_exact` 一直没被调用，`R_mismatch` 也没有置信区间**：规范 §35 明确
   要求对 paired success 额外报告 McNemar exact test。现在 `evaluate_planning_gain.py`
   会用 base_success/foresight_success 的不一致对数（即 planning_gain=-1/+1 的
   计数）算出 McNemar p 值，并给 R_mismatch 补上 bootstrap 95% 置信区间。

第 4 条是我在本地用合成数据（不需要真实 ALFWorld/NPU）反复验证过的：构造"真实
效应为零"的数据，确认新代码给出 NO-GO 而不是 WEAK-GO；再构造"一半有害一半有用"
的真实异质性数据，确认新代码能正确识别出真实信号并放行到正常的阈值判断逻辑。

### 8.3 一个配置默认值的改动

交接包自己测出来的结论是"该走规范 §39 的第③条补救"（换用 AdaMEM 官方提示词），
但它带过来的 `preexperiment.yaml` 里 `prompt_style` 默认值还留在 `"spec"`，跟它
自己的结论对不上。我按它测出来的真实数据把默认值改成了 `"adamem_think"`：

| | 规范提示词 30 步 | 规范提示词 50 步 | AdaMEM `<think>` 30 步 |
|---|---|---|---|
| 成功率 | 10.0% | 13.3% | **26.7%** |
| 打转 episode | 23% | 27% | **10%** |

数据存在 `diagnostics/baseline_*.jsonl`，测这份数据的脚本是新加的
`scripts/measure_baseline.py`（原来在交接包的 `tools/` 目录下，路径写死了机器
特定的绝对路径，我把它整理成了通用版本放进 `scripts/`）。如果换了模型或者数据集
版本，应该重新跑一遍这个脚本，再决定要不要改这个默认值。

### 8.4 其它新增文件

- `scripts/offline_download/`：断点续传的分块下载器（`dl_shards.py` 纯 Python
  版、`dl_blocks.sh` 多进程 curl 版），给"下载 HuggingFace/ModelScope 模型权重时
  单连接传几 MB 就被掐断"这种网络受限环境用的。都是**模板**，用之前要把里面写死的
  路径/文件名改成你自己的。
- `third_party/textworld-1.7.0-setup.sh`：aarch64 机器上 TextWorld 源码安装会
  因为 Inform7 6M62 没有 aarch64 二进制而失败的补丁（这些二进制只在"从零生成新
  游戏"时才用得到，ALFWorld 跑的是预生成好的 `.tw-pddl`，用不上，可以安全跳过）。
- `scripts/env.sh.example`：真机跑通时用的环境变量模板，展示了
  `logging_utils.py` 新增的 4 个路径类环境变量覆盖（`PREEXP_MODEL_NAME` /
  `PREEXP_API_BASE` / `PREEXP_EMBEDDING_MODEL` / `PREEXP_EMBEDDING_DEVICE`，只能
  覆盖路径和端点，种子/阈值/步数上限不可覆盖）怎么用。

---

## 9. 第二次交接包（`STAGE1_PATCH`）：两条独立血统对出了同一批 bug

这次收到的是一个 `git diff` 补丁包（`stage1.diff`），声明的前提是"仓库正好在
GitHub `YokilyHIT/cs5446` 的 commit `1147997`"。**这个 commit 不在我这边的 git
历史里**——`git apply --check` 直接报错：连它要改的 `CHANGES_AND_KNOWN_ISSUES.md`
（还有 `REPRODUCE.md`、`diagnostics/stage0_baseline.md`）在我这边根本不存在。
说明这是另一条独立演化的血统：大概率是同一个人（或同一个真机验证流程）把仓库
推到了 GitHub 上并继续往前做，文档结构和我这边分别重新组织过。

补丁没法直接打（`git apply`/`patch` 都会失败），所以我把 `stage1.diff` 整段
读完，跟我这边当前代码逐条对比后手动移植了实质性内容，而不是机械套用。

**结论先说**：补丁里 5 项修复中的 4 项（分支步数预算、`prompt_style` 贯通、
B4 套推理脚手架、未变道点不跑 Branch W），我这边在上一轮"真机验证反馈"里已经
独立实现了功能等价的版本——两条血统在同一份真实硬件上各自跑出了同样的 bug，
这是个好消息，说明这些 bug 是真的，不是巧合。第 5 项（实验 A 的纯噪声守卫）
两边思路不同，我采纳了对方更站得住脚的做法，具体见下面。

### 9.1 一处真正的分歧：纯噪声守卫该拿哪个统计量当门槛

我上一轮把纯噪声守卫的判定统计量从 `P(Δ≤0)` 换成了 `Var(Δ)`，理由是我自己构造的
合成数据里 `P(Δ≤0)` 检测不出真实存在的异质效应。这次的补丁坚持用 `P(Δ≤0)`
（跟规范 §16 本来就用的主指标一致），补丁自己的合成数据显示 `Var(Δ)` 在这个
样本规模下功效不稳定——真有效果时可能检不出、纯噪声时反而"显著"。

重新想过之后我采纳了补丁的做法：**判决门槛统一改回 `P(Δ≤0)` 本身的运气基线**
（跟规范 §16 用的判决指标保持一致，逻辑上更自洽——用统计量 A 做判决，就该用
统计量 A 自己的机会分布去检验它，而不是换一个可能不同调的统计量 B），
`Var(Δ)` 只作为披露信息写进报告，不参与判决。用两组合成数据重新验证过：
纯噪声数据和"一半真有害一半真有用"的异质数据，现在都正确给出 `INCONCLUSIVE`
（而不是像换成 `Var(Δ)` 之后那样把后一种情况误判成 `GO`——因为 `P(Δ≤0)=0.55`
这个具体数值本身其实并不比纯运气更极端，`Var(Δ)` 检测到的是另一种结构，
但规范 §16 的判决问的不是那个问题）。

顺带采纳了补丁里两处更好的措辞：

- **"跟运气分不开"判成 `INCONCLUSIVE` 而不是 `NO-GO`**：这两者不是一回事——
  前者是"没有证据"，后者是"有证据说明不存在"，这次数据只能撑起前者。
- **`luck_note` 的自相矛盾文案**：以前不管运气检验过没过，都无条件拼一句
  "(< 0.1 = distinguishable from pure chance)"，导致 p=1.00 的情况下打印出
  "p=1.00 (< 0.1 = 可以和纯运气区分)"——自己打自己脸。现在措辞跟着 p 值走。

另外补丁还加了一道我没有的守卫：**地板效应**——如果配对评估的平均成功率
低于 5%，说明 delta 恒为 0 是因为 agent 压根做不动任务，不是因为教训价值相同，
现在会在任何 GO/WEAK-GO/NO-GO 判读之前先判 `INCONCLUSIVE`。已经采纳。

### 9.2 一个配置默认值又改了回去

`sampling.prompt_style` 上一轮被我改成默认 `"adamem_think"`（理由是真机测出来
它成功率明显更高，26.7% vs 10%）。这次补丁坚持默认值**留在 `"spec"`**，
理由是换提示词会改变结论的适用范围——测出来的 delta 是"对一个会推理的 agent
的价值"，不再是"对规范 §5.1 那个裸 agent 的价值"，这个范围变化必须是每次跑的
时候明确写进报告的决定，不该是配置文件里一个不声不响的默认值。这个理由我觉得
站得住脚，已经改回默认 `"spec"`，`adamem_think` 仍然完整可用，跑之前显式设置
或者传参数即可。

### 9.3 其它移植

- `experiment_b.branch_rollout_budget`（默认 30）单独成一个配置项，不再直接
  复用 `sampling.max_episode_steps`——以后想单独调分支预算不用动全局步数上限。
- 实验 B 的"置信度/ambiguity 退化"这条以前是"低优先级、没法靠代码修"的
  已知问题（模型这次表现出的置信度确实全挤在 0.95–0.99，ambiguity 确实全是
  0，这是数据现象不是 bug），现在采纳了补丁的建议，把 eval 子集上 tau_c 的
  **实际 gate 使用率**、**置信度分布**（min/p25/median/p75/max）、
  **ambiguity 三个分桶各自的点数**都写进了 `B_summary.json`，方便一眼看出
  `R_mismatch` 这个数字在退化数据上有多大水分。
- `mcnemar_exact` 死代码 + `R_mismatch` 无置信区间——这两条补丁也列成了"未修"，
  但其实我在上一轮已经修过了（`evaluate_planning_gain.py` 现在会算
  McNemar p 值和 `R_mismatch` 的 bootstrap 置信区间），不需要重复处理。

---

## 10. 第三次交接（`part01-11`）：完整实验真的跑完了

这次收到的是 11 个小包（`part01`~`part11`，每包 ≤57KB），本质是**同一条 GitHub 血统**
（`YokilyHIT/cs5446`）的最新快照，相对我这边的 `4f3fe6f`（"Fix 5 methodology/correctness
issues found in review"）commit 生成的完整 `git diff` 补丁，**这次不再是增量**，
而是从那个 commit 到 2026-09-07 的全部累积改动（32 个文件，+2714/−303 行）。

### 10.1 怎么处理的

`4f3fe6f` 正好是我本地历史里真实存在的一个 commit，所以这次没有像上次那样只能"读懂再手动
搬"——我把这个 commit 单独检出到一个临时目录，把 part01/part02 的 `.patch` 用 `git apply`
干净地打了上去（验证通过：跟真机上的目录逐字节一致），再拿这个"打过补丁的干净基线"和我
现在的代码逐文件 diff，精确定位哪些文件对方是纯粹的超集（可以直接整份覆盖）、哪些文件我
这边有对方没有的独有内容（需要在覆盖后重新叠上去）。

**结果**：`preexperiments/common/`、`world_model_utility/`（除 `analyze.py` 和
`evaluate_planning_gain.py`）、`failure_selection/`（除 `analyze.py`，内容其实跟我这边
完全一致）、`scripts/`、新增的 `tools/` 目录、`.gitignore`、两份配置文件——这些直接整份
换成对方的版本。`world_model_utility/analyze.py` 和 `evaluate_planning_gain.py` 我这边
多出 McNemar 检验、`R_mismatch` 置信区间、置信度/ambiguity 退化披露（`gate_usage_rate_eval`
等字段）——对方目前还没修这两条（他们自己的"已知未修"清单也这么写），所以是换成对方版本后
把这几块重新叠上去。`third_party/`、`scripts/offline_download/`、`scripts/env.sh.example`
这几个我这边独有、对方没碰的补充文件原样保留。

### 10.2 真正新增的能力（不只是把之前几轮的修复合并到一起）

- **`preexperiments/common/parallel.py`（新文件）+ 全线路并发改造**：一个保序、失败不丢弃
  的线程池封装（`ordered_map`），现在 `collect_failures.py`、`evaluate_single_lessons.py`、
  `evaluate_topk_vs_all.py`、`generate_foresight.py`、`build_counterfactual_pairs.py` 都
  支持 `--workers N` 并发跑多个 episode。之前测出的 14 倍吞吐提升（16 路并发 513 tok/s
  vs 单路 37 tok/s）现在真正用在了正式实验上，不再只是 `measure_baseline.py` 自己的能力。
- **`format_admissible`/`format_history` 对齐 AdaMEM 原版渲染方式**：动作列表改成 AdaMEM
  的 `'action'` 逐行加引号格式，历史长度默认从 8 轮提到 50 轮（AdaMEM 自己用 50，8 轮的话
  跑到 30 步之后 agent 根本看不到自己试过什么），并且过滤掉 `help`（AdaMEM 也过滤，
  真机测出过一个 episode 把整个步数预算耗在反复 `help` 上）。
- **一个改变实验 B 解读方式的发现**：`tools/probe_confidence_elicitation.py` 测出，规范
  §22 那种"写完预测紧接着写置信度"的行内自报置信度，148 个决策点里 102 个恰好是 0.95，
  跟真实预测准确性的相关只有 **+0.034 (p=0.68)**——基本不相关。WorldEvolver 路线"置信度
  ≈ 预测正确概率"这个前提在这份数据上不成立。作为回应，`generate_foresight.py` 现在额外
  记录两个预注册的替代信号：`confidence_separate`（预测写完之后**另开一次独立调用**去评估，
  分布散开到 0.30–0.90）和 `logprob_prob`（用 token logprob 算出的置信度代理），跟规范
  合规的 `self_confidence` 一起写进 CSV，供以后对照。另外还发现真正预测 Δ_t 的其实不是
  预测质量，而是"被打断的动作本身值不值钱"（打断空动作如 `look`/`examine` 净赚 +2，打断
  有实际效果的动作净亏 -1）——`base_action_is_noop` 字段把这个也记了下来。
- **`temperature: 0.7`**（偏离规范 §2 的 0.2，写在配置注释里的显式决定）：按 AdaMEM 自己
  runner 的默认值复现。副作用是 0.2 配上约束解码会让 B11 的 4 次重采样几乎必然给出同一个
  动作，ambiguity 特征因此恒为 0——0.7 才可能有方差。0.2 那一轮的完整结果原样保留在本仓库
  `results_temp02_spec/`，没有被覆盖丢弃。

### 10.3 实验真的跑完了，结论是什么

跟前两次交接不同，这次实验 A 全量跑完、实验 B（temp 0.2 + spec 提示词）也全量跑完并归档在
`results_temp02_spec/`（temp 0.7 + adamem_think 那一轮快照时还在跑）。我把这两份真实结果
拷进了本仓库的 `results_reference_npu/`、`results_temp02_spec/`、`reports_reference_npu/`
（起了跟 `results/`/`reports/` 不同的名字，避免以后自己重新跑一遍时和这份参考数据搞混），
并且**用我这边重新整理过的 `generate_report.py` 跑了一遍**，端到端验证了整条分析链路在真实
数据上真的能跑通、字段都对得上。结果：

- **实验 A：`WEAK-GO`**——P(Δ≤0)=0.85，运气基线 p=0.015（能排除纯噪声，说明教训之间确实
  存在真实的价值差异），但 rho_U=-0.20（当前的新颖度+可迁移性代理信号完全没找对方向，
  跟真实价值负相关）、SR_TopK-SR_All=-0.03（挑出来的"高价值"教训实际效果反而不如全量）。
  翻译成大白话：**"有些教训确实比别的更差"这件事是真的，但我们现在这套"怎么挑出好教训"
  的方法目前还挑不对。**
- **实验 B：`WEAK-GO`**——3 条判据里只过了 1 条（mismatch_rate=0.086，oracle_gain=0.031，
  rho_self=-0.108）。翻译成大白话：**置信度和"参考预测是否真的有帮助"之间确实存在偏差，
  但偏差幅度和 oracle 上限空间目前都不算大，值得继续跟但不算强信号。**
- **两个方向都没有干脆利落地清出 GO**，`generate_report.py` 的最终建议是"neither"——
  但也都没有被 NO-GO 排除掉，是"值得用更大样本量再验证一次，而不是现在就下定论"的状态。

详细数字见 `reports_reference_npu/preliminary_results_A_and_tempB0.2spec.md`。

---

## 11. 第四次交接（新的 `part1-7`）：新增"方向二"，旧实验 B 结论也更新了

这次的 7 个包还是同一条 GitHub 血统、还是相对 `4f3fe6f` 生成的完整累积补丁（这次 48 个文件，
+5465/−303 行），处理方式跟上一轮完全一样（检出干净基线、打补丁、逐文件 diff）。这次
diff 出来的范围比上次小很多——`common/`、`failure_selection/`、`world_model_utility/`
除 `analyze.py`/`evaluate_planning_gain.py` 之外全部跟我这边一致（说明上一轮的"整份覆盖 +
叠加我方独有内容"策略是对的，双方没再各自往不同方向漂）。这两个文件里我独有的 McNemar
检验/置信区间/置信度退化披露照上次的方式重新叠了上去，叠完跟已提交的版本逐字节相同。

### 11.1 真正新增的内容

- **`preexperiments/direction_b/`（12 个新文件）**：一条全新的实验线，比"旧实验 B"更贴近
  WorldEvolver 论文原本的方法——真的实现了 Episodic Memory（用动作词元的 Jaccard 相似度做
  检索，不用模型）、Weak/Strong 两档世界模型、动作级和 episode 级两种粒度的分析、门控对比、
  多 seed 复测、提示词 framing 消融。配置独立成 `preexperiment.yaml` 里的 `direction_b:` 段
  （temperature=0、top_p=0.5、seed=42，照 WorldEvolver 原文设的，不影响实验 A/旧实验 B 的配置）。
  `alfworld_base_config.yaml` 也加了 `dagger:` 段——方向二的动作级实验需要从 ALFWorld 的
  expert 轨迹里采样决策点，这个功能只在 `training_method: dagger` 时才会挂载。
- **旧实验 B 之前"跑到一半"的那一轮（temp 0.7 + adamem_think）现在跑完了，结论从
  WEAK-GO 变成了 `GO`**：oracle_gain=0.060（CI [0.02, 0.11]），3 条判据过了 2 条。
  已经把这份新结果合并进 `results_reference_npu/`（覆盖了里面的 B_* 文件，A_* 部分数据
  跟之前完全一致，没有变化）。

### 11.2 方向二本轮最重要的发现：两个粒度的指标结论正好相反

- **动作级**（在 train 划分上，逐步问"选的动作是不是跟 expert 一样"）：foresight 净有害
  （−0.6pp）。
- **episode 级**（在 eval_in_distribution 上，只看任务最后有没有做完）：foresight 净有益
  （**+4.29pp**，比 WorldEvolver 论文自己报的 +2.24pp 还高）。

`EXPERIMENT_STATUS.md` 的判断（我认同）：**这不是 bug，是两个指标本来就没在测同一件事**——
动作级把"偏离 expert 走的路"一律算成犯错，但 ALFWorld 里经常有不止一条可行路径，
偏离 expert 不等于任务失败；episode 级只认"最后有没有做完"这一件事。**在 episode 级复现
出来之前，动作级的结论不能直接当结论用**——比如"foresight 有害"这种话，只能加上"在单步
expert-match 这个指标下"这个限定语，不能不加限定地引用。

置信度这边的发现也很关键：置信度门控在动作级测出来**省钱有效、提分无效**——选择性 foresight
只花了 16.3% 的调用量就打平了"每次都用 foresight"的效果，但没有比"每次都用"更好；而且
自报置信度对"baseline 这一步本来对不对"几乎没有信息量（两组之间只差 0.0016），换成
"检测 baseline 是不是错了"这种门控直接打到 Oracle 上界，而且这是可学的信号——这才是方向二
真正想验证的方法主张，但目前还没有专门训练这样一个门控，只是发现了这个可能性。

### 11.3 已知问题清单里最该注意的两条

- **Cosine 那一列指标跨论文不可比**：我们用的 all-MiniLM-L6-v2 和 WorldEvolver 用的
  Qwen3-Embedding-8B 数值尺度完全不同（MiniLM 上两句毫不相关的 ALFWorld 观察中位数
  cosine 就有 0.399），"三项指标全面超过完整系统"这个说法里 Cosine 那一项站不住，
  Exact Match 和 Token F1 两项可比、也确实更好。
- **episode 级目前只跑了一个 seed（42）**，13 vs 19 只差 6 个 episode，作者自己也说
  "不足以下结论"，`EXPERIMENT_STATUS.md` 第 7 节把"多 seed 复测"列成了下一步的第一优先级。

详细的三条线现状、配置差异、代码索引、复现命令，都在新增的 `EXPERIMENT_STATUS.md` 里，
比这里写的详细得多。方向二的原始逐条数据（`data/*.jsonl`，7.1MB）和图（`figures/dirB_*.png`）
这次没有打包，只有汇总表 `outputs/tables/dirB_*.json` 和 `reports_reference_npu/direction_b_strong_wm.md`
——想要图的话在有真实结果数据之后跑一遍 `analyze_confidence_utility.py` 就能生成。

---

如果你想让我在真机上跑之前先review一遍某个具体脚本的逻辑，或者想让我针对某一部分（比如实验 A 的相关任务挑选逻辑）再详细讲一遍，随时说。

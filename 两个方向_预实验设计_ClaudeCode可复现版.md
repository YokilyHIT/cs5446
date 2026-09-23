# 两个方向预实验：Claude Code 可执行复现规范

> **用途**：把本文件直接交给 Claude Code。目标不是让它“理解研究想法后自由发挥”，而是让它按照下面的固定协议搭环境、写脚本、跑预实验、产出 CSV / JSONL / 图和 summary。
>
> **总原则**：先复现实验基础设施，再跑最小 Go / No-Go 实验。不要先完整复现 AdaMEM、MNL、COMAP 或 WorldEvolver。

---

# 0. Claude Code 的任务

请在一个全新的工作目录中完成以下工作：

1. 安装并验证 ALFWorld TextWorld 环境。
2. 使用 `Qwen/Qwen3-4B-Instruct-2507`，通过本地 vLLM OpenAI-compatible server 调用模型。
3. 建立统一的 ReAct-style ALFWorld agent runner。
4. 所有 episode 都记录完整 trajectory、task metadata、seed、model config 和 token usage。
5. 完成两个彼此独立的预实验：
   - **实验 A：Selective Failure Learning**
   - **实验 B：Prediction Confidence vs Planning Utility**
6. 自动生成：
   - `results/*.jsonl`
   - `results/*.csv`
   - `figures/*.png`
   - `reports/preliminary_results.md`
7. 不允许通过手工挑样本、手工修改结果或根据 test set 调 threshold 来获得正结果。

---

# 1. 固定实验环境

## 1.1 Python

优先使用：

```bash
conda create -n alfworld-preexp python=3.10 -y
conda activate alfworld-preexp
python --version
```

Python 3.9+ 是 ALFWorld 当前官方 Quickstart 支持范围。

---

## 1.2 克隆实验底座

优先使用 **AdaMEM repository 作为 Agent 代码底座**，因为它已经公开：

- ALFWorld runner；
- no-memory baseline；
- ReasoningBank / Synapse / AdaMEM memory infrastructure；
- Qwen3-4B-Instruct-2507；
- vLLM 调用方式；
- `train / eval_in_distribution / eval_out_of_distribution` split。

执行：

```bash
git clone https://github.com/yunx-z/AdaMEM.git
cd AdaMEM

git rev-parse HEAD | tee ../ADAMEM_COMMIT.txt

pip install -e .
pip install -r requirements.txt
```

**不要假设 repo 永远和本文件描述完全一致。**

Claude Code 在修改任何文件前，必须先检查：

```bash
find . -maxdepth 3 -type f | sort | head -200
```

并确认：

```text
examples/prompt_agent/gpt4o_alfworld.py
build_index.py
requirements.txt
```

是否存在。

如果路径发生变化，只允许做“等价路径适配”，不要改变实验定义。

---

## 1.3 ALFWorld

如果 AdaMEM 自带的依赖安装没有准备好 ALFWorld，则执行：

```bash
pip install "alfworld[full]"
alfworld-download
```

然后验证：

```bash
alfworld-play-tw
```

如果交互命令不适合服务器环境，则写一个最小 Python smoke test：

```python
import alfworld
print("ALFWorld import OK")
```

以及至少完成：

```text
reset -> read observation -> read admissible actions -> step -> receive next observation
```

---

## 1.4 模型服务

启动：

```bash
CUDA_VISIBLE_DEVICES=0 \
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-4B-Instruct-2507 \
  --host 0.0.0.0 \
  --port 8001 \
  --dtype bfloat16 \
  --max-model-len 32768
```

健康检查：

```bash
curl http://127.0.0.1:8001/v1/models
```

保存：

```bash
python -m pip freeze > ../requirements_lock.txt
nvidia-smi > ../gpu_info.txt
```

---

# 2. 固定随机性与模型参数

所有实验先使用：

```yaml
model: Qwen/Qwen3-4B-Instruct-2507
temperature: 0.2
top_p: 0.95
max_tokens_per_action: 256
max_episode_steps: 30
seeds: [13, 37, 73]
```

如果 AdaMEM runner 的默认参数不同，可以增加 CLI/config override，但**不要偷偷沿用不确定的默认值**。

每个结果文件必须记录：

```json
{
  "model": "Qwen/Qwen3-4B-Instruct-2507",
  "temperature": 0.2,
  "top_p": 0.95,
  "seed": 13,
  "max_episode_steps": 30
}
```

---

# 3. Split 固定

为了让经验构建和 evaluation 分离：

## Experience / failure collection

使用：

```text
SPLIT=train
```

## Preliminary evaluation

使用：

```text
SPLIT=eval_in_distribution
```

第一阶段不跑 `eval_out_of_distribution`。

原因：

1. AdaMEM 官方 runner 已使用这些 split 名；
2. memory / experience 从 train 构建；
3. evaluation 使用独立 split，避免同任务泄漏。

---

# 4. 建议目录结构

在 AdaMEM 根目录增加：

```text
preexperiments/
├── common/
│   ├── llm_client.py
│   ├── alfworld_runner.py
│   ├── logging_utils.py
│   ├── replay_state.py
│   └── prompts.py
│
├── failure_selection/
│   ├── collect_failures.py
│   ├── extract_lessons.py
│   ├── select_related_tasks.py
│   ├── evaluate_single_lessons.py
│   ├── score_failure_proxies.py
│   ├── evaluate_topk_vs_all.py
│   └── analyze.py
│
├── world_model_utility/
│   ├── collect_decision_points.py
│   ├── generate_foresight.py
│   ├── build_counterfactual_pairs.py
│   ├── evaluate_planning_gain.py
│   ├── evaluate_oracle_gate.py
│   └── analyze.py
│
└── configs/
    └── preexperiment.yaml

results/
figures/
reports/
```

---

# 5. 共用 Agent Runner

## 5.1 Agent 必须输出合法 ALFWorld Action

优先使用 ALFWorld 提供的 admissible actions。

Prompt 至少包含：

```text
Goal:
{goal}

Current observation:
{observation}

Recent interaction history:
{history}

Available actions:
{admissible_actions}

Choose exactly one action from Available actions.
Return only the action string.
```

这样预实验主要研究 planning，而不是 action formatting。

---

## 5.2 每一步日志

统一记录：

```json
{
  "run_id": "...",
  "task_id": "...",
  "game_id_or_path": "...",
  "split": "train",
  "seed": 13,
  "step": 4,
  "goal": "...",
  "observation": "...",
  "admissible_actions": ["...", "..."],
  "action": "...",
  "next_observation": "...",
  "done": false,
  "success": false,
  "prompt_tokens": 0,
  "completion_tokens": 0
}
```

如果 ALFWorld/AdaMEM 暴露的字段名称不同，保存实际字段，同时保证：

```text
task_id
game identifier
goal
action prefix
observation
success
```

至少存在。

---

# 6. Smoke Test 验收标准

在正式预实验之前必须运行：

```text
5 个 train episodes
5 个 eval_in_distribution episodes
```

并确认：

- 没有环境 crash；
- action 均来自 admissible actions；
- trajectory JSONL 能重读；
- 至少有成功和失败样本，或者明确记录 success rate；
- 同一个 task + 同一 seed 可以确定性重放 action prefix。

如果最后一项失败，**先修复 replay，再做实验 B**。

---

---

# 实验 A：Selective Failure Learning

# 7. 研究问题

验证：

$$
\boxed{
\text{不同失败经验对未来任务的真实价值是否存在显著差异？}
}
$$

以及是否存在：

$$
\Delta_i \le 0,
$$

即：

> 某条 failure-derived lesson 对未来任务没有帮助，甚至造成负迁移。

---

# 8. A1：收集 Failure Pool

运行 No-Memory agent：

```bash
SPLIT=train \
MODEL_NAME=Qwen/Qwen3-4B-Instruct-2507 \
python -m examples.prompt_agent.gpt4o_alfworld
```

如果现有 runner 无法限制 episode 数，请给它增加：

```text
--max_episodes
--seed
--output_file
```

但不要改变其 Agent logic。

第一轮目标：

```text
最多运行 50 个 train episodes
```

停止条件：

```text
收集到至少 20 个失败
```

或：

```text
已运行 50 episodes
```

两者先到者停止。

输出：

```text
results/A_failures_raw.jsonl
```

每个 failure 至少保存：

```json
{
  "failure_id": "F0001",
  "task_id": "...",
  "task_type": "...",
  "goal": "...",
  "trajectory": [],
  "final_observation": "...",
  "seed": 13
}
```

---

# 9. A2：从 Failure 抽象单条 Lesson

固定 prompt：

```text
You are analyzing a failed household-planning trajectory.

Task:
{goal}

Trajectory:
{trajectory}

Identify the main planning mistake and derive ONE reusable rule.

Requirements:
- The rule must describe a planning principle.
- Do not mention object instance IDs.
- Do not mention exact room or receptacle indices.
- Do not merely restate the failure.
- Maximum 35 words.

Return exactly:
Mistake: <one sentence>
Reusable rule: <one sentence>
```

生成：

```text
results/A_failure_lessons.jsonl
```

格式：

```json
{
  "failure_id": "F0001",
  "mistake": "...",
  "lesson": "...",
  "task_type": "..."
}
```

Temperature 固定为 `0.2`。

每个 failure 只生成一次 lesson。

---

# 10. A3：Related Task Selection

## 10.1 预实验不要让人工手选任务

必须自动选择。

候选池：

```text
eval_in_distribution split
```

每个 failure 选择：

$$
K=3
$$

个测试任务。

优先按：

1. task type 相同；
2. goal embedding similarity；
3. task_id 不同。

如果同 task type 不足 3 个，再允许不同 task type。

必须排除：

```text
与 failure 来源相同 game/task
```

---

## 10.2 Embedding

使用一个固定的小 embedding 模型，例如：

```text
sentence-transformers/all-MiniLM-L6-v2
```

计算：

$$
s_{ij}
=
\operatorname{cos}
\left(
E(\text{lesson}_i),
E(\text{goal}_j)
\right).
$$

选择 top-3：

$$
\mathcal T_i
=
\operatorname{Top3}_{j}(s_{ij}).
$$

输出：

```text
results/A_failure_task_pairs.jsonl
```

---

# 11. A4：严格 Pairwise Evaluation

对每个：

$$
(f_i,T_{ij})
$$

执行两个条件。

## Condition 0：No Lesson

正常 ReAct agent。

## Condition 1：With Lesson

仅增加：

```text
Relevant lesson from previous experience:
{lesson}

Use it only if it is relevant to the current task.
```

其他：

```text
model
temperature
seed
max steps
admissible actions
```

全部相同。

对每一对使用相同 seed：

```text
13, 37, 73
```

因此每条 failure 共：

$$
3 \text{ tasks}
\times
2 \text{ conditions}
\times
3 \text{ seeds}
=
18
$$

个 episode。

第一版最多测试前：

```text
20 个 failures
```

总上限：

$$
20\times18=360
$$

episodes。

---

# 12. A5：真实 Failure Utility

定义：

$$
S_{ijk}^{(0)}
\in
\{0,1\},
$$

$$
S_{ijk}^{(m)}
\in
\{0,1\}.
$$

其中：

- \(i\)：failure；
- \(j\)：related task；
- \(k\)：seed。

定义：

$$
\Delta_i
=
\frac{1}{3\times 3}
\sum_{j=1}^{3}
\sum_{k=1}^{3}
\left(
S_{ijk}^{(m)}
-
S_{ijk}^{(0)}
\right).
$$

输出：

```text
results/A_failure_utility.csv
```

至少有：

```text
failure_id
task_type
lesson
mean_success_no_lesson
mean_success_with_lesson
delta
```

---

# 13. A6：预实验的第一个核心结果

统计：

$$
P_{-}
=
P(\Delta_i<0),
$$

$$
P_{0}
=
P(\Delta_i=0),
$$

$$
P_{+}
=
P(\Delta_i>0),
$$

以及：

$$
\operatorname{Var}(\Delta_i).
$$

画：

```text
figures/A_failure_utility_hist.png
```

横轴：

$$
\Delta_i.
$$

---

# 14. A7：Failure Selection Proxy

先只验证两个简单信号。

## Novelty

对 diagnosis/lesson embedding：

$$
N(f_i)
=
1-
\max_{j<i}
\operatorname{cos}
\left(
E(m_i),E(m_j)
\right).
$$

第一个 failure 的 novelty 定义为 `1.0`。

---

## Transferability

固定 prompt：

```text
Rate how reusable this planning lesson is across DIFFERENT household tasks.

0.0 = useful only for this exact task
1.0 = broadly reusable planning constraint

Lesson:
{lesson}

Return only one decimal number between 0.0 and 1.0.
```

得到：

$$
T(f_i)\in[0,1].
$$

---

## 简单 Utility Proxy

不要调权重。

预实验固定：

$$
U_i
=
\frac{N(f_i)+T(f_i)}{2}.
$$

计算：

$$
\rho_U
=
\operatorname{SpearmanCorr}
(U_i,\Delta_i).
$$

输出：

```text
results/A_proxy_correlation.csv
```

---

# 15. A8：Top-K vs All Memory

这是第二个最重要的验证。

按照：

$$
U_i
$$

排序。

取：

```text
K = ceil(0.4 * number_of_lessons)
```

构造：

- `NoMemory`
- `AllLessons`
- `RandomK`
- `TopK`

在同一个固定 evaluation subset 上比较。

Evaluation subset：

```text
eval_in_distribution 中固定 30 个任务
```

固定 task IDs 并保存：

```text
results/A_eval_task_ids.json
```

每个条件跑 seeds：

```text
13, 37, 73
```

检索规则统一：

对当前 goal 与 lesson embedding 做 cosine similarity，注入 Top-1 lesson。

注意：

> `AllLessons` 不是把所有 lesson 全塞进 prompt。

它表示检索池是 AllLessons；每一步/episode 实际注入的 lesson 数与 TopK 条件保持一致。

否则比较会混入 prompt length confound。

主要比较：

$$
SR_{\text{TopK}}
\quad\text{vs}\quad
SR_{\text{All}}.
$$

---

# 16. 实验 A Go / No-Go

## 强支持

满足：

$$
P(\Delta_i\le0)\ge0.20
$$

并且：

$$
\rho_U\ge0.30.
$$

或者：

$$
SR_{\text{TopK}}
-
SR_{\text{All}}
\ge
0.05.
$$

这里 `0.05` 表示 **5 percentage points**。

---

## 中等支持

存在明显：

$$
P(\Delta_i\le0)>0,
$$

但：

$$
\rho_U\approx0.
$$

结论：

> Failure Selection 有意义，但当前 proxy 不够好。

---

## 不支持

如果几乎所有：

$$
\Delta_i>0
$$

且：

$$
SR_{\text{TopK}}
\le
SR_{\text{All}},
$$

则暂停该方向。

---

---

# 实验 B：Prediction Confidence vs Planning Utility

# 17. 核心研究问题

验证：

$$
\boxed{
\text{Prediction Confidence}
\neq
\text{Planning Utility}
}
$$

注意：

**这个预实验的目标不是先证明我们的 gate 能赢。**

先证明：

> confidence-only selective foresight 存在可利用的错误选择空间。

---

# 18. 非常重要：Counterfactual State Reproduction

实验 B 必须从**同一个 ALFWorld state**比较：

$$
a_t^{(0)}
$$

和：

$$
a_t^{(W)}.
$$

不能：

- 在两个不同 episode 中随便比较；
- 在 state 已经变化后再执行第二个 action；
- 用不同 task initial state。

---

# 19. State Restore 的实现要求

优先方案：

## Deterministic Replay

对每个 decision point 保存：

```text
game/task identifier
seed
action_prefix = [a_0, ..., a_{t-1}]
observation_t
```

需要评估某个 branch 时：

1. 创建一个新的 ALFWorld env；
2. 加载**同一个 game/task**；
3. reset；
4. 依次 replay：
   ```text
   a_0, ..., a_{t-1}
   ```
5. assert 最终 observation 与保存的 `observation_t` 一致；
6. 从这里执行 branch action。

必须实现：

```python
restore_state(task_id, game_identifier, action_prefix, expected_observation)
```

并带 assert。

如果 ALFWorld 当前 API 不允许直接按 `task_id` reset：

1. 检查 AdaMEM/ALFWorld runner 如何存储 game file / trajectory path；
2. 使用对应 game identifier 重新构造环境；
3. 不允许通过“不断 reset 直到碰到同一个任务”的脆弱方法作为最终实现。

如果底层环境提供可靠 snapshot / copy API，可以使用，但必须写单元测试确认两个 clone state 完全一致。

---

# 20. B1：采集 Decision Points

从：

```text
eval_in_distribution
```

固定选：

```text
30 个 episodes
```

每个 episode 最多采：

```text
5 个 decision points
```

目标：

$$
N=150
$$

个 decision points。

优先保留：

- 至少 2 个 admissible actions；
- episode 尚未结束；
- 当前不是明显的纯格式/终止动作；
- history 长度未超过模型 context。

输出：

```text
results/B_decision_points.jsonl
```

每个 sample：

```json
{
  "point_id": "D00001",
  "task_id": "...",
  "game_id_or_path": "...",
  "seed": 13,
  "step": 6,
  "goal": "...",
  "action_prefix": ["...", "..."],
  "observation": "...",
  "admissible_actions": ["...", "..."]
}
```

---

# 21. B2：Base Action

Base planner：

$$
a_t^{(0)}
=
\pi(h_t).
$$

使用和普通 ReAct 完全一样的 prompt。

保存：

```text
base_action
```

---

# 22. B3：World Model Prediction

固定 prompt：

```text
You are a world model for an interactive household environment.

Current task:
{goal}

Current observation:
{observation}

Recent action-observation history:
{history}

Candidate action:
{base_action}

Predict the immediate NEXT observation after executing this action.

Also report your confidence that the important state changes and
preconditions in your prediction are correct.

Return exactly:
Prediction: <one concise predicted observation>
Confidence: <number from 0.0 to 1.0>
```

得到：

$$
\hat{o}_{t+1}
$$

和：

$$
C_t^{self}.
$$

---

# 23. B4：Foresight-Conditioned Action

在**仍然是原始 state \(h_t\)** 的情况下，让 Planner 重新选择 action：

```text
Goal:
{goal}

Current observation:
{observation}

Available actions:
{admissible_actions}

A world model predicts the following consequence if the originally
proposed action "{base_action}" is executed:

{predicted_next_observation}

Choose the best CURRENT action.
You may keep the original action or select another available action.

Return exactly one action from Available actions.
```

得到：

$$
a_t^{(W)}.
$$

定义：

$$
D_t
=
\mathbf{1}
[
a_t^{(W)}
\neq
a_t^{(0)}
].
$$

---

# 24. B5：得到真实 Prediction Correctness

从 restore 后的原 state 执行：

$$
a_t^{(0)}
$$

得到真实：

$$
o_{t+1}.
$$

预实验同时保留两个 correctness 指标。

## Self confidence

$$
C_t^{self}.
$$

## Semantic correctness

使用固定 embedding：

$$
C_t^{sem}
=
\operatorname{cos}
\left(
E(\hat{o}_{t+1}),
E(o_{t+1})
\right).
$$

不要在第一版声称 cosine similarity 等于真正 world-model accuracy。

它只是辅助 proxy。

---

# 25. B6：定义 Planning Utility

## 推荐第一版使用完整后续 Episode Rollout

相比人为设计 dense heuristic，这更干净。

对每个 decision point：

### Branch 0

restore state 后执行：

$$
a_t^{(0)}
$$

然后使用相同 Base ReAct planner 继续直到：

```text
success
or done
or max_episode_steps
```

得到：

$$
Y_t^{(0)}\in\{0,1\}.
$$

### Branch W

再次 restore 到**相同 state**。

先执行：

$$
a_t^{(W)}
$$

之后也使用同一个 Base ReAct planner 继续。

得到：

$$
Y_t^{(W)}\in\{0,1\}.
$$

定义：

$$
\Delta_t
=
Y_t^{(W)}
-
Y_t^{(0)}.
$$

因此：

$$
\Delta_t\in\{-1,0,1\}.
$$

解释：

- \(+1\)：foresight 改变 action 后救活任务；
- \(0\)：没有改变最终 success；
- \(-1\)：foresight 导致原本可成功的任务失败。

---

# 26. 为什么第一版不用 Short-Horizon Heuristic

上一版设计中的：

$$
V_H
=
\lambda_1\cdot\text{success}
-\lambda_2\cdot\text{invalid}
+\lambda_3\cdot\text{progress}
$$

会引入新的主观超参数。

预实验优先使用：

$$
\boxed{\text{最终 episode success}}
$$

定义 Utility。

如果完整 rollout 成本过高，再实现 `H=5` 的 short-horizon 版本作为 fallback，但必须在 report 中明确它是 proxy。

---

# 27. B7：只对 Decision-Changing States 做主要 Utility 分析

如果：

$$
a_t^{(W)}=a_t^{(0)},
$$

则：

$$
\Delta_t
$$

通常没有提供 gating 的判别信息。

因此同时报告：

## All decision points

和：

## Changed subset

$$
\mathcal D
=
\{
t:
D_t=1
\}.
$$

主要 mismatch 分析在：

$$
\mathcal D
$$

上进行。

---

# 28. B8：Confidence–Utility Mismatch

先在 calibration subset 上确定 confidence threshold。

将 150 个 decision points 固定分：

```text
前 50 个：calibration
后 100 个：evaluation
```

不要随机反复切分。

在 calibration 上选择：

$$
\tau_c
$$

使 confidence gate 的 foresight usage rate 接近：

```text
50%
```

然后锁死：

$$
\tau_c.
$$

在 evaluation 上统计：

### High-confidence harmful

$$
C_t\ge\tau_c,
\qquad
\Delta_t=-1.
$$

### Low-confidence helpful

$$
C_t<\tau_c,
\qquad
\Delta_t=+1.
$$

定义：

$$
R_{\text{mismatch}}
=
\frac{
N_{\text{high-conf,harmful}}
+
N_{\text{low-conf,helpful}}
}{
N_{\text{changed,evaluation}}
}.
$$

---

# 29. B9：相关性

在 changed evaluation subset 上计算：

$$
\rho_{\text{self}}
=
\operatorname{SpearmanCorr}
(
C_t^{self},
\Delta_t
),
$$

以及：

$$
\rho_{\text{sem}}
=
\operatorname{SpearmanCorr}
(
C_t^{sem},
\Delta_t
).
$$

由于：

$$
\Delta_t\in\{-1,0,1\},
$$

同时报告 bootstrap 95% confidence interval。

Bootstrap：

```text
1000 resamples
seed = 2026
```

---

# 30. B10：Oracle Gate 的正确实现

这里不要错误地“在真正在线 episode 中读取未来结果”。

Oracle 只作为**离线 upper bound**。

对于每个 evaluation decision point：

Confidence Gate 的理想 decision：

$$
g_t^{conf}
=
\mathbf{1}
[
C_t\ge\tau_c
].
$$

Oracle Gate：

$$
g_t^{oracle}
=
\mathbf{1}
[
\Delta_t>0
].
$$

定义 point-level oracle advantage：

$$
A_t^{oracle}
=
\max(
Y_t^{(0)},
Y_t^{(W)}
)
-
Y_t^{conf},
$$

其中：

$$
Y_t^{conf}
=
\begin{cases}
Y_t^{(W)}, & C_t\ge\tau_c,\\
Y_t^{(0)}, & C_t<\tau_c.
\end{cases}
$$

计算：

$$
G_{\text{oracle}}
=
\frac{1}{N}
\sum_t
A_t^{oracle}.
$$

这比把不同 decision-point branches 强行拼成一个“Oracle online episode”更严谨。

**预实验阶段使用 point-level oracle upper bound。**

正式项目如果要做真实 episode-level Utility Gate，再单独实现在线 policy。

---

# 31. B11：Action Ambiguity

对每个原始 state，用 Base Planner 独立采样：

$$
K=4
$$

个 action：

$$
a_t^{(1)},\ldots,a_t^{(4)}.
$$

使用相同 prompt，但分别改变 inference seed。

定义：

$$
A_t
=
1-
\frac{
\max_a
\sum_{k=1}^{4}
\mathbf{1}[a_t^{(k)}=a]
}{4}.
$$

分成：

```text
Low: A = 0
Medium: 0 < A <= 0.5
High: A > 0.5
```

比较三个 bucket 的：

$$
R_{\text{mismatch}}
$$

与：

$$
P(\Delta_t=1).
$$

---

# 32. 实验 B 输出

生成：

```text
results/B_world_model_utility.csv
```

字段至少包括：

```text
point_id
task_id
step
base_action
foresight_action
action_changed
wm_prediction
self_confidence
semantic_correctness
base_success
foresight_success
planning_gain
ambiguity
```

---

# 33. 实验 B Figures

必须生成：

```text
figures/B_confidence_vs_gain.png
figures/B_mismatch_matrix.png
figures/B_gain_by_ambiguity.png
```

## Figure 1

横轴：

$$
C_t^{self}.
$$

纵轴：

$$
\Delta_t.
$$

因为 \(\Delta_t\) 是离散的，绘图时对纵轴只做轻微 jitter 以便观察，不改变统计值。

## Figure 2

2×2 mismatch matrix。

## Figure 3

按 ambiguity bucket 画 helpful / harmful foresight rate。

---

# 34. 实验 B Go / No-Go

方向 B 判为“强支持”，满足以下至少两个：

$$
R_{\text{mismatch}}\ge0.15,
$$

$$
G_{\text{oracle}}\ge0.05,
$$

$$
\rho_{\text{self}}<0.70.
$$

其中 `0.05` 表示 5 percentage points 的 point-level oracle upper-bound gain。

如果：

$$
R_{\text{mismatch}}\approx0
$$

并且：

$$
G_{\text{oracle}}\approx0,
$$

则停止方向 B。

---

# 35. 统计要求

所有核心 success comparison 附：

```text
bootstrap 95% confidence interval
```

使用：

```text
1000 bootstrap resamples
seed = 2026
```

对于 paired success：

优先额外报告：

```text
McNemar exact test
```

但预实验阶段：

> effect size > p-value。

不要因为样本小而把“不显著”等同于“没有现象”。

---

# 36. 结果报告模板

Claude Code 最后自动生成：

```text
reports/preliminary_results.md
```

格式固定：

```markdown
# Preliminary Experiment Results

## Environment
- AdaMEM commit:
- ALFWorld version:
- Qwen model:
- GPU:
- seeds:

# Experiment A

## Data
- train episodes:
- failures:
- evaluated failures:
- evaluation episodes:

## Main numbers
- P(delta < 0):
- P(delta = 0):
- P(delta > 0):
- Var(delta):
- Spearman U vs delta:
- NoMemory SR:
- AllLessons SR:
- RandomK SR:
- TopK SR:

## Decision
GO / WEAK-GO / NO-GO

## Interpretation
...

# Experiment B

## Data
- decision points:
- changed-action points:
- calibration points:
- evaluation points:

## Main numbers
- mismatch rate:
- rho(self-confidence, planning gain):
- rho(semantic-correctness, planning gain):
- oracle upper-bound gain:
- helpful foresight rate:
- harmful foresight rate:

## Decision
GO / WEAK-GO / NO-GO

## Interpretation
...

# Recommendation
Candidate A / Candidate B / neither
```

---

# 37. 最终验收标准

Claude Code 完成后，以下文件必须存在：

```text
ADAMEM_COMMIT.txt
requirements_lock.txt
gpu_info.txt

results/A_failures_raw.jsonl
results/A_failure_lessons.jsonl
results/A_failure_task_pairs.jsonl
results/A_failure_utility.csv
results/A_proxy_correlation.csv
results/A_eval_task_ids.json

results/B_decision_points.jsonl
results/B_world_model_utility.csv

figures/A_failure_utility_hist.png
figures/A_topk_vs_all.png

figures/B_confidence_vs_gain.png
figures/B_mismatch_matrix.png
figures/B_gain_by_ambiguity.png

reports/preliminary_results.md
```

并且：

```bash
python -m pytest preexperiments/tests -q
```

至少包含以下测试：

1. vLLM client 能返回文本；
2. ALFWorld reset/step 正常；
3. 同 task + action prefix 能 restore 到相同 observation；
4. paired condition 使用相同 task/seed；
5. evaluation task 不出现在 train failure source 中；
6. result CSV 中没有重复 run ID；
7. analysis script 可从原始 JSONL 独立重建主要统计量。

---

# 38. Claude Code 开始执行时的顺序

必须按这个顺序：

```text
1. Inspect repository
2. Install dependencies
3. Run ALFWorld smoke test
4. Start / verify vLLM
5. Run 10-episode baseline smoke test
6. Implement deterministic replay + tests
7. Run Experiment B on 10 decision points as a mini-smoke-test
8. Run Experiment A on 3 failures as a mini-smoke-test
9. Only after both pass, run full preliminary experiments
10. Generate analysis + report
```

不要先实现完整 memory system。

不要先复现完整 WorldEvolver。

不要先跑 300+ episodes。

---

# 39. 失败时的处理原则

## 如果 Qwen3-4B success rate 太低

先检查：

- prompt 是否要求从 admissible actions 选择；
- max steps 是否太低；
- AdaMEM 官方 no-memory runner 的 prompt 是否可直接复用。

不要第一反应换闭源大模型。

---

## 如果 success rate 太高，几乎没有 failure

优先：

- 增加任务 horizon；
- 使用更难的 eval tasks；
- 减少过强的 oracle-like environment hints。

然后再考虑模型大小。

---

## 如果 deterministic replay 失败

**禁止继续实验 B。**

必须先保证：

$$
\text{same task}
+
\text{same action prefix}
\Rightarrow
\text{same state}.
$$

否则：

$$
\Delta_t
$$

没有因果可比性。

---

# 40. 本预实验明确不做的内容

### Experiment A 不做

- 完整 AgeMem RL training；
- 完整 AdaMEM STEP-MFT；
- 大规模 memory hyperparameter search；
- 所有 ALFWorld task family。

### Experiment B 不做

- 训练新的大型 world model；
- 完整 COMAP co-evolution；
- 完整 WorldEvolver reproduction；
- 在预实验阶段训练复杂 neural utility model。

这些都应该在 Go / No-Go 成立后再做。

---

# 41. 与最新工作的衔接

## Experiment A

AdaMEM 已公开 ALFWorld + Qwen3-4B-Instruct-2507 的运行方式，并提供 `no-memory`、`reasoningbank`、`synapse`、`adamem-*` 等 memory types。

正式项目如果 Experiment A GO：

```text
No Memory
→ All Failure
→ Random-K
→ MNL-port
→ ReasoningBank / AdaMEM
→ Ours
```

逐步增加 baseline。

预实验只验证：

$$
\boxed{
\text{failure selection 是否本身值得研究}
}
$$

---

## Experiment B

WorldEvolver 的 Selective Foresight 已经说明：

$$
\text{unreliable foresight can hurt planning}.
$$

我们预实验进一步验证：

$$
\boxed{
\text{prediction confidence 是否足以决定 foresight 的使用？}
}
$$

如果存在明显 confidence–utility mismatch，并且 point-level Oracle Utility Gate 相对 confidence gate 有明显上限空间，则正式项目继续做：

$$
\text{Planning-Utility-Gated Foresight}.
$$

---

# 42. 参考项目

- AdaMEM: `https://github.com/yunx-z/AdaMEM`
- ALFWorld: `https://github.com/alfworld/alfworld`
- MNL: `https://github.com/Bairong-Xdynamics/MistakeNotebookLearning`
- COMAP: `https://github.com/loyiv/CoMAP`
- WorldEvolver: `https://arxiv.org/abs/2606.30639`

---

# 43. 最后一条要求

Claude Code 在实际运行完成前，不得在 report 中写：

```text
“我们的假设已被证明”
```

只能根据结果写：

```text
supported by preliminary evidence
weakly supported
not supported under the current setup
```

因为这份实验的目标是方向筛选，不是最终论文结论。

# 变更清单：相对 `cs5446-master.zip` 原始解压版

基准 = 本仓库的上一个 commit（`4f3fe6f` "Fix 5 methodology/correctness issues found in review"）。
共 **16 个源文件**有改动，**没有新增仓库内文件**。全部改动的统一 diff 见 `CHANGES.diff`（822 行）。

每条改动都标了三个属性：

- **类型**：`BUG`（仓库缺陷，与机器无关）/ `ENV`（环境兼容）/ `VALID`（实验有效性）/ `PERF`（性能）/ `TEST`（体检可用性）
- **换机器还需要吗**
- **改了多少行**

---

## BUG-1　step 0 的决策点永远无法重放 → 实验 B 整体中止

**文件**：`world_model_utility/collect_decision_points.py`、`build_counterfactual_pairs.py`　**换机器：必须带**

`collect_decision_points` 存进决策点的 `observation`，是被 `extract_goal_and_observation()`
剥掉开头 "Your task is to: …" 之后的文本；而 `restore_state()` 做重放断言时，拿的是
`reset()` 返回的**原始**观察。第 1 步及以后的观察里没有那句话，两者相同；**唯独 step 0
必然不相等**。

实测：10 个决策点里 2 个落在 step 0，重放失败率 20% > 10% 硬上限，
`build_counterfactual_pairs` 按规范 §39 抛异常终止，实验 B 一步都跑不了。

**改法**：决策点新增字段 `restore_observation`（环境原始文本）专供重放断言，
`observation`（剥离版）继续用于提示词。修完重放失败 **0/10**。

---

## BUG-2　报告里 GPU 行印的是 ASCII 表格边框

**文件**：`scripts/generate_report.py`　**换机器：建议带**

`gpu_info.txt` 是 `npu-smi info`（GPU 机器上是 `nvidia-smi`）的输出，首行是 `+-----+`
边框，报告的 `- GPU:` 行就直接印了一行加号。改成取第一行有实际内容的文本。

顺带把模板里一直是占位符的 `ALFWorld version` 改成从已安装发行版真实读取（现显示 `0.4.2`）。

---

## ENV-1　`AlfredTWEnv` 导入路径变了

**文件**：`common/alfworld_runner.py`、`scripts/inspect_alfworld_api.py`　**换机器：视 alfworld 版本**

alfworld 0.4.x 移除了包根部的再导出，改成惰性工厂 `get_environment("AlfredTWEnv")`，
原来的 `from alfworld.agents.environment import AlfredTWEnv` 直接 ImportError。
新增 `_import_alfred_tw_env()`，按 工厂 → 子模块 → 旧路径 依次尝试，新旧布局都能用。

## ENV-2　ALFWorld 配置缺 `dagger` 段导致 KeyError

**文件**：`configs/alfworld_base_config.yaml`　**换机器：必须带**

`AlfredTWEnv.init_env()` 按 `config["general"]["training_method"]` 分支。取 `"dagger"` 时
会读 `config["dagger"]["training"]["max_nb_steps_per_episode"]`——本配置没有这一段，KeyError；
而且会在 train split 上额外挂 `AlfredExpert` wrapper，每次 reset 都跑一遍 PDDL 规划器算专家
计划，我们的 ReAct agent 根本不用。改成 `"dqn"`：读已有的 `rl` 段，不挂 expert wrapper，
agent 看到的环境完全不变。

## ENV-3　模型/词向量路径不该写死进共享配置

**文件**：`common/logging_utils.py`　**换机器：建议带**

`load_yaml_config` 增加 4 个环境变量覆盖：`PREEXP_MODEL_NAME`、`PREEXP_API_BASE`、
`PREEXP_EMBEDDING_MODEL`、`PREEXP_EMBEDDING_DEVICE`。
**只允许覆盖路径和端点**——seed、温度、episode 上限、判决阈值一律不可覆盖，
保证任何一次运行的实验协议都与签入的配置一致。

---

## VALID-1　51% 的动作是兜底乱选的

**文件**：`common/llm_client.py`、`common/alfworld_runner.py`、`world_model_utility/generate_foresight.py`
**换机器：强烈建议带**

体检脚本第一次跑，强制动作率闸门当场失败：**51.3%**。诊断后**不是**提示词格式问题：
模型输出的 `examine bowl 1` 格式正确、语义也合理，只是当前状态下不合法（合法的是
`take bowl 1 from desk 1`）。`ground_action()` 的 difflib 兜底把它模糊匹配成了**另一个物体**
的动作 `examine desk 1`；该动作不改变状态 → 下一步提示词完全相同 → 输出相同 →
**死循环到 30 步耗尽**。大部分"失败"测的是动作格式，不是规划能力，正是规范 §5.1 想避免的混淆。

**改法**：`LLMClient.complete()` 增加 `choices` 参数，走 vLLM 的 `guided_choice` 约束解码，
把输出限制在当前合法动作集合内。base action 和 foresight action 用同一机制，
否则 `action_changed` 会混入"哪一次调用碰巧输出了可解析动作"。

**效果：强制率 51.3% → 0.0%。**

## VALID-2　决策点全落在同一个任务类型上

**文件**：`world_model_utility/collect_decision_points.py`　**换机器：必须带**

原来取排序后的**前 N 个**游戏文件。ALFWorld 的路径以任务类型开头，所以 30 个 episode 会
几乎全是 `look_at_obj_in_light` / `pick_and_place_simple`，六类任务只覆盖两类。
改成与 `evaluate_topk_vs_all.py::_select_eval_subset` 相同的等距抽样（同样完全确定性）。
那个函数的注释里本就写明了这个理由，只是这里没照做。

## VALID-3　AdaMEM 提示词选项（规范 §39 第③条）

**文件**：`common/prompts.py`、`common/alfworld_runner.py`、`configs/preexperiment.yaml`
**换机器：带，但默认关闭**

规范 §39 规定成功率太低时按顺序检查三件事。前两条已用数据排除：

| | 规范提示词 30 步 | 规范提示词 50 步 | AdaMEM `<think>` 30 步 |
|---|---|---|---|
| 成功率 | 3/30 = 10.0% | 4/30 = 13.3% | **8/30 = 26.7%** |
| 打转 episode | 7/30 | 8/30 | **3/30** |
| 强制动作率 | 0.0% | 0.0% | 0.0% |

- ① 提示词是否要求从合法动作里选 → 已满足（强制率 0%）
- ② 步数上限太低 → 30→50 多花 62% 算力只多 1 个成功；成功的 episode 只用了 5/11/12 步，
  失败的是在十来个动作间兜圈而非系统探索。**排除**
- ③ 复用 AdaMEM 官方 no-memory 提示词 → 生效

新增 `sampling.prompt_style`，两个取值：
- `"spec"`（**默认，未改**）：规范 §5.1 固定提示词 + 约束解码
- `"adamem_think"`：AdaMEM 提示词（`<think>` 推理 → `<action>`），每步 2 次调用：
  第一次预填 `<think>` 拿推理，第二次带 `guided_choice` 只出动作（强制率仍为 0）

> ⚠️ **两个必须知道的坑**
> 1. 这个模型面对"请在 `<think></think>` 里推理"的提示词会**立刻输出 EOS**（空回复，1 个 token），
>    温度 0.2 和 0.7 都一样。**必须预填 `<think>`** 让它接着写。不是 vLLM/Ascend 的问题。
> 2. AdaMEM 的**两段式 strategy 路径没有采用**——它的 strategy 来自历史经验，属于记忆机制，
>    注入无教训基线会污染实验 A 要做的对照。这里用的是它的单次调用无记忆版。

## PERF-1　全程串行，vLLM 的批处理完全没用上

**文件**：`common/alfworld_runner.py`　**换机器：强烈建议带**

实测吞吐：单路 **37 tok/s**，8 路 273 tok/s，16 路 **513 tok/s（14 倍）**，
而单请求延迟几乎不变。30 个 episode 从串行预估 3 小时降到 **16 分钟**。

但并发暴露了 TextWorld 的**两处线程不安全**，报错都指向完全无关的地方：

- 构建/reset：`fast_downward.pddl2sas()` 的 PDDL→SAS 翻译器有模块级可变状态
  → `KeyError: (2, 0)`（深在 `translate.build_sas_operator` 里）
- step：`textworld/envs/pddl/textgen` 的模块级 tatsu `_PARSER`，两个线程并发 pop
  它的 `_rule_stack` → `IndexError: pop from empty list`

**改法**：一把 `_ENV_LOCK` 串行化所有进入 TextWorld 的调用（build / reset / step）。
环境步进 <0.1s，而 LLM 调用 0.5s（spec）到 13s（adamem_think），锁只占个位数百分比，
等模型的部分仍全并发。

---

## TEST-1　"迷你冒烟测试"实际要跑约 2000 次模型调用

**文件**：`world_model_utility/collect_decision_points.py`、`generate_foresight.py`、`scripts/run_smoke_test.sh`

`collect_decision_points` 加 `--max_episodes/--max_points`，`generate_foresight` 加 `--max_points`，
体检改用 3 episode / 10 决策点（规范 §38 第 7 步的原意）。

## TEST-2　强制动作率闸门放得太靠后

**文件**：`scripts/run_smoke_test.sh`

原来在 Step 6，要等 Step 4-5 花掉约 2000 次调用之后才响。移到 **Step 2b**，
用前面 15 个便宜 episode 就判。**本次正是它在这个新位置拦下了 VALID-1 的 51% 兜底率。**

## TEST-3　体检从不检验分析链路

**文件**：`world_model_utility/evaluate_planning_gain.py`、`evaluate_oracle_gate.py`、`analyze.py`、
`failure_selection/evaluate_topk_vs_all.py`、`scripts/run_smoke_test.sh`

原体检止于 `build_counterfactual_pairs`，下游三个脚本要等全量跑完才第一次被执行。
现在体检把 `evaluate_planning_gain / evaluate_oracle_gate / analyze` 也跑一遍。
为此加了 `--calibration_points`（否则配置里的 50 会把 10 个点全吃进标定、评估子集为空）
和 `--max_tasks`（A8 全量是 4×30×3=360 episodes，体检跑不起）。两者正式运行都不传。

顺带修一处一致性问题：`evaluate_oracle_gate` 和 `analyze` 原本各自从**配置**读
`calibration_points`，改成从 `B_tau_c.json` / `B_evaluation_stats.json` 读
`evaluate_planning_gain` **实际用的**值，三个脚本的切分点不可能再互相打架
（仍然只依赖磁盘文件，满足"分析可从原始日志独立重建"）。

---

# 阶段 1 修复（5 项，均已验证）

上一轮诊断出的问题里，5 项已修复并逐一验证。

## FIX-1　实验 A 的纯噪声守卫

**文件**：`failure_selection/analyze.py`

`simulate_luck_baseline` 此前只接在 GO 分支上，没有能力把结论降级成"这次没测出来"。
合成数据验证过：教训效果设为完全为零（纯抛硬币）时，旧代码仍输出 **WEAK-GO**，
理由写着"某些教训显示负迁移，所以筛选有意义"。

新增两道 INCONCLUSIVE 闸门，**在任何 GO/WEAK-GO/NO-GO 判读之前**触发：

1. **地板效应**：配对评估 episode 的平均成功率 < 5% → Δ 几乎恒为 0 是因为
   agent 做不动任务，不是因为教训价值相同
2. **与运气不可区分**：`P(Δ≤0)` 的运气基线 p 值不显著，**且** `SR_TopK − SR_All < 0.05`

顺带修了一句会进最终报告的自相矛盾文案：旧代码无条件拼接
"(< 0.1 = distinguishable from pure chance)"，于是 p=1.00 的运行会打印
"luck-baseline p=1.00 (< 0.1 = distinguishable from pure chance)"。现在措辞随 p 值走，
并且把 `Var(Δ)` 的 p 值也一并披露。

**六个合成场景的验证结果**：

| 场景 | 判决 |
|---|---|
| 两个条件全失败（地板效应） | INCONCLUSIVE |
| SR=10%，教训完全无效果（纯噪声） | INCONCLUSIVE |
| SR=30%，教训完全无效果（纯噪声） | INCONCLUSIVE |
| SR=30%，教训有正向差异化效果 | INCONCLUSIVE |
| 存在负迁移 + 代理信号有效 | **GO** |
| 存在负迁移 + 代理信号无效 | **WEAK-GO** |

> 第 4 行值得说明：那组数据里教训**确实**有真实的差异化效果，但它的
> `Var(Δ)=0.0586` 甚至低于无效果那组的 `0.0653`——20 条教训 × 9 次试验的规模下，
> 这个设计**客观上分辨不了**它。判 INCONCLUSIVE 是诚实的，不是漏报。
> 这也正好量化了实验 A 当前样本量的能力边界。
>
> 注意方差统计量在这个规模下功效不足（真有效果时 p=0.20 检不出，无效果时 p=0.06 反而"显著"），
> 所以它只作为披露信息，**不参与判决**；判决仍以规范 §16 自己的主指标 `P(Δ≤0)` 为准。

## FIX-2　分支 rollout 的步数预算

**文件**：`world_model_utility/build_counterfactual_pairs.py`、`common/alfworld_runner.py`、
`configs/preexperiment.yaml`

两条分支的步数上限原本是"全局 30 减去决策点所在步数"。采样铺开后决策点分布到
`[0,0,1,2,3,4,7,14,22,29]`——**step 29 那个点两条分支各只剩 1 步**，必然双双失败、
Δ 恒为 0。这不是"预测没用"，是"没机会证明有没有用"。

`rollout()` 新增 `max_steps` 覆盖参数；两条分支改为都从决策点起算
`experiment_b.branch_rollout_budget`（默认 30）步。预算相同，配对比较依然成立。

实测：step 29 的那个点现在拿到完整 30 步（仍然失败，但这次是真实失败）。

## FIX-3　`prompt_style` 贯通到所有 `choose_action` 调用点

**文件**：`world_model_utility/collect_decision_points.py`、`generate_foresight.py`

这两个脚本的 `choose_action` 调用没传 `prompt_style`，会静默退回 `"spec"`；
而分支续跑走的 `rollout()` 会从配置读 `adamem_think`。结果是**走到决策点的轨迹和
base_action 用不推理的规划器，决策点之后的续跑用会推理的规划器**——混合策略。
现在三处都从配置读同一个值。

## FIX-4　B4 foresight 调用套上同一推理脚手架

**文件**：`common/alfworld_runner.py`（新增 `decide_action_from_prompt`）、
`common/prompts.py`、`world_model_utility/generate_foresight.py`

规范 §23 的 foresight 提示词是固定文本、单次调用无推理。若 base action 走
`adamem_think` 两段式，则

$$D_t = \mathbf{1}[a_t^{(W)} \neq a_t^{(0)}]$$

同时混入**两个**变化：看没看到世界模型预测、有没有经过推理。而 D_t 正是实验 B 要隔离的量。

抽出公共函数 `decide_action_from_prompt(llm, prompt, admissible, ...)`：任何已渲染好的
动作选择提示词都经它产出一个合法动作，`adamem_think` 下自动套上同一个 `<think>` 两段式。
规范的固定文本一字未改，只是外面包了同一层脚手架。推理指令也从 AdaMEM 模板里抽出来
（`ADAMEM_THINK_INSTRUCTION_SUFFIX`），由该函数统一追加。

实测对称性（同一状态、同一 seed）：

| prompt_style | base 动作 token | foresight 动作 token |
|---|---|---|
| `spec` | 6 | 2 |
| `adamem_think` | 229 | **240**（修复前是 2） |

## FIX-5　未变道决策点不跑 Branch W

**文件**：`world_model_utility/build_counterfactual_pairs.py`

`a_t^(W) == a_t^(0)` 时，Branch W 会从同一个还原状态执行同一个动作、再用同一个规划器续跑，
所以 `Y_W == Y_0`、`Δ_t == 0` 是**构造上必然**的。现在直接断言，不再实测。两个理由：

- **正确性**：vLLM 的批处理采样在并发下不可复现（同 prompt 同 seed，批组成不同就会分叉，
  本机已验证）。重跑同一条分支可能纯因批次数值差异分叉成 Δ_t = ±1，
  **在实验 B 最核心的 mismatch rate 上凭空制造信号**。
- **成本**：未变道点通常占多数，这一项直接省掉它们一半的 rollout。

实测：10 个决策点里 7 个未变道，rollout 次数从 20 降到 13，
未变道点的 `planning_gain` 全为 0、`base_success == foresight_success` 全部成立。

---

# 已知未修

阶段 1 修掉了原先 7 条里的 5 条（见上一节）。**剩下 2 条，都已诊断清楚但尚未动手：**

1. **【低】置信度与 ambiguity 退化。** 10 个决策点实测：自报置信度全部落在 0.95–0.99，
   ambiguity 全为 0。后果是 τ_c 取中位数后 gate 使用率接近 100%，
   "低置信但有用"这一格结构性为 0，`R_mismatch` 退化成单边指标；
   B11 的三个 ambiguity 分桶也只会有一个非空、图 3 无信息。
   这是模型行为而非代码缺陷，但分析脚本目前既不报告实际 gate 使用率，也不报告置信度分布，
   读者无从判断 `R_mismatch` 是否可信。**建议**：把 eval 子集的实际使用率和置信度直方图
   写进 `B_summary.json`，退化时在报告里明说。

2. **【低】统计披露不全。** `stats.mcnemar_exact` 已实现但从未被调用
   （规范 §35 要求"优先额外报告 McNemar"）；`R_mismatch` 没有置信区间，
   而 `_MIN_CHANGED_POINTS=10` 的下限意味着它可能只由十几个点算出，
   点估计 0.00 的 95% CI 实际能宽到 ±0.26。

## 仍然存在但属于设计取舍（非缺陷）

- **并发破坏 seed 复现性。** 串行发 3 次同一请求结果一致，并发（周围 15 个其他请求）
  3 次不一致——批处理的数值归约依赖批的组成，这是批量推理的常态。
  FIX-5 已消除它对实验 B 核心指标的污染路径（未变道点不再重跑）。
  **残留影响**：变道点两条分支的续跑、以及实验 A 的配对 episode，仍会有小幅方差，
  重跑数字会有波动。两个条件面对的批次环境是随机混合的，不产生系统性偏向。
  要完全消除只能串行跑，代价是 14 倍的时间。

- **`prompt_style: "adamem_think"` 改变结论的适用范围。** 测出的 Δ 是"教训对一个
  **会推理的** agent 的价值"，不是"对规范 §5.1 那个裸 agent 的价值"。
  它对所有条件一视同仁（有教训/无教训、base/foresight），不偏袒任何一方，
  但适用对象变了，必须写进最终报告。默认值仍是 `"spec"`。

- **`build_counterfactual_pairs` 未并行。** 实测 13 次 rollout 用了 6 分 24 秒；
  150 个决策点的全量运行按此外推约 80 分钟。`_ENV_LOCK` 已使并发安全，
  加线程池即可，但会放大上面那条 seed 复现性的残留影响，故暂未做。

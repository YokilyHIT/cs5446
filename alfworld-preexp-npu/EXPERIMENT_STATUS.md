# 预实验现状总表：设置 / 结果 / 已知问题 / 代码索引

**更新日期** 2026-09-09 · **机器** Ascend 910B3 × 2 (aarch64, Python 3.11) ·
**仓库根** `/home/ma-user/work/5446/cs5446-master/alfworld-preexp-npu`

---

## 0. 一句话现状

三条实验线：**实验 A**（教训选择性学习，WEAK-GO，已结束）、**旧实验 B**（世界模型效用，GO，已结束）、
**方向二**（Planning Utility vs Prediction Confidence，进行中）。

方向二本轮最重要的事：**动作级和 episode 级给出了相反的结论**。动作级说 foresight 净有害
（−0.6pp），episode 级说 foresight 净有益（+4.3pp）。这不是 bug，是两个指标测的本来就不是
一件事——详见 §3.3。**在 episode 级复现出来之前，所有基于动作级的结论都不能当结论用。**

---

## 1. 实验设置

### 1.1 各部件用的模型

| 部件 | 模型 | 谁在用 | 配置位置 |
|---|---|---|---|
| **Planner**（选动作） | Qwen3-4B-Instruct-2507 | 全部三臂共用 | `preexperiments/configs/preexperiment.yaml:9` |
| **World Model**（预测下一步观察） | **同一个** Qwen3-4B-Instruct-2507 | always / selective 臂 | 同上 |
| **Embedding**（只用于给指标打分） | all-MiniLM-L6-v2 (22M, CPU) | 不进 agent 回路 | `preexperiment.yaml:57` |
| **Episodic Memory 检索** | **不用模型**——动作词元 Jaccard | Strong WM 臂 | 论文机制本身就是词法的 |

服务方式：vLLM 0.11.0 + vllm-ascend 0.11.0，OpenAI 兼容接口 `http://127.0.0.1:8001/v1`，
本仓库只走 HTTP。

对照 WorldEvolver：planner + world model 用 Gemma-4-26B / Qwen3.5-9B / Gemma-4-31B，
embedding 用 Qwen3-Embedding-8B。

### 1.2 解码参数

| | 方向二 | 实验 A / 旧实验 B |
|---|---|---|
| temperature | **0.0** | 0.7（对齐 AdaMEM runner） |
| top_p | 0.5 | 0.95 |
| seed | 42 | [13, 37, 73] |
| max steps | 30 | 30 |
| 动作解码 | vLLM `guided_choice` 约束到 admissible 集合 | 同（`prompt_style: adamem_think` 时不约束） |

方向二的 temperature 0 / top_p 0.5 / seed 42 是**照 WorldEvolver 原文**设的，
方案 §40 也独立要求 temperature=0。配置段 `preexperiment.yaml: direction_b:`。

### 1.3 数据划分

| 用途 | 划分 | 规模 |
|---|---|---|
| 动作级 state 采样（方向二 Stage 1/3） | **train** | 100 条 expert 轨迹 → 500 states（剔除 expert-noop 后 353） |
| Episodic Memory 转移库 | **train** | 200 条轨迹 → 3588 条真实转移 |
| **Episode 级评测（方向二）** | **eval_in_distribution**（valid_seen） | **140 games** |
| 实验 A / 旧实验 B | train（收集） + eval_in_distribution（评测） | 见 §2 |

⚠️ 动作级实验只能在 train 上做，因为 ALFWorld 的 `expert_plan` 只在 train 划分附加
（`alfred_tw_env.py`: `expert_plan = True if self.train_eval == "train" else False`）。
这是**诊断实验，不是泛化测试**。

### 1.4 关键实现约定

- **§39 单变量约束**：`baseline_action` 和 `foresight_action` 由**同一个模板** + 一个可选的
  foresight 块生成，两者只差"有没有想象的下一步观察"这一件事。
  同样的纪律用在世界模型上：`{memory_block}` 渲染为空时与改动前的 prompt **逐字节相同**（已断言验证）。
- **约束解码的理由**：实测 Qwen3-4B 自由解码有 **51% 的步**产出非法动作，
  `ground_action` 的 difflib 回退会把它映射到**另一个物体**的动作，导致无限循环——
  那样测的是 action formatting 而非 planning。约束在两臂上完全相同，不会偏袒被测的比较。
- **Episodic Memory 泄漏控制**：查询 `(episode e, step t)` 时丢弃 e 中 step ≥ t 的全部条目
  （保留 step < t，那是 agent 真的已掌握的经验）。500 行穷举检查，**违规 0 例**。
  Jaccard 并列时按 `(episode_id, step_id)` 破平，保证可复现。

---

## 2. 实验 A 和旧实验 B 的位置（已结束）

### 2.1 实验 A：失败教训是否有选择性价值

**代码** `preexperiments/failure_selection/`

| 文件 | 作用 |
|---|---|
| `collect_failures.py` | 在 train 上跑 baseline，收集失败 episode |
| `extract_lessons.py` | 让 LLM 从每个失败里抽一条教训 |
| `select_related_tasks.py` | 为每条教训挑相关任务 |
| `evaluate_single_lessons.py` | 单条教训的配对评测（Δ 分布） |
| `evaluate_topk_vs_all.py` | NoMemory / AllLessons / TopK / RandomK 四臂 |
| `score_failure_proxies.py` | 教训价值的代理特征打分 |
| `analyze.py` | 汇总 + Go/No-Go 判定 + 出图 |

**结果** `results/A_*.{json,jsonl,csv}`，汇总在 `results/A_summary.json`；
图 `figures/A_failure_utility_hist.png`、`figures/A_topk_vs_all.png`。

**结论：WEAK-GO**
- P(Δ<0)=0.600，纯噪声 luck-baseline p=0.015 → **负迁移是真的**，不是采样噪声
- 但四臂成功率：**NoMemory 34.4%** > AllLessons 33.3% > TopK 30.0% > RandomK 23.3%
  —— 检索教训反而不如不用
- ρ_U = −0.196（p=0.41，不显著）

### 2.2 旧实验 B：世界模型 foresight 的效用（episode 级，temp 0.7）

**代码** `preexperiments/world_model_utility/`

| 文件 | 作用 |
|---|---|
| `collect_decision_points.py` | 从 base episode 里取决策点 |
| `generate_foresight.py` | 生成 foresight + 自报 confidence |
| `build_counterfactual_pairs.py` | 构造 Branch 0 / Branch W 反事实分支 |
| `evaluate_planning_gain.py` | 分支 rollout，算 planning gain |
| `evaluate_oracle_gate.py` | Oracle 门控上界 |
| `analyze.py` | 汇总 + Go/No-Go |

**结果** `results/B_*.{json,jsonl,csv}`，汇总 `results/B_summary.json`；
temp 0.2 那一轮归档在 `results_temp02_spec/`；
图 `figures/B_confidence_vs_gain.png` 等三张；报告 `reports/experiment_B_report.md`。

**结论：GO** —— oracle_gain 0.060，CI [0.02, 0.11]；mismatch_rate 0.136；
但 ρ_self = 0.098（CI 跨 0），即**自报 confidence 与 gain 无关**，这正是方向二的起点。

---

## 3. 方向二：结果

### 3.1 世界模型预测质量（n=500，train states）

| 指标 | Weak (0-shot) | **Strong (+Episodic Memory)** | WorldEvolver 完整系统 |
|---|---|---|---|
| Exact Match | 12.40% | **57.80%** (+45.4pp) | 52.88% |
| Token F1 | 53.33% | **84.91%** (+31.6pp) | 76.75% |
| Fact F1 | 66.60% | **75.85%** (+9.3pp) | — |
| Cosine | 71.98% | 87.62% | 80.13% |

检索命中率 100%，平均 5.00/5。**"世界模型太弱"这个反驳关闭了**（就 EM 和 Token F1 而言，
Cosine 列不可比，见 §4.1）。

三个指标的含义：**Exact Match** = 归一化后逐字相同才给 1（最严）；
**Token F1** = 词级重合的 F1（说对一半给一半分）；**Cosine** = 两句话过 embedding 后的语义夹角（最松）。

### 3.2 动作级（n=353，train，剔除 expert-noop）

单步问"选出来的动作 == expert 这一步的动作吗"。

| 策略 | Weak WM | Strong WM |
|---|---|---|
| 无 foresight | 40.5% | 40.5% |
| 总是 foresight | 39.4% | 39.9% |
| 选择性（logprob 门） | 40.8%（用 30.0%） | 40.8%（用 10.2%） |
| 选择性（self-report 门） | 39.4%（98.9%） | 39.7%（99.7%） |
| Oracle 上界 | 42.2% | 42.2% |

**世界模型好了 45pp，Oracle 上界纹丝不动。** Oracle − 最优置信度门 = +1.4pp，
低于方案 §34 条件 4 的 5pp 门槛。

**机制**（按 baseline 本来对不对分层）：

| | n | ACR | AIR | AHR | 净 |
|---|---|---|---|---|---|
| base 本来就 = expert | 143 | 5.6% | 0.0% | 5.6% | **−5.6%** |
| base ≠ expert | 210 | 12.9% | 2.9% | 0.0% | **+2.9%** |

两层里预测越准，效果都越强（该帮的更帮，该害的更害）。所以不是"错预测带偏"，而是
**foresight 让规划器改动作；baseline 错时改对了，baseline 对时改错了，而规划器分不清自己在哪一边**。

置信度对"baseline 是否已对"几乎零信息：logprob 在两组间只差 **0.0016**。
而门控换成 `1[baseline is WRONG]` 直接打到 42.2%，与需要预知答案的 Oracle 同一上界，且**可学**。

### 3.3 ⚠️ Episode 级（n=140，eval_in_distribution，30 步）—— 结论反转

**这是本轮最重要的结果。**

| 策略 | 成功率 | 平均步数 | Foresight 使用率 | WM 调用数 |
|---|---|---|---|---|
| 无 foresight | **9.29%** (13/140) | 28.1 | 0% | 0 |
| 总是 foresight | **13.57%** (19/140) | 27.3 | 100% | 3820 |
| 选择性 foresight | **13.57%** (19/140) | 27.8 | **16.3%** | 3893 |

配对 McNemar 检验（同一批 game）：

| 对比 | 谁赢 | p |
|---|---|---|
| 无 vs 总是 | 总是赢 9，无赢 3 | 0.146（不显著） |
| **无 vs 选择性** | **选择性赢 6，无赢 0** | **0.031（显著）** |
| 总是 vs 选择性 | 8 : 8 | 1.000 |

两臂成功率相同但**不是同一批 game**（交集只有 11/19）。

与 WorldEvolver 对比（他们 Gemma-4-26B, ReAct, AgentBoard 134 任务）：

| | 无 | 总是 | 选择性 | 选择性−总是 | 选择性−无 |
|---|---|---|---|---|---|
| WorldEvolver | 23.88% | 24.63% | 26.12% | +1.49pp | +2.24pp |
| **我们** (Qwen3-4B) | 9.29% | 13.57% | 13.57% | **+0.00pp** | **+4.29pp** |

**读法**：
1. **绝对值只有他们的一半**，与 4B vs 26B 的规模差一致，不构成反驳。
2. **"foresight 有用"复现出来了，而且比他们更强**（+4.29pp vs +2.24pp），
   且选择性臂从未输掉一个无 foresight 能赢的 game。
3. **"选择性 > 总是"没有复现**（我们 +0.00pp vs 他们 +1.49pp）。
   但选择性只花了 **16.3%** 的 foresight 就打平总是 —— 省 6 倍开销，不掉分。
   这与动作级结论一致：置信度门**省钱有效，提分无效**。
4. **动作级说 foresight 有害（−0.6pp），episode 级说有益（+4.3pp）——两者矛盾。**
   合理解释：动作级把"偏离 expert"一律记为坏，但 ALFWorld 常有多条可行路径，
   偏离 expert 不等于失败；而 episode 级只看最后做没做完。
   **以 episode 级为准**，动作级只能当机制诊断工具。

---

## 4. 已知问题（按严重程度）

### 4.1 会影响已发布结论的

1. **Cosine 那一列跨论文不可比。** 我们用 all-MiniLM-L6-v2，WorldEvolver 用 Qwen3-Embedding-8B，
   两者 cosine 数值尺度完全不同（MiniLM 上两句毫不相干的 ALFWorld 观察中位数就有 0.399）。
   之前说"三项指标全面超过完整系统"，**Cosine 那一项站不住**；EM 和 Token F1 可比。
2. **动作级结论已被 episode 级推翻**（§3.3）。凡引用 "foresight 净有害 −0.6pp / −1.1pp"
   的地方都必须加限定："在单步 expert-match 指标下"。
3. **`ρ_self = −0.111 (p=0.036)` 是提示性证据，不是确证。** 本轮跑了多个相关系数，
   p=0.036 经不起多重比较校正。

### 4.2 限制外推的

4. **模型规模差 6 倍**（4B vs 26B/31B）。硬件约束下的取舍：两张 NPU 卡要长时间跑几千次调用。
   "4B 分不清自己原计划对不对"不代表 30B 也分不清。
5. **planner 和 world model 是同一份权重**（论文也这样，忠实）。副作用真实：
   两者的错误相关而非独立，会让 foresight 的增量信息偏小。
6. **动作级实验全在 train 划分**（`expert_plan` 只在 train 可得）。是诊断，不是泛化测试。
7. **Episodic Memory 的转移库来自 expert 轨迹**，而 WorldEvolver 是 agent 在线积累自己的经验。
   我们的库质量偏高（全是专家走过的路），这会高估 memory 的收益。
8. **Semantic Memory 未复现**，只做了 Episodic（对应论文 `w/o MS` 行的能力）。

### 4.3 尚未完成的

9. **Stage 2（H=3/5 短程 rollout）未做** —— 方案 §34 条件 4 真正要的量。
10. **Episode 级只跑了 Strong WM 一臂**，Weak WM 的 episode 级对照没跑，
    所以"memory 在 episode 级值多少分"目前未知。
11. **单 seed（42）** —— episode 级结果只有一次运行，6 个 episode 的差距（13 vs 19）需要多 seed 复测。
12. **成功率 9–13% 偏低**，30 步上限对 4B 偏紧（平均步数 27–28，说明大量 episode 是耗尽预算而非做错）。
13. 未推送到 GitHub（需要 token）；CoEx / Internalizing the Future 两篇未读。

### 4.4 已解决（留档）

- TextWorld 在 aarch64 上装不了（Inform7 6M62 无 aarch64 二进制）→ patch `setup.sh` 跳过
- `AlfredTWEnv` ImportError（alfworld 0.4.x）→ `_import_alfred_tw_env()` 三级回退
- `ModuleNotFoundError: acl` → `env.sh` 里 `PYTHONPATH` 必须 **append** 不能覆盖
- 51.3% 强制动作率 → `guided_choice` → 0.0%
- step-0 决策点无法还原 → 增加 `restore_observation`，失败 2/10 → 0/10
- TextWorld 非线程安全（fast_downward 的 `KeyError: (2,0)`、tatsu 的 `IndexError`）→ 全局 `_ENV_LOCK`
- Stage 0 只有 ~7 req/min → dagger expert wrapper 在锁内重复执行 → 改 dqn + 两阶段拆分 → 30 states/50s
- 实验 A 的纯噪声守卫只 gate 了 GO → 补 INCONCLUSIVE 门，6 个场景验证

---

## 5. 代码索引

```
preexperiments/
├── common/                         三条线共用
│   ├── alfworld_runner.py          ★ 环境适配 + 动作选择 + episode rollout
│   │                                 _ENV_LOCK / _import_alfred_tw_env /
│   │                                 visible_actions(排除 help) / format_history(50轮)
│   ├── llm_client.py               ★ vLLM 客户端：guided_choice / logprobs→mean_logprob / prefill
│   ├── embeddings.py               all-MiniLM-L6-v2 封装 + cosine_sim
│   ├── prompts.py                  spec 版 / AdaMEM <think> 版动作模板
│   ├── replay_state.py             决策点状态还原（含 restore_observation 修复）
│   ├── parallel.py                 ordered_map：并发但保证输出顺序确定
│   ├── stats.py                    bootstrap CI / 相关系数
│   └── logging_utils.py            配置加载 + 环境变量覆盖
│
├── configs/
│   ├── preexperiment.yaml          ★ 唯一配置源（模型/解码/划分/direction_b 段）
│   └── alfworld_base_config.yaml   training_method: dqn + dagger 段（expert_plan 需要）
│
├── failure_selection/              【实验 A】→ results/A_*
├── world_model_utility/            【旧实验 B】→ results/B_*
│
└── direction_b/                    【方向二】
    ├── sample_states.py            走 expert 轨迹采 500 个决策点 → data/sampled_states.jsonl
    ├── build_transition_bank.py    走 200 条轨迹 dump 全部转移 → data/transition_bank.jsonl（纯环境，无 LLM）
    ├── episodic_memory.py          ★ Episodic Memory：动作 Jaccard 检索 top-5 + 因果过滤
    ├── pipeline.py                 ★ Planner + World Model；ACTION_PROMPT 的 {foresight_block}
    │                                 和 WORLD_MODEL_PROMPT 的 {memory_block} 保证单变量
    ├── metrics.py                  Exact Match / Token F1 / Fact F1 / Cosine / risk-coverage
    ├── action_canonicalizer.py     动作归一化 + U = 1[a_fore==a*] − 1[a_base==a*]
    ├── run_action_level.py         Stage 1：两阶段（LLM 全并行 → 环境串行回放）
    ├── rebuild_foresight_arm.py    只重算 foresight 臂（省掉 ~1h 环境阶段）
    ├── run_strong_wm.py            ★ Strong WM 臂：WM + Episodic Memory，Weak/Strong 精确 A/B
    ├── run_episode_level.py        ★ Episode 级三臂（本轮新增，§3.3 的来源）
    ├── run_gate_comparison.py      Stage 3：四门对比 + Fig 4
    ├── run_framing_ablation.py     foresight 措辞三臂消融（A/B/C）
    ├── run_multiseed_acr.py        多 seed 复测 + 纯噪声对照臂
    └── analyze_confidence_utility.py  §18/§20-26 分析 + Fig 1-3
```

### 数据与产物

| 路径 | 内容 |
|---|---|
| `data/sampled_states.jsonl` | 500 个 expert 标注决策点 |
| `data/transition_bank.jsonl` | 3588 条真实转移（Episodic Memory 库） |
| `data/action_utility_framingB.jsonl` | Stage 1 Weak 臂 |
| `data/action_utility_strongwm.jsonl` | Stage 1 Strong 臂 |
| `data/episode_level_strong.jsonl` | **Episode 级三臂逐 episode 记录** |
| `outputs/tables/dirB_*.json` | 各阶段汇总表 |
| `figures/dirB_fig1..4*.png` | 置信度分箱 / 置信度-效用 / risk-coverage / 门控对比 |
| `reports/direction_b_strong_wm.md` | Strong WM 臂详细报告 |
| `reports/experiment_B_report.md` | 旧实验 B 报告 |
| `diagnostics/stage0_baseline.md` | Stage 0 基线 |
| `REPRODUCE.md` / `CHANGES_AND_KNOWN_ISSUES.md` | 环境搭建 / 改动清单 |

---

## 6. 复现命令

```bash
source /home/ma-user/work/5446/preexp_env/env.sh   # 注意 PYTHONPATH 必须 append

# 方向二：转移库（纯环境，~22 min）
$PY -m preexperiments.direction_b.build_transition_bank --episodes 100 --extra 100

# 方向二：Strong WM 臂（~4 min）
$PY -m preexperiments.direction_b.run_strong_wm --workers 16

# 方向二：动作级门控对比
$PY -m preexperiments.direction_b.run_gate_comparison \
    --rows action_utility_strongwm.jsonl --exclude_noop --tag _strongwm

# 方向二：Episode 级三臂（~75 min，140 games × 3）
$PY -m preexperiments.direction_b.run_episode_level \
    --workers 10 --memory --out episode_level_strong.jsonl --tag _strong
```

---

## 7. 下一步（按优先级）

1. **Episode 级多 seed 复测** —— 目前 13 vs 19 只差 6 个 episode，单 seed 不足以下结论。
2. **Episode 级跑 Weak WM 对照臂** —— 回答"Episodic Memory 在真实任务上值多少分"。
3. **训练/评测 `1[baseline is WRONG]` 门控** —— §3.2 显示它与 Oracle 同上界且可学，
   这是方向二真正的方法主张。
4. Stage 2（H=3/5 短程 rollout），补齐方案 §34 条件 4。
5. 放宽 30 步上限到 50 步复测一次 —— 平均步数 27–28 说明预算是活跃约束。

# 方向二 · Strong-WM 臂：给世界模型装上 Episodic Memory

**日期** 2026-09-09 · **数据** 500 states / 100 expert trajectories / ALFWorld train ·
**解码** temperature 0, top_p 0.5, seed 42 · **模型** Qwen3-4B-Instruct-2507

## 0. 为什么必须做这一臂

在此之前，方向二的全部结论（Always-Foresight 净 −0.8%、Oracle headroom +1.4pp）都建立在一个
**零样本世界模型**上。这留了一个致命的反驳口子：

> 你测出"foresight 没用"，可能只是因为你的世界模型太弱。预测一半是错的，
> 规划器当然不该听它的。

WorldEvolver 自己的消融表把这个反驳坐实了：他们的零样本行 Token F1 只有 35.48%，
而完整系统 76.75%；差距几乎全部来自 **memory**，不来自 gate。也就是说，
**我们此前复现的是他们的消融行，不是他们的系统**。

本臂补上缺的那一半：复现 WorldEvolver 的 Episodic Memory。

## 1. 实现（严格照论文机制）

| 论文机制 | 我们的实现 |
|---|---|
| 记忆条目 = 完整三元组 `(o_i, a_i, o_{i+1})`，不压缩 | `build_transition_bank.py` 走 expert 轨迹，逐步 dump |
| 检索键 = **候选动作**；相似度 = **动作词元的 Jaccard**（词法，非向量） | `episodic_memory.jaccard()` |
| `k_ME = 5`（论文报告 k=1→5 使 EM 提升 16.8/23.5 点） | `--k 5` |
| 渲染为 `## Retrieved similar past transitions` 块，前置于预测请求 | `EpisodicMemory.render()` |
| 在线累积，"记录只在执行后追加"故无污染 | 见 §2 |

转移库：**3588 条真实转移 / 200 条 expert 轨迹**（100 条与 `sampled_states.jsonl`
一一对齐，另 100 条不含任何被评测 state）。全程不调用 LLM，纯环境行走，约 22 分钟。

## 2. 泄漏控制（比论文更严）

论文靠"在线追加"天然免疫污染。我们的诊断是在**固定 state 集**上打分、库预先建好，
这个论证不自动成立——同一条 expert 轨迹里就含有待预测的那条转移本身。

`episodic_memory.retrieve()` 显式重建了他们的规则：查询 `(episode e, step t)` 时，
**丢弃 episode e 中 step ≥ t 的全部条目**，保留 step < t（那是 agent 真的已经掌握的经验），
其他 episode 全部可用（不同 game 实例、不同房间布局）。

对全部 500 行做了穷举检查：**因果过滤违规 0 例**。

排序在 Jaccard 相同时按 `(episode_id, step_id)` 破平——ALFWorld 动作高度模板化，
并列极多，不稳定排序会让整条 Strong 臂不可复现。

弱臂 prompt 保持**字节不变**（`{memory_block}` 渲染为空时与改动前的模板逐字节相同，
已断言验证），所以 Weak vs Strong 只差一件事。

## 3. 结果一：世界模型质量

n=500，对同一批 `true_next_observation` 打分（`a_base` 未变，故真值完全复用）。

| 指标 | Weak (0-shot) | **Strong (+EM)** | WorldEvolver 报告的**完整系统** |
|---|---|---|---|
| Exact Match | 12.40% | **57.80%** (+45.4pp) | 52.88% |
| Token F1 | 53.33% | **84.91%** (+31.6pp) | 76.75% |
| Fact F1 | 66.60% | **75.85%** (+9.3pp) | — |
| Cosine | 71.98% | **87.62%** (+15.7pp) | 80.13% |

检索命中率 100%，平均 5.00/5 条，无一 state 退化为零样本。

**"世界模型太弱"这个反驳到此关闭** —— 但只就 EM 和 Token F1 而言。

⚠️ **Cosine 那一列跨论文不可比，之前写"三项全面超过"是错的。** 我们用 all-MiniLM-L6-v2，
WorldEvolver 用 Qwen3-Embedding-8B，两个 embedding 模型的 cosine 数值尺度完全不同——
MiniLM 上两句毫不相干的 ALFWorld 观察中位数就有 0.399（见 `metrics.py` 模块注释）。
EM 和 Token F1 是纯字符串算的，那两列才可比（评测数据仍不同：他们 AgentBoard 134 任务，
我们 train 划分 500 states）。

一个必须说明的保留：增益中相当一部分是**格式对齐**而非物理理解。弱臂典型失败是
`"You are now at the desk. You see a desklamp..."` vs 真值
`"You arrive at desk 1. On the desk 1, you see a alarmclock 1, a bowl 1, ..."`——
Token F1 0.38 大半输在措辞。记忆直接提供了这个模板。这也正好解释了论文零样本行为何低至 35%。
Fact F1（只看实体，对措辞不敏感）增益最小（+9.3pp），与这一判断一致。

## 4. 结果二：动作层面（n=353，剔除 expert-noop）

| 臂 | ACR | AIR | AHR | 净 | fore==expert |
|---|---|---|---|---|---|
| Weak | 12.2% | 1.7% | 2.8% | **−1.1%** | 39.4% |
| **Strong** | 9.9% | 1.7% | 2.3% | **−0.6%** | 39.9% |
| 不用 foresight | — | — | — | — | **40.5%** |

世界模型好了 45 个百分点，**foresight 依然是净负的**，依然打不过完全不用 foresight。

四门对比（Stage 3）：

| Gate | ActionAcc | Foresight 使用率 |
|---|---|---|
| No Foresight | 40.5% | 0% |
| Always Foresight | 39.9% | 100% |
| Confidence Gate (self-report) | 39.7% | 99.7% |
| Confidence Gate (logprob) | 40.8% | 10.2% |
| Oracle Utility Gate | 42.2% | 1.7% |

Oracle − 最优 Confidence Gate = **+1.4pp**，与弱臂**完全相同**。§34 条件 4 的 5pp 门槛仍未达到。

## 5. 结果三：机制——为什么 foresight 是净负的

按"baseline 本来对不对"分层，图景完全变了（此前不分层的分层是有混淆的：
预测完全正确的 state 上 base 本来就有 50% 命中 expert，foresight 只能往下掉）：

**A. base 本来就 = expert（n=143，foresight 只可能变差）**

| 预测质量 | n | ACR | AIR | AHR | 净 |
|---|---|---|---|---|---|
| 完全正确 | 109 | 6.4% | 0.0% | 6.4% | **−6.4%** |
| 近乎正确 | 22 | 4.5% | 0.0% | 4.5% | −4.5% |
| 较差 | 12 | 0.0% | 0.0% | 0.0% | 0.0% |
| 小计 | 143 | 5.6% | 0.0% | 5.6% | **−5.6%** |

**B. base ≠ expert（n=210，foresight 有机会帮忙）**

| 预测质量 | n | ACR | AIR | AHR | 净 |
|---|---|---|---|---|---|
| 完全正确 | 109 | 17.4% | 3.7% | 0.0% | **+3.7%** |
| 近乎正确 | 35 | 11.4% | 2.9% | 0.0% | +2.9% |
| 较差 | 66 | 6.1% | 1.5% | 0.0% | +1.5% |
| 小计 | 210 | 12.9% | 2.9% | 0.0% | **+2.9%** |

两层里预测质量都是**单调有益**的：预测越准，该帮的地方帮得越多，该错的地方错得也越多。
净值 −5.6%·(143/353) + 2.9%·(210/353) = −0.55% ≈ 实测 −0.6%。

**机制因此不是"错误预测把规划器带偏"，而是：**
> foresight 会让规划器改变动作；当 baseline 本来是错的，改动是好的；
> 当 baseline 本来是对的，改动是坏的；而规划器分不清自己处在哪一种情形。

## 6. 结果四：置信度为什么原理上救不了它

若把门控换成"baseline 是不是已经错了"这个 oracle：

| Gate | ActionAcc | 使用率 |
|---|---|---|
| Oracle: `1[U>0]`（不可学，需知道答案） | 42.2% | 1.7% |
| **Oracle: `1[baseline is WRONG]`** | **42.2%** | 59.5% |

**两者达到同一上界。** 后者不需要知道正确答案，只需要判断"我当前的计划大概率是错的"——
这是**可学的**。

而世界模型的置信度对这个量几乎零信息：

| 信号 | base 已对 | base 错 | 差 |
|---|---|---|---|
| logprob confidence | 0.9834 | 0.9818 | **+0.0016** |
| self-report | 0.9772 | 0.9521 | +0.0251 |

相关性（n=353）：

```
confidence -> correctness   self_report token_f1 rho=+0.504 (p<0.001)
                            logprob     token_f1 rho=+0.032 (p=0.55)
confidence -> utility       self_report spearman=-0.111 (p=0.036)
                            logprob     spearman=+0.031 (p=0.56)
```

注意强臂上的一个反转：**logprob 置信度作为正确性信号崩溃了**（弱臂 ρ=+0.373 → 强臂 +0.032）。
原因很直接——模型现在在**抄检索到的文本**，token 概率一律很高，与抄得对不对无关。
反过来 self-report 成了不错的正确性信号（ρ=+0.504），但它对 utility 的相关是**负的**
（ρ=−0.111, p=0.036）。这一条只能算提示性证据，不能算确证：本轮跑了多个相关系数，
p=0.036 经不起多重比较校正。

## 7. 这一臂改变了什么

方向二的论点现在是这样一句话，且它在一个**比已发表系统更强的世界模型**上成立：

> Confidence 度量的是"我的预测对不对"；utility 取决于"我当前的计划对不对"。
> 这是两个正交的量（Δ=0.0016），所以任何基于预测置信度的门控在原理上都无法逼近
> 可达上界；而按"计划正确性"门控可以，且它可学。

⚠️ **但本报告的动作级结论随后被 episode 级实验推翻，见 `../EXPERIMENT_STATUS.md` §3.3。**
在 140 个 eval_in_distribution game 上跑完整 episode：无 foresight 9.29%、总是 13.57%、
选择性 13.57%（只用 16.3% 的步）。**episode 级 foresight 是净有益的（+4.29pp，选择性 vs 无
的配对 McNemar p=0.031）**，与本报告 §4 的动作级 −0.6% 相反。合理解释是动作级把"偏离 expert"
一律记为坏，而 ALFWorld 常有多条可行路径。**以 episode 级为准；本报告 §4–§5 的动作级数字
只能当机制诊断，不能当结论。** §6 的正交性论证（置信度 vs baseline 正确性，Δ=0.0016）
不依赖动作级的正负号，仍然成立。

三点仍需诚实标注：

1. Oracle headroom 仍只有 +1.4pp，**低于方案 §34 条件 4 设定的 5pp 门槛**。这是动作级
   accuracy 的头部空间，不是 episode 成功率的——Stage 2（H=3/5 短程 rollout）还没做。
2. 上述所有数字来自 ALFWorld **train** 划分（expert_plan 只在 train 上可得），
   是诊断实验，不是泛化测试。
3. Semantic Memory 与 Selective Foresight 的完整闭环未复现；本臂只补了 Episodic Memory
   （对应论文 `w/o MS` 那一行的能力，而实测已超过其完整系统的三项指标）。

## 8. 复现

```bash
source /home/ma-user/work/5446/preexp_env/env.sh
$PY -m preexperiments.direction_b.build_transition_bank --episodes 100 --extra 100   # ~22 min, 无 LLM
$PY -m preexperiments.direction_b.run_strong_wm --workers 16                          # ~4 min
$PY -m preexperiments.direction_b.run_gate_comparison --rows action_utility_strongwm.jsonl \
     --exclude_noop --tag _strongwm
$PY -m preexperiments.direction_b.analyze_confidence_utility --rows action_utility_strongwm.jsonl \
     --exclude_noop
```

产物：`data/transition_bank.jsonl`、`data/action_utility_strongwm.jsonl`、
`outputs/tables/dirB_strong_wm.json`、`outputs/tables/dirB_gate_comparison_strongwm.json`、
`figures/dirB_fig4_gate_performance_strongwm.png`。

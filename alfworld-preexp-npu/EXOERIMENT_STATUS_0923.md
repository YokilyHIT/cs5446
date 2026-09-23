# Direction B 实验发现总结：ReAct、Ground-Truth Foresight 与 Selective Foresight

## 1. 实验背景

本轮实验针对 Direction B 中的一个关键问题进行了重新诊断：

> 当 world-model foresight 不能提升、甚至损害 ALFWorld 任务表现时，问题究竟来自 world model 预测不准，还是来自 Planner 对 foresight 的使用方式本身？

为排除实现层面的混淆，本轮实验完成了以下修改与验证：

1. 保留原有 **direct action** 模式；
2. 新增可配置 **ReAct** 模式；
3. baseline 与 foresight 使用完全一致的推理流程与 action parser；
4. 禁止通过模糊匹配静默替换非法动作；
5. 新增 **ground-truth foresight probe**：
   - 在独立环境中执行 baseline action；
   - 获取真实的下一观察；
   - 将该真实观察作为“尚未发生的预测”重新提供给原状态 Planner；
   - 检查 Planner 是否仍然发生跳步；
6. 修复 confidence 统计：
   - 排除模型自报的 `Confidence:` 部分；
   - 仅使用真正决策相关 token 的 logprob；
7. 在修复后的 confidence 上重新校准 Selective gate 阈值；
8. 完整重跑 episode-level：None / Always / Selective；
9. 所有旧结果均保留，新结果使用独立文件名保存；
10. 本轮实验 **没有更换模型**。

---

## 2. 环境与实验有效性

本轮运行过程中发现当前容器的软件包环境已丢失，但持久化目录仍保留：

- 完整 Python venv；
- ALFWorld 数据集；
- 之前未完整下载的模型文件。

模型文件虽然表面文件大小接近完整，但通过 resumable downloader 的 block tracking 文件确认，实际仍存在缺失 block。

随后完成：

- 模型断点续传并验证完整；
- 启动 vLLM server；
- 验证真实 ALFWorld API；
- 通过 replay determinism 测试；
- 确认后续实验均运行于真实环境，而非 mock 环境。

因此，本轮结果可以视为真实 ALFWorld + 当前固定模型下的有效实验结果。

---

# 3. Ground-Truth Foresight Probe

## 3.1 目的

该实验的核心思想是：直接将 world-model prediction 替换成真实环境中的下一步 observation。

即：

\[
s_t \xrightarrow{a_t} s_{t+1}
\]

先在一个独立环境中执行 baseline action \(a_t\)，得到真实：

\[
o_{t+1}^{GT}
\]

再将：

\[
o_{t+1}^{GT}
\]

作为一个“尚未真正发生的未来预测”提供给仍然处于原状态 \(s_t\) 的 Planner。

这样可以近似构造：

\[
\text{World Model Accuracy} = 100\%
\]

如果在这种情况下 foresight 仍然导致错误，则问题不能再归因于 world model 预测质量。

---

## 3.2 典型案例：S00013

原状态下：

```text
a_base = open drawer 1
expert = open drawer 1
```

真实执行该动作后，下一观察为：

```text
You open the drawer 1...
you see nothing.
```

### Direct 模式

Planner 看到这条未来 observation 后，直接选择：

```text
examine drawer 1
```

也就是说，它实际上把：

> “如果现在执行 `open drawer 1`，未来会看到 drawer 被打开”

错误理解成了：

> “drawer 当前已经处于打开状态”

因此跳过了当前真正必须执行的：

```text
open drawer 1
```

此时 foresight utility：

\[
U=-1
\]

说明完美未来信息反而把原本正确的行为改坏了。

---

## 3.3 ReAct 模式

同一个状态下，ReAct Planner 显式推理：

> “The drawer is closed and contains nothing currently.”

关键点是：

```text
currently
```

Planner 正确地区分了：

- 当前状态；
- 假设执行动作后的未来状态。

因此最终仍选择：

```text
open drawer 1
```

没有发生 temporal skip。

类似现象也出现在 S00059：direct 模式会跳过“拿起 box”这一中间动作，而 ReAct 能正确保持当前时间状态。

---

# 4. Ground-Truth Probe 聚合结果

当前 probe 使用：

\[
n=50
\]

个 state。

结果如下：

| Planner Mode | AHR | AIR | Net |
|---|---:|---:|---:|
| Direct | 4% | 0% | -4% |
| ReAct | 0% | 6% | +6% |

其中：

- **AHR**：Action Harm Rate，即 foresight 将原本正确的 action 改坏的比例；
- **AIR**：Action Improvement Rate，即 foresight 将原本错误的 action 改好的比例；
- **Net**：

\[
\text{Net} = AIR - AHR
\]

因此：

### Direct

\[
0\%-4\%=-4\%
\]

说明即使使用真实下一观察：

> perfect foresight 在 direct 模式下仍然可能产生净负收益。

### ReAct

\[
6\%-0\%=+6\%
\]

说明：

> 在当前 50 个 state 上，ReAct 能将 perfect foresight 转化为正向 planning signal，并且没有观察到 harmful case。

---

# 5. 最重要的诊断结论

本轮实验表明：

\[
\boxed{
\text{Perfect World Model}
\centernot\Rightarrow
\text{Better Planning}
}
\]

问题不只在于：

> world model 是否预测准确。

还在于：

> Planner 是否正确理解预测结果在时间上的语义。

如果 Planner 将：

\[
\hat{o}_{t+1}
\]

错误地当作：

\[
o_t
\]

则会出现：

\[
\text{future observation}
\rightarrow
\text{state confusion}
\rightarrow
\text{action skipping}
\]

即使：

\[
\hat{o}_{t+1}=o_{t+1}^{GT}
\]

也可能损害 planning。

因此，一个更准确的表述是：

\[
\boxed{
\text{Useful Foresight}
=
\text{Accurate Prediction}
+
\text{Correct Temporal Grounding}
}
\]

---

# 6. Confidence 修复

## 6.1 原问题

原 confidence 统计中包含模型文本输出中的：

```text
Confidence: ...
```

相关 token。

例如：

```text
Thought: ...
Action: open drawer 1
Confidence: 0.95
```

如果将：

```text
Confidence:
0.95
```

本身对应的 token logprob 也平均进去，则得到的 confidence 会受到输出格式影响，而不是纯粹反映 action decision 的确定性。

## 6.2 修复

新版本 confidence：

- 排除自报 `Confidence:` 段；
- 只统计真正与 decision/action generation 有关的 token；
- 不再让 self-reported confidence 文本污染 logprob-based confidence。

修复后，各 state confidence 值发生了非均匀变化。

这说明此次变化不是：

\[
C_{new}=C_{old}+c
\]

这种简单常数平移，而是实际改变了不同样本之间的置信度排序。

---

# 7. Gate Threshold 重新校准

在完整：

\[
n=500
\]

个 calibration states 上重新标定 gate threshold。

旧阈值：

\[
\tau=0.9990
\]

修复后：

\[
\boxed{\tau=0.9997}
\]

因此旧 threshold 不应再直接用于修复后的 confidence。

---

# 8. Episode-Level 完整结果

完整评估使用：

\[
140
\]

个 ALFWorld games。

结果：

| Arm | Direct | ReAct |
|---|---:|---:|
| None | 8.57% | 17.86% |
| Always | **15.00%** | **19.29%** |
| Selective | 7.86% | **19.29%** |

---

# 9. Finding 1：ReAct Baseline 本身显著更强

不使用任何 foresight 时：

### Direct

\[
8.57\%
\]

### ReAct

\[
17.86\%
\]

绝对提升：

\[
+9.29\text{ percentage points}
\]

相对提升约：

\[
\frac{17.86-8.57}{8.57}
\approx108\%
\]

因此：

> 当前模型下，free-form reasoning + strict action parsing 明显优于 guided-choice / bare-action direct decoding。

这意味着当前实验中一个非常重要的 confound 是 **Planner interface 本身**。

不能将 Direct → ReAct 带来的增益错误归因于 foresight。

---

# 10. Finding 2：Direct 下 Selective Foresight 失败

Direct：

\[
None=8.57\%
\]

\[
Always=15.00\%
\]

\[
Selective=7.86\%
\]

即：

\[
\boxed{
Selective < None < Always
}
\]

这说明在 direct 模式下：

> 当前 confidence gate 没有正确选出“值得使用 foresight”的 state。

甚至 Selective 选择出来的 states 总体上比“不使用 foresight”更差。

因此：

> confidence 本身并不能在 direct Planner 下可靠表示 foresight utility。

---

# 11. Finding 3：ReAct 下 Selective Foresight 达到预期行为

ReAct：

\[
None=17.86\%
\]

\[
Always=19.29\%
\]

\[
Selective=19.29\%
\]

因此：

\[
\boxed{
Selective=Always>None
}
\]

更重要的是：

Selective 只调用了约：

\[
25\%
\]

的 world-model calls。

换句话说：

\[
\boxed{
75\%\text{ fewer world-model calls}
}
\]

同时保持：

\[
19.29\%
\]

与 Always 完全相同的完整任务成功率。

这是当前结果中最符合 selective foresight 设计目标的现象。

---

# 12. 公平解读 Foresight 增益

不能直接比较：

\[
8.57\%\rightarrow19.29\%
\]

并将其全部归因于 foresight。

因为其中很大一部分来自：

\[
\text{Direct Planner}
\rightarrow
\text{ReAct Planner}
\]

公平比较应该固定 Planner mode。

## Direct 内部

Always：

\[
8.57\%\rightarrow15.00\%
\]

即：

\[
+6.43\text{ pp}
\]

但 Selective：

\[
8.57\%\rightarrow7.86\%
\]

即：

\[
-0.71\text{ pp}
\]

## ReAct 内部

Always：

\[
17.86\%\rightarrow19.29\%
\]

Selective：

\[
17.86\%\rightarrow19.29\%
\]

均为：

\[
\boxed{+1.43\text{ pp}}
\]

因此当前最稳妥的实验陈述是：

> Under the ReAct planner, selective foresight matches always-on foresight in full-task success rate while using only about 25% of the world-model calls.

---

# 13. 当前最值得强调的研究故事

原始研究问题可以表述为：

> When should an LLM agent trust its imagination?

但本轮实验表明，在这个问题之前还存在一个更基础的问题：

> Can the planner correctly understand an imagined future as a counterfactual future rather than as the current state?

因此，一个更完整的问题结构是：

### Step 1：World Model Quality

\[
\hat{o}_{t+1}\approx o_{t+1}
\]

### Step 2：Temporal Grounding

Planner 是否理解 \(\hat{o}_{t+1}\) 是“如果执行当前 action 后可能出现的未来”，而不是“当前已经成立的 observation”。

### Step 3：Planning Utility

该 foresight 是否真正改变当前 action decision，并提高完整任务 success。

### Step 4：Selective Invocation

能否只在真正有用的状态调用 world model，从而降低推理成本。

---

# 14. 当前核心结论

## 结论 1

> Foresight failure 不能简单归因于 world model prediction error。

Ground-truth foresight probe 表明，即使输入真实下一观察，direct Planner 仍然可能发生跳步。

## 结论 2

> Direct Planner 存在明显的 temporal grounding failure。

它容易把“未来预测”解释成“当前已经发生的状态”。

## 结论 3

> ReAct reasoning 明显缓解了该问题。

在 n=50 ground-truth probe 中：

- Direct：Net = -4%
- ReAct：Net = +6%

## 结论 4

> Confidence-based selective foresight 是否有效，高度依赖 Planner interface。

Direct 下：

\[
Selective < None
\]

ReAct 下：

\[
Selective=Always>None
\]

## 结论 5

> 在当前配置下，ReAct + Selective 已经表现出理想的效率行为。

完整任务成功率：

\[
19.29\%
\]

与 Always 相同，同时仅使用约：

\[
25\%
\]

world-model calls。

---

# 15. 当前不能过度声称的结论

虽然 n=50 的 ground-truth probe 趋势非常清晰，但目前样本仍然较少。

例如：

Direct：

\[
AHR=4\%
\]

在 50 个样本中大约对应 2 个 harmful states。

ReAct：

\[
AIR=6\%
\]

大约对应 3 个 improved states。

因此目前适合说：

> The n=50 probe provides direct evidence that temporal misinterpretation can cause action skipping under direct decoding, while the observed cases disappear under ReAct.

但暂时不宜仅凭 n=50 强声称：

> ReAct completely eliminates foresight harm in general.

---

# 16. 推荐下一步

建议将 ground-truth foresight probe 扩展到：

\[
n=200
\]

至少，更理想是：

\[
n=500
\]

并统计：

- AHR；
- AIR；
- Net utility；
- Direct vs ReAct paired comparison；
- harmful state 类型；
- improvement state 类型；
- action-skip proportion；
- confidence 与真实 foresight utility 的相关性。

如果趋势继续保持，将更有力地支持：

> Perfect foresight can still be harmful when the planner lacks correct temporal grounding.

以及：

> ReAct-style explicit reasoning improves the planner's ability to consume counterfactual future observations.

---

# 17. 新旧结果文件

本轮实验保留了所有旧结果。

旧文件未覆盖，包括：

```text
action_utility.jsonl
episode_level_strong.jsonl
dirB_gate_comparison.json
```

新结果单独保存为：

```text
data/action_utility_confidencefix.jsonl
data/episode_level_confidencefix.jsonl
data/episode_level_react_confidencefix.jsonl
data/ground_truth_foresight_probe.jsonl
```

对应汇总结果位于：

```text
outputs/tables/dirB_*.json
```

因此当前可以明确区分：

1. original pipeline；
2. confidence-fixed direct；
3. ReAct + confidence-fixed；
4. ground-truth foresight diagnostic。

---

# 18. 一句话总结

> **The bottleneck was not only whether the world model could predict the future, but whether the planner could correctly understand that future as counterfactual rather than current.**

更具体地：

\[
\boxed{
\text{Useful Foresight}
=
\text{Prediction Quality}
+
\text{Temporal Grounding}
+
\text{Planning Utility}
}
\]

而当前实验进一步表明：

\[
\boxed{
\text{ReAct + Selective}
}
\]

是目前最合理的 Direction B 实现路径。

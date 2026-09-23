# CS4246/5446 项目候选方向：两个与 2026 年最新 Agent Planning 工作衔接的研究方案

> **定位说明**：这两个方向都不是"搭一个通用 Agent
> 系统"，而是围绕一个明确的 planning / sequential decision-making
> 机制提出可验证的小型研究问题。两者都优先使用 **ALFWorld
> 家庭任务规划**，这样可以与 2026 年最新的 Agent Memory / World Model
> 工作尽量使用同一套实验生态。推荐默认 backbone 为
> **Qwen3-4B-Instruct-2507**。

------------------------------------------------------------------------

# 方向一：面向持续家庭任务规划的选择性失败学习

## 1. 建议题目

**Which Mistakes Are Worth Learning From? Selective Failure Learning for
Continual Household Task Planning**

中文：

**哪些错误值得学习？面向持续家庭任务规划的选择性失败经验学习**

### 核心研究问题

> 当 LLM Agent
> 在连续执行家庭任务时，不应该把所有失败都转化成长期记忆。那么，能否在"失败经验抽象成
> Memory"之前，判断哪些失败真正值得学习？

我们研究的不是完整 Memory Architecture，而是一个非常具体的决策：

$$
\boxed{\text{哪些失败轨迹应该进入长期记忆学习流程？}}
$$

------------------------------------------------------------------------

# 2. 与 2026 最新工作的关系

## 2.1 AdaMEM

**AdaMEM: Test-Time Adaptive Memory for Language Agents**

AdaMEM 关注传统 memory agent 的一个问题：很多方法只在 episode
开始时检索一次长期记忆，之后执行过程中 memory 基本固定。

AdaMEM 引入：

-   Long-term trajectory memory；
-   Dynamic short-term strategy memory；
-   Step-level test-time adaptation；
-   核心机制不要求在线更新模型参数。

它在 **ALFWorld、WebShop、HotpotQA** 上进行了实验，公开代码中也提供了
**Qwen3-4B-Instruct-2507 + ALFWorld** 的配置。

### 和我们的区别

AdaMEM 主要研究：

$$
\boxed{\text{Agent 在执行过程中应该如何使用和动态调整 Memory？}}
$$

我们研究一个更前置的问题：

$$
\boxed{\text{哪些失败经验一开始就值得进入 Memory Learning Pipeline？}}
$$

------------------------------------------------------------------------

## 2.2 AgeMem

**Agentic Memory: Learning Unified Long-Term and Short-Term Memory
Management for Large Language Model Agents**

AgeMem 将 Memory Operation 本身纳入 Agent Policy，例如：

$$
a_t^{\text{mem}}
\in
\{
\text{store},
\text{retrieve},
\text{update},
\text{summarize},
\text{discard}
\}.
$$

它关注的是：

> Agent 如何学习管理长期和短期记忆？

我们的区别在于：

-   不训练一个新的 memory policy；
-   保持 training-free；
-   只研究 **failure selection**。

------------------------------------------------------------------------

## 2.3 Mistake Notebook Learning（MNL）

**Mistake Notebook Learning: Batch-Clustered Failures for Training-Free
Agent Adaptation**

MNL 是和我们最接近的 baseline。

它的大致流程是：

$$
\text{Failures}
\rightarrow
\text{Cluster}
\rightarrow
\text{Mistake Abstraction}
\rightarrow
\text{Mistake Notes}
\rightarrow
\text{Future Inference}.
$$

具体来说：

1.  收集失败轨迹；
2.  将相似失败进行聚类；
3.  从每个 failure cluster 中抽象出 generalized mistake note；
4.  检查新的 mistake notes 是否真的改善 batch performance；
5.  将有效 notes 加入后续推理。

MNL 本身并不是以 ALFWorld 为主要 benchmark，因此如果我们在 ALFWorld
上实现 MNL，应明确称为 **MNL-port / our reproduction of MNL on
ALFWorld**。

### 我们的方法插在哪里？

我们在 MNL 的 clustering **之前**加入 Failure Selection：

$$
\text{Raw Failures}
\rightarrow
\boxed{\text{Failure Selection}}
\rightarrow
\text{Clustering}
\rightarrow
\text{Mistake Abstraction}
\rightarrow
\text{Memory}.
$$

所以我们的贡献不是重新设计 MNL，而是研究：

> MNL 是否真的应该让所有失败进入 clustering / abstraction？

------------------------------------------------------------------------

# 3. Research Gap

假设 Agent 产生失败集合：

$$
F=\{f_1,f_2,\ldots,f_n\}.
$$

并不是所有失败都包含值得迁移的 planning knowledge。

一些失败可能是：

-   已经出现过很多次的重复错误；
-   随机探索导致的偶然失败；
-   输出格式错误；
-   只对当前房间布局成立的 task-specific error；
-   信息不足导致的失败，而不是 planning error。

如果所有失败都进入 abstraction：

$$
F
\rightarrow
\text{Cluster}
\rightarrow
M,
$$

可能导致：

$$
|M|\uparrow,
$$

同时：

$$
\text{Retrieval Noise}\uparrow,
\qquad
\text{Token Cost}\uparrow,
\qquad
\text{Bad / Redundant Rules}\uparrow.
$$

因此我们的核心 gap 是：

$$
\boxed{
\text{Failure Occurrence}
\neq
\text{Failure Learning Value}
}
$$

即：

> 一个失败发生了，不代表它值得被 Agent 学习。

------------------------------------------------------------------------

# 4. Hypothesis

## H1：选择性失败学习能够提高性能

$$
SR_{\text{selective}}
>
SR_{\text{all-failure}}.
$$

其中 (SR) 表示任务成功率。

------------------------------------------------------------------------

## H2：选择性失败学习能够减少 Memory

希望：

$$
|M_{\text{selective}}|
<
|M_{\text{all-failure}}|,
$$

同时：

$$
SR_{\text{selective}}
\ge
SR_{\text{all-failure}}.
$$

也就是：

> **Remember less, learn more.**

------------------------------------------------------------------------

## H3：Transferability 比单纯的 Failure Severity 更重要

一个造成很多 wasted steps 的失败，不一定值得长期保存。

真正有价值的是能够抽象出：

> "以后其他任务也可能用到的 planning constraint"。

------------------------------------------------------------------------

# 5. 方法数学定义

对于第 (i) 个失败轨迹，定义：

$$
f_i=(g_i,\tau_i,e_i),
$$

其中：

-   (g_i)：当前任务目标；
-   (`\tau`{=tex}\_i)：完整交互轨迹；
-   (e_i)：LLM 对失败原因的文本诊断。

轨迹写为：

$$
\tau_i=
(s_0,a_0,s_1,a_1,\ldots,s_T).
$$

我们为每个失败定义一个 **Failure Learning Utility**：

$$
U(f_i)
=
\alpha N(f_i)
+
\beta T(f_i)
+
\gamma R(f_i)
-
\delta D(f_i).
$$

其中四项分别表示：

1.  Novelty；
2.  Transferability；
3.  Repeatability；
4.  Duplication Penalty。

------------------------------------------------------------------------

## 5.1 Novelty：这个错误新不新？

设当前已有 Memory 为 (M)，文本 embedding 函数为 (E(`\cdot`{=tex}))。

定义：

$$
N(f_i)
=
1-
\max_{m\in M}
\operatorname{sim}
\left(
E(e_i),E(m)
\right).
$$

如果这个错误和已有 memory 很像：

$$
N(f_i)\approx 0.
$$

如果是以前没见过的新 failure：

$$
N(f_i)\approx 1.
$$

------------------------------------------------------------------------

## 5.2 Transferability：能不能迁移到未来任务？

定义：

$$
T(f_i)
=
P_{\text{LLM}}
\left(
\text{该失败包含可迁移的 planning rule}
\mid f_i
\right).
$$

实际实现时不一定需要真正取得 calibrated probability。

可以要求 LLM 输出：

$$
r_i\in\{1,2,3,4,5\},
$$

再归一化：

$$
T(f_i)=\frac{r_i-1}{4}.
$$

例如：

**Failure A**

> 把物体放进冰箱前忘记打开冰箱。

可以抽象成：

> 在将物体放入封闭容器之前，必须先确认容器处于打开状态。

Transferability 高。

而：

> 在这个特定房间里先去了 shelf 2，而正确物体恰好在 shelf 3。

Transferability 较低。

------------------------------------------------------------------------

## 5.3 Repeatability：这种错误是否反复出现？

将近期 failures 聚类。

设 (C(f_i)) 为包含 (f_i) 的 failure cluster。

定义：

$$
R(f_i)
=
\frac{|C(f_i)|}
{|F_{\text{recent}}|}.
$$

如果某类错误反复发生，它更值得形成 generalized rule。

------------------------------------------------------------------------

## 5.4 Duplication Penalty

定义：

$$
D(f_i)
=
\max_{m\in M}
\operatorname{sim}
\left(
E(e_i),E(m)
\right).
$$

它显式惩罚：

> 已经有非常相似 lesson 的 failure。

------------------------------------------------------------------------

## 5.5 Failure Selection

最终：

$$
z_i=
\mathbf{1}
\left[
U(f_i)>\tau
\right].
$$

只保留：

$$
F^*
=
\{f_i\mid z_i=1\}.
$$

然后再做 MNL-style clustering：

$$
F^*
\rightarrow
\{C_1,C_2,\ldots,C_K\}.
$$

每个 cluster 通过 LLM abstraction：

$$
m_j=A(C_j),
$$

得到 generalized mistake note。

最后更新：

$$
M_{t+1}
=
M_t\cup\{m_1,\ldots,m_K\}.
$$

------------------------------------------------------------------------

# 6. 数据集与模型

## 数据集：ALFWorld

建议只使用 **TextWorld / textual ALFWorld**。

典型任务包括：

-   Pick & Place；
-   Clean & Place；
-   Heat & Place；
-   Cool & Place。

例如：

> Clean the apple and put it in the fridge.

Agent 需要完成：

$$
\text{Find Apple}
\rightarrow
\text{Take Apple}
\rightarrow
\text{Go to Sink}
\rightarrow
\text{Clean Apple}
\rightarrow
\text{Go to Fridge}
\rightarrow
\text{Open Fridge}
\rightarrow
\text{Put Apple}.
$$

这非常适合研究 long-horizon planning failure。

### 第一版不要全部任务类型都做

建议：

$$
\boxed{
\text{Pick}
+
\text{Clean}
+
\text{Heat}
+
\text{Cool}
}
$$

这样还能研究跨任务经验迁移。

------------------------------------------------------------------------

## 模型

主模型：

**Qwen3-4B-Instruct-2507**

原因：

-   开源；
-   规模可控；
-   AdaMEM 公开 ALFWorld 配置支持该模型；
-   能和最新工作形成较好的 baseline 对齐。

如果算力足够，再加：

**Qwen3-8B**

作为 robustness experiment。

------------------------------------------------------------------------

# 7. Baselines

## B0 --- No Memory

每个任务完全独立：

$$
M=\varnothing.
$$

------------------------------------------------------------------------

## B1 --- All-Failure Memory

所有 failure 都进入 abstraction。

它是检验"selection 是否有意义"的最直接 baseline。

------------------------------------------------------------------------

## B2 --- Random-(K)

假设我们最终选择了 (K) 个 failures。

Baseline 随机选择同样数量：

$$
|F_{\text{random}}|
=
|F_{\text{ours}}|.
$$

这样可以排除：

> Ours 只是因为 Memory 更小。

------------------------------------------------------------------------

## B3 --- ReasoningBank-style Memory

使用成功/失败 trajectory 形成 reasoning memory。

------------------------------------------------------------------------

## B4 --- AdaMEM

这是重要的 2026 baseline：

-   ALFWorld；
-   开源代码；
-   Qwen3-4B 配置。

------------------------------------------------------------------------

## B5 --- MNL-port

将 MNL 的：

$$
\text{Failure}
\rightarrow
\text{Cluster}
\rightarrow
\text{Mistake Note}
$$

移植到 ALFWorld。

------------------------------------------------------------------------

## Ours

$$
\boxed{
\text{Failure}
\rightarrow
\text{Selection}
\rightarrow
\text{Cluster}
\rightarrow
\text{Mistake Note}
}
$$

最重要的 controlled comparison 是：

$$
\boxed{
\text{MNL-port}
\quad\text{vs}\quad
\text{MNL-port + Our Failure Selection}
}
$$

其他所有组件尽量完全一致。

------------------------------------------------------------------------

# 8. 完整实验流程

## Stage 0：先验证 ALFWorld Pipeline

运行：

$$
\text{ALFWorld}
+
\text{Qwen3-4B}
+
\text{No Memory Agent}.
$$

检查：

-   action parsing；
-   environment transition；
-   success/failure；
-   trajectory logging；
-   token statistics。

如果成功率接近 0% 或 100%，需要调整任务难度。

------------------------------------------------------------------------

## Stage 1：收集失败轨迹

运行：

$$
\mathcal{T}_{exp}
=
\{T_1,T_2,\ldots,T_N\}.
$$

对于每个失败保存：

$$
(g_i,\tau_i,r_i,\text{feedback}_i).
$$

------------------------------------------------------------------------

## Stage 2：Failure Diagnosis

让 frozen LLM 对每个 failure 输出：

1.  immediate cause；
2.  planning mistake；
3.  reusable lesson。

记作：

$$
e_i=D_\theta(f_i).
$$

------------------------------------------------------------------------

## Stage 3：Failure Scoring

计算：

$$
N(f_i),
\quad
T(f_i),
\quad
R(f_i),
\quad
D(f_i).
$$

然后：

$$
U(f_i)
=
\alpha N(f_i)
+
\beta T(f_i)
+
\gamma R(f_i)
-
\delta D(f_i).
$$

------------------------------------------------------------------------

## Stage 4：Selection

$$
F^*
=
\{
f_i:U(f_i)>\tau
\}.
$$

------------------------------------------------------------------------

## Stage 5：Memory Abstraction

对 selected failures 聚类：

$$
F^*
\rightarrow
C_1,\ldots,C_K.
$$

然后：

$$
m_j=A(C_j).
$$

得到 Memory：

$$
M=\{m_1,\ldots,m_K\}.
$$

------------------------------------------------------------------------

## Stage 6：新任务 Retrieval

对于新任务 (T)，检索：

$$
R_T
=
\operatorname{TopK}
\left(
E(T),E(M)
\right).
$$

最终 prompt：

$$
P_T=
[
\text{Goal};
\text{Observation};
\text{Retrieved Lessons}
].
$$

Agent 再进行规划。

------------------------------------------------------------------------

# 9. 三个核心实验

## Experiment A1：Selective Failure 是否优于 All Failure？

比较：

-   No Memory；
-   All Failure；
-   Random-(K)；
-   MNL-port；
-   Ours。

主要指标：

$$
SR
=
\frac{
N_{\text{success}}
}{
N_{\text{total}}
}.
$$

同时报告：

$$
\text{Memory Size},
$$

$$
\text{Memory Tokens},
$$

$$
\text{Average Steps},
$$

$$
\text{Inference Tokens}.
$$

最理想结果：

$$
SR_{\text{ours}}
\ge
SR_{\text{MNL-port}},
$$

但：

$$
|M_{\text{ours}}|
\ll
|M_{\text{MNL-port}}|.
$$

------------------------------------------------------------------------

## Experiment A2：到底什么 Failure 值得学习？

对 utility 做 ablation：

$$
U=N,
$$

$$
U=T,
$$

$$
U=R,
$$

$$
U=N+T,
$$

以及完整：

$$
U=N+T+R-D.
$$

回答：

> Novelty、Transferability、Repeatability 中到底谁最重要？

------------------------------------------------------------------------

## Experiment A3：Cross-Task Transfer

设任务类型：

$$
\mathcal C=
\{
\text{Pick},
\text{Clean},
\text{Heat},
\text{Cool}
\}.
$$

定义：

$$
G_{ij}
=
SR(T_j\mid M_i)
-
SR(T_j\mid \varnothing).
$$

其中：

-   (M_i)：从第 (i) 类任务学到的 Memory；
-   (T_j)：第 (j) 类测试任务。

最终得到 transfer matrix。

这个实验可以回答：

> Clean 任务学到的规则是否能帮助 Heat 任务？

以及：

> 哪些错误是真正 domain-general 的 household planning knowledge？

------------------------------------------------------------------------

# 10. Expected Figures

## Figure A：Success Rate vs Memory Size

横轴：

$$
|M|
$$

或 Memory Tokens。

纵轴：

$$
SR.
$$

希望 Ours 位于：

> 更左、更上。

也就是：

> **更少 Memory，更高性能。**

------------------------------------------------------------------------

## Figure B：Continual Learning Curve

横轴：

$$
\text{Number of Experience Tasks Seen}.
$$

纵轴：

$$
\text{Held-out Success Rate}.
$$

观察随着 Agent 经历更多任务：

$$
SR(t)
$$

是否逐渐提升。

------------------------------------------------------------------------

## Figure C：Cross-Task Transfer Heatmap

绘制：

$$
G_{ij}.
$$

这是 presentation 中很有研究味的一张图。

------------------------------------------------------------------------

# 11. 工作量与风险

### 工作量

**中等。**

主要工程：

-   ALFWorld；
-   Agent loop；
-   trajectory logging；
-   failure diagnosis；
-   clustering；
-   retrieval；
-   evaluation。

不需要训练主 LLM。

### 最大风险

Failure Utility 可能过于依赖 LLM judge。

### Fallback

使用完全可解释的：

$$
U(f_i)
=
\alpha N(f_i)
+
\beta R(f_i).
$$

这样甚至可以作为一个很强的 ablation。

------------------------------------------------------------------------

------------------------------------------------------------------------

# 方向二：基于 Planning Utility 的 World Model Selective Foresight

# 1. 建议题目

**When Should an LLM Agent Trust Its Imagination? Planning-Utility-Gated
Foresight for Household Task Planning**

中文：

**LLM Agent 什么时候应该相信自己的"想象"？面向家庭任务规划的
Planning-Utility-Gated World Model Foresight**

更正式一点：

**基于规划效用门控的世界模型辅助家庭任务规划**

------------------------------------------------------------------------

# 2. 核心研究问题

在状态 (h_t) 下，Agent 准备执行：

$$
a_t.
$$

World Model 先预测：

$$
\hat{o}_{t+1}
=
W_\phi(h_t,a_t).
$$

Planner 可以在真正执行前看到这个 imagined future。

现有工作已经发现：

> World Model 的错误预测可能伤害 Agent。

因此 WorldEvolver 等工作开始做 Selective Foresight。

但我们进一步问：

$$
\boxed{
\text{应该因为预测“看起来准确”而使用它，}
\quad
\text{还是因为预测“真的能帮助决策”而使用它？}
}
$$

------------------------------------------------------------------------

# 3. 与最新工作的关系

## 3.1 COMAP

**COMAP: Co-Evolving World Models and Agent Policies for LLM Agents**

核心思想是：

World Model 和 Agent Policy 不应该彼此独立。

大致流程：

$$
(s_t,a_t)
\rightarrow
\hat{o}_{t+1}
\rightarrow
\text{Future-Aware Reflection}
\rightarrow
a_t'
\rightarrow
o_{t+1}.
$$

然后根据：

$$
(\hat{o}_{t+1},o_{t+1})
$$

继续改善 World Model。

COMAP 已经在 embodied planning 等环境中使用 Qwen3 系列模型。

------------------------------------------------------------------------

## 3.2 WorldEvolver

**Self-Evolving World Models for LLM Agent Planning**

WorldEvolver 是这个项目最重要的 baseline。

它包含：

1.  Episodic Memory；
2.  Semantic Memory；
3.  Selective Foresight。

它发现：

> 不可靠的 imagined future 可能降低 downstream planning performance。

因此会根据 prediction confidence / reliability 决定是否使用 foresight。

------------------------------------------------------------------------

# 4. Research Gap

WorldEvolver 主要关心：

$$
C_t
=
P(
\hat{o}_{t+1}
\text{ is correct}
).
$$

然后：

$$
C_t>\tau
\Rightarrow
\text{use foresight}.
$$

但我们认为：

$$
\boxed{
\text{Prediction Correctness}
\neq
\text{Planning Utility}
}
$$

定义：

$$
C(\hat{o})
=
P(
\hat{o}_{t+1}
\approx
o_{t+1}
),
$$

而真正关心的是：

$$
U(\hat{o})
=
P(
\text{使用 }\hat{o}_{t+1}
\text{ 后 Planner 做出更好的决策}
).
$$

两者不一定相同。

------------------------------------------------------------------------

# 5. 一个具体例子

假设任务：

> Put the apple in the fridge.

World Model Prediction A：

> You will move toward the fridge. The fridge may still be closed.

这个预测可能并不完整，confidence 也未必最高。

但是它提醒 planner：

> fridge 可能还没打开。

因此对下一步 action selection 很有帮助。

另一个 Prediction B：

> You will be near the fridge and the apple will eventually be stored.

语言非常合理，模型 confidence 很高。

但它没有暴露关键 precondition：

> 必须先 open fridge。

所以：

$$
C(B)>C(A)
$$

并不意味着：

$$
U(B)>U(A).
$$

------------------------------------------------------------------------

# 6. Hypotheses

## H1：Confidence 与 Planning Utility 不完全一致

$$
\rho(C,U)<1.
$$

我们预计存在：

### High-confidence harmful prediction

$$
C_t\text{ high},
\qquad
\Delta_t<0.
$$

以及：

### Low-confidence helpful prediction

$$
C_t\text{ low},
\qquad
\Delta_t>0.
$$

------------------------------------------------------------------------

## H2：Utility Gating 优于 Always Foresight

$$
SR_{\text{utility}}
>
SR_{\text{always}}.
$$

------------------------------------------------------------------------

## H3：Utility Gating 优于 Confidence Gating

最重要的 hypothesis：

$$
SR_{\text{utility}}
>
SR_{\text{confidence}}.
$$

并且在相近 compute budget 下成立。

------------------------------------------------------------------------

# 7. 方法数学定义

设当前 interaction history：

$$
h_t=
(o_0,a_0,o_1,a_1,\ldots,o_t).
$$

Base Planner 直接产生：

$$
a_t^{(0)}
=
\pi_\theta(h_t).
$$

World Model 对 candidate action 预测：

$$
\hat{o}_{t+1}^{(a)}
=
W_\phi(h_t,a).
$$

Planner 看到 foresight 后产生：

$$
a_t^{(W)}
=
\pi_\theta
(
h_t,
\hat{o}_{t+1}
).
$$

------------------------------------------------------------------------

# 8. Confidence-Gated Baseline

World Model 输出 confidence：

$$
C_t
=
C_\psi
(
h_t,
a_t,
\hat{o}_{t+1}
).
$$

Confidence gate：

$$
g_t^{\text{conf}}
=
\mathbf{1}
[
C_t>\tau_c
].
$$

如果：

$$
g_t^{\text{conf}}=1,
$$

则使用 world-model foresight。

否则忽略。

------------------------------------------------------------------------

# 9. 我们的方法：Planning-Utility Gate

定义 foresight 的真正 planning gain：

$$
\Delta_t
=
V
(
h_t,
a_t^{(W)}
)
-
V
(
h_t,
a_t^{(0)}
).
$$

其中：

-   (a_t\^{(0)})：不使用 World Model 时的 action；
-   (a_t\^{(W)})：使用 World Model 后的 action；
-   (V(h,a))：从当前状态执行 action 后的 expected planning value。

理想情况下：

$$
g_t^*
=
\mathbf{1}
[
\Delta_t>0
].
$$

这是 **Oracle Utility Gate**。

但真实 test time 时不知道 (`\Delta`{=tex}\_t)。

因此学习/估计：

$$
\hat{\Delta}_t
=
f_\psi(x_t).
$$

最终：

$$
g_t^{\text{util}}
=
\mathbf{1}
[
\hat{\Delta}_t>0
].
$$

Agent 执行：

$$
a_t=
\begin{cases}
a_t^{(W)}, & g_t^{\text{util}}=1,\\
a_t^{(0)}, & g_t^{\text{util}}=0.
\end{cases}
$$

------------------------------------------------------------------------

# 10. Utility Estimator 的输入

定义 feature：

$$
x_t=
[
C_t,
D_t,
A_t,
L_t,
S_t
].
$$

可以包含：

### World Model Confidence

$$
C_t.
$$

### Action Change

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

如果 World Model 根本没有改变 planner decision，那么它可能没有多少实际
utility。

### Action Ambiguity

从 base planner 独立 sample (K) 次：

$$
a_t^{(1)},\ldots,a_t^{(K)}.
$$

定义：

$$
A_t
=
1-
\frac{
\max_a
\sum_{k=1}^{K}
\mathbf{1}[a_t^{(k)}=a]
}{
K
}.
$$

如果所有 sample 都选择同一个 action：

$$
A_t\approx0.
$$

说明 decision 很明确。

如果意见分歧：

$$
A_t\rightarrow1.
$$

World Model 在这种 state 上可能更有价值。

### Trajectory Length

$$
L_t=t.
$$

### Retrieved Transition Similarity

如果有 episodic memory：

$$
S_t
=
\max_{m\in M}
\operatorname{sim}
(
E(h_t,a_t),
E(m)
).
$$

------------------------------------------------------------------------

# 11. Utility Estimator

最简单可以用 Logistic Regression：

$$
\hat U_t
=
\sigma
(
w^\top x_t+b
).
$$

训练 label：

$$
y_t=
\mathbf{1}
[
\Delta_t>0
].
$$

因此优化：

$$
\mathcal L
=
-
\sum_t
\left[
y_t\log\hat U_t
+
(1-y_t)
\log(1-\hat U_t)
\right].
$$

注意：

> 我们的 research contribution 不是 Logistic Regression。

真正的贡献是把 gating target 从：

$$
\text{Prediction Correctness}
$$

改成：

$$
\boxed{\text{Planning Utility}}.
$$

------------------------------------------------------------------------

# 12. Dataset

同样使用：

## ALFWorld

好处是：

-   WorldEvolver 使用 ALFWorld；
-   AdaMEM 也使用 ALFWorld；
-   如果团队先探索两个方向，可以共享 environment infrastructure；
-   household task 的 action / state / goal 对 LLM 很容易理解。

------------------------------------------------------------------------

# 13. 模型

推荐：

**Qwen3-4B**

Planner 与 World Model 第一版甚至可以使用同一个 backbone、不同 prompt。

例如：

$$
\pi_\theta
=
\text{Qwen3-4B Planner Prompt},
$$

$$
W_\phi
=
\text{Qwen3-4B World-Model Prompt}.
$$

这样不需要额外训练大型模型。

------------------------------------------------------------------------

# 14. Baselines

## B0 --- No Foresight / ReAct

$$
a_t=\pi(h_t).
$$

------------------------------------------------------------------------

## B1 --- Always Foresight

所有 world-model prediction 都提供给 planner：

$$
g_t=1.
$$

------------------------------------------------------------------------

## B2 --- Random Gate

以和 Ours 相同的平均使用比例随机启用 foresight。

例如 Ours：

$$
P(g_t=1)=0.42,
$$

Random baseline 也保持约：

$$
P(g_t=1)=0.42.
$$

这样控制 compute。

------------------------------------------------------------------------

## B3 --- Confidence-Gated Foresight

$$
g_t
=
\mathbf{1}
[
C_t>\tau_c
].
$$

这是**最重要 baseline**。

------------------------------------------------------------------------

## B4 --- COMAP-style Agent

如果公开实现可顺利复现，则加入。

------------------------------------------------------------------------

## B5 --- WorldEvolver / Selective Foresight

这是和我们最新、最直接的 baseline。

------------------------------------------------------------------------

## Ours --- Planning-Utility Gate

最重要 controlled comparison：

$$
\boxed{
\text{Confidence Gate}
\quad
\text{vs}
\quad
\text{Planning Utility Gate}
}
$$

必须尽可能保持：

$$
W_\phi,
\quad
\pi_\theta,
\quad
\text{Prompt},
\quad
\text{Retrieval}
$$

全部相同。

只改变：

$$
\boxed{\text{Gating Criterion}}.
$$

------------------------------------------------------------------------

# 15. 完整实验流程

## Stage 0：ALFWorld Base Agent

先实现：

$$
\text{ALFWorld}
+
\text{Qwen3-4B}
+
\text{ReAct}.
$$

得到 baseline success rate。

------------------------------------------------------------------------

## Stage 1：World Model

对于：

$$
(h_t,a_t),
$$

预测：

$$
\hat{o}_{t+1}
=
W_\phi(h_t,a_t).
$$

真正执行后得到：

$$
o_{t+1}.
$$

保存：

$$
(h_t,a_t,\hat{o}_{t+1},o_{t+1}).
$$

------------------------------------------------------------------------

## Stage 2：Prediction Accuracy

计算：

$$
C_t^{\text{true}}
=
\operatorname{sim}
(
\hat{o}_{t+1},
o_{t+1}
).
$$

如果可以将 ALFWorld observation 解析成 structured facts，则更推荐计算：

$$
\text{Precision},
\quad
\text{Recall},
\quad
F_1.
$$

最终具体指标应尽量和复现的 WorldEvolver / COMAP 设置保持一致。

------------------------------------------------------------------------

## Stage 3：构造 Counterfactual Planning Utility

在同一个 (h_t)：

### 不使用 World Model

$$
a_t^{(0)}
=
\pi(h_t).
$$

### 使用 World Model

$$
a_t^{(W)}
=
\pi(h_t,\hat{o}_{t+1}).
$$

分别做短 rollout 或 value estimation：

$$
V^{(0)}
=
V(h_t,a_t^{(0)}),
$$

$$
V^{(W)}
=
V(h_t,a_t^{(W)}).
$$

于是：

$$
\Delta_t
=
V^{(W)}-V^{(0)}.
$$

------------------------------------------------------------------------

## Stage 4：训练轻量 Utility Estimator

构造：

$$
(x_t,y_t),
$$

其中：

$$
y_t
=
\mathbf{1}
[
\Delta_t>0
].
$$

训练：

$$
f_\psi(x_t).
$$

注意 calibration set 和 evaluation set 必须分开。

------------------------------------------------------------------------

## Stage 5：Test-Time Utility Gating

每一步：

1.  Base Planner 生成 action；
2.  World Model 生成 foresight；
3.  Confidence estimator 得到 (C_t)；
4.  Utility estimator 得到 (`\hat{\Delta}`{=tex}\_t) 或
    (`\hat `{=tex}U_t)；
5.  Gate 决定是否使用 foresight；
6.  Planner 执行最终 action；
7.  Environment 返回真实 observation。

------------------------------------------------------------------------

# 16. 三个核心实验

# Experiment B1：Confidence 和 Planning Utility 到底是不是一回事？

这是整个项目的 **Go / No-Go Experiment**。

对每个 state 计算：

$$
C_t
$$

和：

$$
\Delta_t.
$$

计算：

$$
\rho
=
\operatorname{Corr}
(
C_t,\Delta_t
).
$$

同时分成四类：

                      Helpful：(`\Delta`{=tex}\_t\>0)   Harmful：(`\Delta`{=tex}\_t\<0)
  ----------------- --------------------------------- ---------------------------------
  High Confidence                            正常情况                      **危险情况**
  Low Confidence                     **被错过的机会**                          正确拒绝

真正重要的是两个 off-diagonal：

$$
C_t\text{ high},
\quad
\Delta_t<0,
$$

以及：

$$
C_t\text{ low},
\quad
\Delta_t>0.
$$

如果这两类大量存在：

> Planning Utility 和 Prediction Confidence 确实是不同信号。

项目继续。

如果几乎不存在：

> 这个方向的 research gap 不够强。

可以及时停止。

------------------------------------------------------------------------

# Experiment B2：不同 Gate 的实际 Planning Performance

比较：

-   No Foresight；
-   Always Foresight；
-   Random Gate；
-   Confidence Gate；
-   Utility Gate；
-   Oracle Utility Gate。

主要指标：

$$
SR.
$$

另外：

$$
\text{Average Steps},
$$

$$
\text{Foresight Usage Rate},
$$

其中：

$$
\text{Foresight Usage Rate}
=
\frac{
N_{\text{foresight steps}}
}{
N_{\text{total steps}}
}.
$$

还要记录：

$$
\text{Total Input Tokens}
$$

和：

$$
\text{World Model Calls}.
$$

------------------------------------------------------------------------

# Experiment B3：什么情况下 World Model 最值得用？

按照 **Action Ambiguity** 分组：

$$
A_t\in
\{
\text{Low},
\text{Medium},
\text{High}
\}.
$$

计算：

$$
Gain(A)
=
SR_{\text{Utility Gate}}(A)
-
SR_{\text{No Foresight}}(A).
$$

我们希望发现：

$$
Gain(\text{High Ambiguity})
>
Gain(\text{Low Ambiguity}).
$$

即：

> World Model 不应该每一步都用，而应该主要用在真正困难、决策不确定的
> planning state。

------------------------------------------------------------------------

# 17. Expected Figures

## Figure A：Prediction Confidence vs Planning Gain

横轴：

$$
C_t.
$$

纵轴：

$$
\Delta_t.
$$

重点观察右下角：

$$
C_t\text{ high},
\qquad
\Delta_t<0.
$$

如果右下角存在大量点，这是最直接的 research motivation。

------------------------------------------------------------------------

## Figure B：Success--Compute Pareto Frontier

横轴：

$$
\text{Average Foresight Tokens / Calls}.
$$

纵轴：

$$
SR.
$$

画：

-   Always；
-   Random；
-   Confidence；
-   Utility。

希望 Ours 位于：

> 更左、更上。

------------------------------------------------------------------------

## Figure C：Utility by Decision Ambiguity

横轴：

$$
\text{Action Ambiguity}.
$$

纵轴：

$$
\text{Planning Gain}.
$$

希望随着 ambiguity 增加，World Model 的 utility 也增加。

------------------------------------------------------------------------

# 18. 最重要的早期实验

这个方向不要一上来完整复现 COMAP。

第一周先做：

$$
\boxed{
C_t
\quad\text{vs}\quad
\Delta_t
}
$$

只需要采集大约：

$$
100\sim300
$$

个有代表性的 decision points。

如果：

$$
\exists
\text{大量 }
(C_t\text{ high},\Delta_t<0)
$$

和：

$$
(C_t\text{ low},\Delta_t>0),
$$

那么项目非常值得继续。

然后再实现完整 Utility Gate。

------------------------------------------------------------------------

# 19. 风险

## Risk 1：Confidence 和 Utility 高度相关

如果：

$$
\rho(C,\Delta)\approx1,
$$

我们的 gap 就很弱。

所以必须最早验证。

------------------------------------------------------------------------

## Risk 2：World Model 本身完全没有帮助

如果：

$$
SR_{\text{Always}}
\le
SR_{\text{No Foresight}},
$$

也不一定立即失败。

先看 Oracle：

$$
g_t^*
=
\mathbf{1}
[
\Delta_t>0
].
$$

如果：

$$
SR_{\text{Oracle}}
\gg
SR_{\text{No Foresight}},
$$

说明：

> World Model 有价值，只是需要正确选择使用时机。

项目仍然成立。

如果：

$$
SR_{\text{Oracle}}
\approx
SR_{\text{No Foresight}},
$$

则说明当前 world model 没有足够 useful information。

建议停止这个方向。

------------------------------------------------------------------------

# 20. 两个方向最终比较

  --------------------------------------------------------------------------
  对比项                  方向一：Selective       方向二：Planning-Utility
                          Failure Learning        World Model
  ----------------------- ----------------------- --------------------------
  应用                    家庭任务持续学习        家庭任务规划

  Dataset                 ALFWorld                ALFWorld

  Backbone                Qwen3-4B                Qwen3-4B

  2026 最新工作衔接       AdaMEM / AgeMem / MNL   COMAP / WorldEvolver

  最直接 baseline         MNL-port                WorldEvolver Confidence
                                                  Gate

  核心变量                Failure Selection       Foresight Selection

  是否训练主 LLM          否                      否

  是否需要小模型          否                      可选 Logistic Regression

  Continual Learning 味道 **强**                  中

  Planning 味道           强                      **很强**

  Agent 味道              **很强**                **很强**

  实验复杂度              中                      中高

  风险                    中低                    中高

  Novelty                 高                      **更高**
  --------------------------------------------------------------------------

------------------------------------------------------------------------

# 21. 当前建议

## 如果希望课程项目稳妥

选择：

$$
\boxed{
\text{方向一：Selective Failure Learning}
}
$$

因为它最容易形成严格 controlled comparison：

$$
\text{MNL-port}
$$

对比：

$$
\text{MNL-port + Failure Selection}.
$$

实验失败风险较低。

------------------------------------------------------------------------

## 如果希望更像一篇真正的 Planning Research Paper

选择：

$$
\boxed{
\text{方向二：Planning-Utility-Gated World Model}
}
$$

它的核心命题更加有研究价值：

$$
\boxed{
\text{Prediction Confidence}
\neq
\text{Planning Utility}
}
$$

而且直接接在 WorldEvolver 的 Selective Foresight 后面。

但是一定先做：

$$
C_t
\quad\text{vs}\quad
\Delta_t
$$

这个 Go / No-Go Experiment。

------------------------------------------------------------------------

# 22. 参考文献

1.  Zhang, Y., Li, Y., Payani, A., & Wang, L. **AdaMEM: Test-Time
    Adaptive Memory for Language Agents.** 2026. arXiv:2606.05684.

2.  Yu et al. **Agentic Memory: Learning Unified Long-Term and
    Short-Term Memory Management for Large Language Model Agents.** ACL
    2026.

3.  Su, X., Zhang, Y., Luo, H., Liu, X., & Huang, L. **Mistake Notebook
    Learning: Batch-Clustered Failures for Training-Free Agent
    Adaptation.** Findings of ACL 2026.

4.  **ReasoningBank: Scaling Agent Self-Evolving with Reasoning
    Memory.** Google Research.

5.  Liu, Y., Wang, J., Wang, H., & Li, W. **COMAP: Co-Evolving World
    Models and Agent Policies for LLM Agents.** 2026. arXiv:2606.02372.

6.  Zhang, X., Zhang, W., Ng, S.-K., & Deng, Y. **Self-Evolving World
    Models for LLM Agent Planning.** 2026. arXiv:2606.30639.

7.  Shridhar et al. **ALFWorld: Aligning Text and Embodied Environments
    for Interactive Learning.** ICLR 2021.

------------------------------------------------------------------------

# 23. 官方资源

-   AdaMEM：`https://github.com/yunx-z/AdaMEM`
-   COMAP：`https://github.com/loyiv/CoMAP`
-   ALFWorld：`https://github.com/alfworld/alfworld`
-   ReasoningBank：`https://github.com/google-research/reasoning-bank`
-   MNL：`https://aclanthology.org/2026.findings-acl.719/`

------------------------------------------------------------------------

# 24. Baseline 比较时必须遵守的规则

最终报告中应严格区分：

### A. Exact Direct Reproduction

满足：

$$
\text{Dataset}
+
\text{Split}
+
\text{Backbone}
+
\text{Evaluation}
$$

全部一致。

这类结果才最适合直接说：

> Ours outperforms X。

### B. Reimplemented / Ported Baseline

例如：

> MNL 原论文没有以 ALFWorld 为核心 benchmark，我们将其方法移植到
> ALFWorld。

此时应该写：

> Under our controlled ALFWorld setup, our method outperforms our
> reproduction of MNL.

### C. Literature Number

如果只是引用论文中的原始数字，而实验设置不同，就不能和我们的数字直接声称
superiority。

应单独标记：

> Reported result in the original paper.

这一点对于最终 project report 的实验严谨性非常重要。

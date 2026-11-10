# 实验部分重设计：先基础实验，再消融实验

更新：2026-11-09。依据当前 report.tex 和两份逐页方案（原文件及 _0 版）。本方案单独输出，保留原方案与 PPT。

## 1. 这部分究竟要讲清楚什么

讲解主线：**有效吗 → 相比其他方法如何 → 哪些任务有效 → 收益是否来自修复接口 → 原因与步骤分别起什么作用 → 记忆或直接执行是否更好。**

“基础实验”指冻结方法的主评估，不是前面 WHEN/WHAT 的开发探针。实验结果统一以 fresh600 为主；dev460 只在 setup 中解释为选型集，避免听众把不同数据集上的绝对分数当成方法改进。

原方案的问题不是单纯页序，而是每页常常直接报结论，没有先交代比较对象与要排除的解释。新版每页固定采用：**一个问题 → 原表截图 → 两三条读表结论 → 一句转场**。

删去独立的“What Do the Controls Test?”主讲页，把控制组的作用放在主结果页读表时说明。对齐基线则必须先介绍在本实验中的具体实现，再展示结果：背景页的相关工作概念不能代替实现说明。子目标漏斗与诊断类别匹配率移入备份，避免主线在消融后再切回相关性分析。

## 2. 建议页序

这里使用 E1–E8 作为实验模块编号，不对应当前 PPT 的绝对页码；E3 拆为 E3a / E3b 两页，共九页。E1 对应你目前的 Experimental Setup（第 14 页）；后续页面按实际内容插入或替换。

| 模块 | 英文标题 | 核心问题 | 报告原表 |
|---|---|---|---|
| E1 实验设置 | Experimental Setup | 用什么模型、任务和指标评估？ | Table 2，tab:protocol；可保留现有 setup 页 |
| E2 基础实验 1 | Does Repair Improve Planning? | 是否优于无干预及失败提示？ | Table 7，tab:main；统计依据 Table 8 |
| E3a 基线实现 | How Are the Baselines Implemented? | 在我们的实验中，何时调用、提供什么信息？ | 新建实现说明表，依据代码与报告 Aligned Baselines 段落 |
| E3b 基础实验 2 | How Does Repair Compare with Other Methods? | 效果和在线调用数如何？ | Table 13，tab:baselines |
| E4 基础实验 3 | Does Repair Help across Task Types? | 效果是否集中在少数任务？ | Table 10，tab:tasks |
| E5 消融实验 1 | Is the Gain from More Context or from Repair? | 输入相同，输出接口是否仍重要？ | Table 9，tab:ablation |
| E6 消融实验 2 | Which Parts of Repair Advice Matter? | 原因、步骤、组合分别如何？ | 同一张 Table 9，改变强调行 |
| E7 消融／诊断控制 | Should We Retain or Directly Execute the Advice? | 记忆与强制采用建议是否更好？ | Table 12，tab:followups |
| E8 总结与边界 | What Do the Experiments Establish? | 证据支持什么、不支持什么？ | 总结 E2–E7；局限来自 Discussion 与补充材料 |

建议基线实现约 1 分钟、主结果约 4 分钟、消融约 3 分钟，setup 与总结各约 1 分钟。不另加章节过渡页：E5 页眉切换到 Ablation Studies 即可。

## E1｜Experimental Setup

**目的：** 建立读结果所需的共同条件。可以保留当前第 14 页及六类任务图，只整理文案。

**English slide copy**

- ALFWorld: six task types; at most 30 steps per episode.
- Frozen models: Qwen3-4B-Instruct-2507 planner and Qwen3-14B WM (thinking off).
- Development: dev460, two runs per task, for method selection.
- Final evaluation: fresh600, 100 tasks per type, three runs per task per condition.
- SR: task completion. PR: subgoal progress.

**Takeaway:** The method is frozen before evaluation on fresh600.

**Footnote:** fresh600 contains previously unrun instances within the training scene distribution. Results use 600 task-level units per condition, with repetitions averaged before paired bootstrap sampling.

**截图与布局：** 本页可沿用已完成的 setup 页。若希望完全使用报告截图，截 Table 2（tab:protocol）整张表；无需再放重复配置文字。右侧六类任务图仅作环境解释，不承载实验结果。

**讲解与转场：** 后面的结果都在这套配置上比较。接下来先验证修复有没有用，再与其他指导方法比较。

## E2｜Does Repair Improve Planning?

**问题：** 使用 WM repair 是否提高成功率？收益是否超过“已经告诉 Planner 动作无效”这一干预？

**English slide copy**

- WM repair raises SR from 20.9% to 36.2% (+15.3 pp).
- It improves PR over failure notification by 4.2 pp.
- It meets the pre-specified PR non-inferiority criterion against rule cards.

**Takeaway:** Repair adds useful guidance beyond flagging an invalid action.

**Footnote:** fresh600; three runs per task. SR vs. none: 95% CI [12.7, 17.8] pp. PR vs. failure: [2.6, 5.7] pp. Both Holm-adjusted p < 0.001. Non-inferiority margin vs. rules: −2 PR points.

**直接截取：** Table 7（tab:main）整张表，保留 Condition、SR、PR 及全部七行。不要只保留 WM repair 行。Table 8 不与 Table 7 挤在同一页，主要统计量放脚注，完整检验表放备份。

**布局：** 上方最多三条短句；下方或左侧放原表，至少占内容区宽度的 65%。在原表外叠加细框，重点突出 No intervention、Failure only、WM repair 三行。规则与 Oracle 保留，但不把本页讲成所有方法逐行介绍。

**读表顺序：**

1. None → WM repair：回答整体有没有用，用 SR。
2. Failure only → WM repair：回答是否超越失败提示，用 PR；失败提示不是“没有新增信息”。
3. Rule cards / Oracle：提供显式规则与局部真实诊断的参照。SR 接近 Oracle 不代表诊断准确率接近 Oracle。

**转场：** “This establishes a benefit over our controls. How does repair compare with other guidance methods?”

## E3a｜How Are the Baselines Implemented?

**问题：** 这些名字在我们的实验里具体对应哪些操作？本页不介绍原论文的完整系统，也不先报性能。

**English slide copy**

- All methods use the same 4B planner, fresh600 tasks, and 30-step budget.
- WM inference and offline knowledge extraction use the same frozen 14B model.
- We vary the guidance mechanism, trigger, and knowledge source.

**Implementation table（直接放在 PPT 上）**

| Aligned baseline | Online procedure in our implementation | Variants / knowledge |
|---|---|---|
| WALL-E-style | WM judges each proposed environment action; predicted failure prompts feedback and planner revision (up to two revisions). | With or without learned rules; the judge does not receive the valid-action list. |
| WorldEvolver-style | WM forecasts the proposed action; only sufficiently confident forecasts are shown to the planner. | With or without episodic memory; the display threshold is calibrated to about 30% use. |
| ExpeL-style | Add 15 learned insights to the planner prompt. | Show them every step or only at the invalid-action gate; no online advisory-model call. |
| RPMS-style | At the invalid-action gate, provide action-specific rule cards and a state summary tracked from observations. | Hand-written rules plus tracked state; no online advisory-model call. |

**Takeaway:** The comparison changes how guidance is produced and delivered, under a shared evaluation setup.

**Footnote:** Aligned implementations, not full reproductions. Learned rules and insights use a separate 448-task pool, disjoint from fresh600. No model weights are updated.

**布局：** 两三条共享设置短句在上，四行实现表占主体；不要把四个方法做成四张单独的介绍页。版面紧张时，把开头三条压缩成一行：“Shared: 4B planner · frozen 14B WM / knowledge model · fresh600 · 30 steps”。表格按 E3b 读表顺序讲 WALL-E、WorldEvolver、ExpeL、RPMS。

**讲解顺序与关键实现细节（不上屏）：**

1. **WALL-E-style：先让 WM 判断，再决定是否让 Planner 修改。** 与我们的有效动作列表触发不同，这里由 WM 判断动作成败，判断时不提供合法动作列表；一次环境步骤最多允许两次修订，修订后可再次判断，因此每步可能多次调用 WM。规则变体将离线学到的规则放入 WM 判断提示。`check valid actions` 是协议例外，不走正常环境动作判断。
2. **WorldEvolver-style：先预测，再按置信度决定是否展示。** 置信度 gate 是“展示预测”的 gate，不能讲成“只在 30% 的步骤调用 WM”。其余步骤仍可能已经付出预测调用成本。这是解释后页 Calls 的关键。记忆变体为预测提供历史转移信息；它不等于修复消融中的“保留五条诊断”。
3. **ExpeL-style：把离线经验写进 Planner 的提示。** 15 条 insights 由模型从 Planner 的历史轨迹中提炼，每步展示和非法动作处展示是两个独立配置。在线不调用额外 WM，但 Planner 仍有推理开销，离线学习也有成本。
4. **RPMS-style：把显式规则和当前状态摘要交给 Planner。** 只在非法动作 gate 触发，提供与动作有关的手写规则及从观测历史追踪的 belief state；不是把环境隐藏真值状态直接交给 Planner。无在线 WM 调用，不等于没有计算或人工知识成本。

**实现简化（答疑用）：** WALL-E-style 使用一步判断与至多两次修订；规则学习采用两轮自然语言归纳，最终使用六条规则。ExpeL-style 不额外检索成功轨迹作为示例；RPMS-style 不使用 episodic memory，规则库采用本项目的 rule cards。其他方法的触发条件与信息访问并不完全相同，因此比较的是对齐系统配置，不能把结果解释为只改变触发器的因果实验。

**代码依据：** `preexperiments/react_study/agent.py` 中的 `walle`、`selective`、`expel`、`inv_expel`、`inv_rpms` 分支；`baselines_r6.py`；`learn_walle_rules.py`；`learn_expel_insights.py`；`calib_selective_r6.py`。上述路径均在 `alfworld-preexp-npu/` 下；实现与评估配置汇总于 `outputs/react_study/r6_baselines/README.md`。

**原表截图约定：** report.tex 的实现描述是正文段落，没有现成实现表，因此本页需要新做上述说明表。后面的性能页仍直接使用原报告 Table 13 截图，不重画结果。

**转场：** “These implementations differ in both guidance and online cost. We now compare their task performance and advisory calls.”

## E3b｜How Does Repair Compare with Other Methods?

**问题：** 在共享 Planner 和任务集的条件下，修复相对现有指导机制的效果、在线调用开销如何？

**English slide copy**

- Repair achieves higher SR than the tested WM-judging, forecasting, and learned-insight baselines.
- RPMS-style rules and tracked state remain competitive: 37.2% SR versus 36.2% for repair.
- Repair uses 5.3 online advisory calls per episode, versus 54.5 for WALL-E-style judging and 25.9 for WorldEvolver-style forecasting.

**Takeaway:** Repair offers effective guidance with fewer advisory calls than the tested judging and forecasting baselines.

**Footnote:** Aligned implementations, not full reproductions. Calls are online advisory-model calls per episode; offline knowledge-learning costs are excluded. Triggers and knowledge access differ across methods.

**直接截取：** Table 13（tab:baselines）整表，保留 Method、SR、PR、Calls、Tokens 及所有变体。不要删掉 RPMS 或 every-step ExpeL 等不方便讲解的结果。

**布局：** 表格占主体，右侧最多两个小注释：“SR: 36.2 vs. 37.2 (RPMS)”和“Calls: 5.3 vs. 54.5 / 25.9”。Tokens 保留但只作为补充，不强行同时讲四个指标。

**读表顺序：** 先看 SR，再看 PR，最后看 Calls。将结果与前页实现连起来：WALL-E 的反复判断、WorldEvolver 的先预测后筛选都会产生在线 WM 调用；ExpeL / RPMS 则主要把现成知识放进 Planner 提示。WALL-E 的 PR 48.2 与 repair 的 49.0 接近，因此不能说所有指标都大幅领先。RPMS 没有在线 WM 调用，不能声称 repair 在所有方法里最省。Calls 也不能直接等价为延迟或能耗。

**转场：** “The aggregate results are promising. Are the gains consistent across task types?”

## E4｜Does Repair Help across Task Types?

**问题：** 总体增益是否由少数任务拉高？哪些能力仍有明显不足？

**English slide copy**

- Repair has higher observed SR than no intervention in all six task types.
- It exceeds rule cards on four task types; rule cards lead on heating and two-object placement.
- Two-object placement remains difficult: 15.3% SR with repair, versus 24.0% with rules.

**Takeaway:** Gains span all six task types, but important task-specific weaknesses remain.

**Footnote:** fresh600; 100 tasks per type and three runs per task. Task-wise comparisons are descriptive, without corrected per-type significance claims.

**直接截取：** Table 10（tab:tasks）整张表。用细框强调 None 和 WM repair 列，再标出 heating / two-object 两行。保留 Rules、Oracle 列作为参照。

**讲解：** 不要逐行念六组数字。先扫全表说明“相对 None 六类均更高”，然后只讲一个反例：双物体任务仍明显落后于规则。

**转场：** “We have established effectiveness and its limits. Next, we isolate what makes the repair interface useful.”

## E5｜Is the Gain from More Context or from Repair?

**问题：** repair 是否只是因为 WM 看到了更多输入？

**控制说明（图上或口头）：** 等信息预测与修复使用相同 WM、Planner、非法动作触发条件和 WM 输入上下文；改变的是要求 WM 输出预测还是原因＋建议步骤。原始预测行仅作为背景参照，不属于“输入已匹配”的核心对比。

**English slide copy**

- Match the WM inputs and invalid-action trigger between prediction and repair.
- Change the requested output: next observation versus cause and first step.
- Repair reaches 49.0% PR, versus 44.9% for equal-input prediction (+4.1 pp).

**Takeaway:** The repair interface matters beyond the amount of input context.

**Footnote:** Repair minus equal-input prediction: 95% CI [2.5, 5.7] PR points; Holm-adjusted p < 0.001. fresh600, three runs per task.

**直接截取：** Table 9（tab:ablation）整表。重点框出 Prediction with repair inputs 和 Cause and first step 两行，强调 PR 列的 44.9 与 49.0。Next-observation prediction 的 42.4 可顺带解释“补充输入本身有帮助”，但不是本页最终结论。

**讲解提醒：** 原表最后一行叫 Cause and first step，它就是完整 WM repair。应当口头说明一次，避免观众以为是新方法。

**转场：** “With inputs controlled, repair still helps. Which part of that advice is responsible?”

## E6｜Which Parts of Repair Advice Matter?

**问题：** 有用的是解释原因、建议步骤，还是两者结合？

**控制说明：** Cause only、First step only、Cause and first step 使用相同的 WM 修复调用形式，改变的是展示给 Planner 的字段；Failure notice only 是不调用 WM 的参照组。

**English slide copy**

- Cause only does not significantly improve PR over a failure notice (45.6% vs. 44.8%).
- First-step advice reaches 47.0% PR; combining it with a cause reaches 49.0%.
- The full response has the highest observed PR among the tested formats.

**Takeaway:** A suggested step provides actionable guidance; the accompanying explanation adds value in this comparison.

**Footnote:** Cause vs. notice: +0.8 pp, 95% CI [−0.5, 2.1]. Step vs. notice: +2.2 [0.6, 3.8]; full vs. step: +2.0 [0.3, 3.6]. The latter two tests are secondary and uncorrected.

**直接截取：** 复用 E5 的同一张完整 Table 9 截图，不重新拼表。此页改为框出 Failure notice only、Cause only、First step only、Cause and first step，主要读 PR 列。两页重复表格是有意设计：第一遍检验“预测还是修复”，第二遍检验“修复的哪部分”。

**讲解提醒：** 原因单独不显著，不等于原因完全没有用；组合相对 step-only 的证据属于次要未校正比较，不与 E5 的主要检验混写。

**转场：** “The combined advice works best among these formats. Would keeping it in memory or forcing its execution help further?”

## E7｜Should We Retain or Directly Execute the Advice?

**问题：** 把诊断跨步骤保留，或者跳过 Planner 直接执行建议，是否比当前方法更好？

**English slide copy**

- Retaining the last five diagnoses does not significantly improve PR (47.9% vs. 49.0%).
- Directly executing the suggested step also gives no significant PR gain (49.2% vs. 49.0%).
- Neither modification improves the primary progress outcome reliably.

**Takeaway:** These variants provide no reliable PR gain over the tested local-advice design.

**Footnote:** PR contrasts vs. repair: memory −1.0 pp [−2.5, 0.4]; direct execution +0.2 [−1.4, 1.8]. Primary PR tests use Holm adjustment; SR comparisons are exploratory.

**直接截取：** Table 12（tab:followups）整张表，尤其保留最右侧 ΔPR 与 CI 列。两条区间均跨过 0，是本页核心证据，不要只截 SR / PR 数值。

**讲解提醒：** 表内 47.9 与 49.0 是已四舍五入的均值；对比 −1.0 来自未四舍五入估计，直接沿用报告值。Direct execution 改变了动作选择权，应称为后续诊断控制；它不等于让 14B 模型重新选择动作的 takeover。

## E8｜What Do the Experiments Establish?

**English slide copy**

- Effectiveness: repair improves SR over no intervention by 15.3 pp.
- Interface: with matched inputs, repair exceeds prediction by 4.1 PR points.
- Components: cause and first-step advice perform best together among the tested formats.
- Scope: valid-action access is required; explicit rules and stronger decision-makers remain competitive alternatives.

**Takeaway:** Evaluate world-model guidance by how it supports the planner’s next decision.

**Footnote:** One environment and model family; fresh600 is within the training scene distribution. A 14B planner alone reaches 59.1% SR; failure-step takeover reaches 49.0%.

**布局：** 不再重复大表。用三条“基础实验 / 接口消融 / 组件消融”结论加一条边界，完成实验叙事闭环。可并入最终 Conclusion。

## 3. 移到备份的内容

- **Development and freeze：** Table 6（tab:development）。用于解释 dev460 如何选型，不与 fresh600 结果并排当成提升曲线。
- **Primary statistical tests：** Table 8（tab:hypotheses）。E2 讲主要结论，答疑时展示完整置信区间与非劣检验。
- **Subgoal progress：** Table 11（tab:funnel）。描述性机制分析，不是严格消融。条件成功率不同于全体 episode 的成功率，不混成一个漏斗，也不据此宣称因果机制已被证明。
- **Capacity and takeover：** report_supplement.tex 的模型大小与动作接管对照。E8 保留一句关键局限，完整结果留答疑。
- **WHEN/WHAT 开发探针：** 留在前面的动机章节，不混进这组 fresh600 主评估。

## 4. “直接截图报告图表”的执行规则

当前 report.tex 正文有 13 个 table 环境，没有 figure 环境；这里应直接截取其编译后 PDF 的原表，不是截 .tex 源码，也不是把截图重画成柱状图。

截图清单按讲述顺序为：**Table 7 → Table 13 → Table 10 → Table 9（使用两次）→ Table 12**。Setup 可选 Table 2；备份使用 Table 6、8、11。这是 slides 的讲述顺序，无需修改报告表号。

每张截图保留表题、表头、全部行列和脚注；去掉周围无关正文。截图占幻灯片主体，避免沿用“大段 bullets + 底部小表”的布局。标注放在 PPT 上层，用细框或箭头指向关键行，不更改图片中的原始数字。Table 9 有不连续重点行时，保留整表并更换高亮，不剪切重组造成表格仿佛来自报告的误解。

建议从 PDF 以至少 300 dpi 导出裁剪区域；保留 PDF 原文件以便追溯。宽表（13、12）尽量占页面宽度的 80–90%，正文最多两三条。表格截图可先整表出现，再逐步显示高亮框。

**当前交付限制：** 仓库未发现 report.pdf，当前 PATH 中未找到 pdflatex、xelatex 或 tectonic。本次交付是重新设计的逐页方案、截图定位和逐字提取的 LaTeX 原表，不冒充已完成 PDF 截图。实际截图应从你最终编译的 report PDF 导出，以保证字号、表号和排版一致。

`output/experiment_redesign/report_table_sources/` 保存从当前 report.tex 直接提取的原表，未重写数据；定位清单包含当前行号和标签。它们是 LaTeX 源片段，不是图片，也不是完整可单独编译的文档。

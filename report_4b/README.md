# 4B 测量研究：阅读与交付导航

本目录整理我们已完成的 Qwen3-4B D0 开发期测量和 E 整局评估，回答“confidence 能否识别对决策有用的预测”。本版另纳入队友已复核的 Step 0c 和方向 B 离线结果，作为不同协议下的补充测量，不与本组 D0/E 合并。当前交付是课程报告草稿，整理于 2026-10-20；结论不依赖其他模型结果。

本目录包含实验答案。参加盲复验的读者应先按[盲复验说明](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/recheck_4b/README.md)完成并交回复验，再阅读本目录。

## 先读什么

1. [主报告](MINIMAL_REPORT_DRAFT.md)：先读摘要、第 4 节结果和第 6 节局限，再按需查看方法与讨论。
2. 下方四张图：快速查看动作与终局的差别、confidence 与准确性、整局成功率及成本。
3. 下方 D0 验收记录与 E 执行记录：查看来源、冻结哈希与核对范围；详细数值以链接的结果文件为准。

## 我们交付了什么

| 内容 | 已完成范围 | 权威文件与记录 |
| --- | --- | --- |
| D0 开发期测量 | 24 游戏、71 个计划状态，68 个完整 D/N/P 状态、3 个源 draft 失败、117 个物理续跑组；含准确性、效用、路径与成本诊断 | [完整报告](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/gpu_analysis/checkpoints/d0_report.md) · [结果 JSON](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/gpu_analysis/checkpoints/d0_report.json) · [已有验收记录](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/gpu_analysis/checkpoints/d0_report_validation.json) |
| E 整局评估 | 134 个固定候选游戏 × Always / no_info / none；10 个分片均采用 attempt 1，共 402 条游戏–策略记录，无技术缺失 | [最终公开分析](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/aim3_e/results/analysis.public.json) · [执行状态](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/aim3_e/results/E_RUN_STATUS.public.md) · [执行任务书](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/aim3_e/results/EXECUTION_TASK.public.md) |
| 报告与图表 | 测量研究、负结果、机制诊断；四图各有 PNG/SVG，保留来源字段和值 | [主报告](MINIMAL_REPORT_DRAFT.md) · [图表来源](figures/figure_sources.json) |
| 补充测量与探索性对照 | 队友 Step 0c 的 127 点／81 游戏局部结果，以及方向 B 在同批标签上的离线信号筛选；不是 D1 | 主报告第 4.6 节 · [既有复核输出与脚本](supplementary/README.md) |

E 方法仍以 [v1.1 冻结清单](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/aim3_e/plan/FREEZE.json) 和 [评估计划](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/aim3_e/plan/EVALUATION_PLAN.md) 为准。D0 的 3 个源失败保持缺失，原状态权重为 `1/(24 × original_k_j)`；admission（P−D）、info（P−N）与 revision（N−D）分别报告。

## 核心结论

- **confidence 与预测准确性有描述性关联，但局部终局差异极少。** confidence 与 EM、token-F1 的加权秩相关为 0.616、0.567；P 相对 D 改变首动作 31/68 次，而终局结果仅在 1/68 个状态不同。现有 D0 不足以可靠辨识稳定的效用排序能力。
- **E 的主收益方向未定，额外成本已有记录。** Always / no_info / none 的 SR@30 为 18.66% / 17.16% / 16.42%；唯一主对比 Always − no_info 为 +1.49 个百分点，预定 97.5% 区间为 [−11.60, +14.47]。Always 调用量约为 none 的 2.9 倍、no_info 的 1.5 倍；不能据此宣称收益为零或等价。
- **按预设条件交付测量研究。** 本组 Utility Gate 学习分支未触发，没有训练或验证 Gate；队友的门控训练属于另一开发流程。
- **补充测量增加了跨协议对照，但未完成独立验证。** Step 0c 中存在更多正负局部差异；方向 B 区分“是否发生变化”与“变化是否有益”。两者共用开发标签，不能计作两次独立验证或替代 D1。

## 四张图

| 图 | 要读出的信息 | 文件 |
| --- | --- | --- |
| 1：D0 动作与终局 | 动作改变不等于终局改变；涉及 N 的动作比较分母为 67 | [PNG](figures/01_d0_action_outcome.png) · [SVG](figures/01_d0_action_outcome.svg) |
| 2：D0 confidence | 按原权重四分组的 EM/F1 与三种单次观测效用 | [PNG](figures/02_d0_confidence.png) · [SVG](figures/02_d0_confidence.svg) |
| 3：E 成功率 | 三臂 SR@30 与唯一主对比的预定区间 | [PNG](figures/03_e_outcomes.png) · [SVG](figures/03_e_outcomes.svg) |
| 4：E 成本 | 模型调用量与已知请求耗时；不代表完整 GPU 成本 | [PNG](figures/04_e_cost.png) · [SVG](figures/04_e_cost.svg) |

## 现有复算入口与可分享版本

- D0：[入口说明](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/gpu_analysis/docs/D0_ANALYSIS_IMPLEMENTATION.md) 与 [build_d0_report.py](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/tools/build_d0_report.py)。在该快照的仓库根目录用新输出名运行 `python -B tools/build_d0_report.py --out gpu_analysis/generated/d0_report_new.json`。既有验收记录记载 78 项测试通过和隔离 CPU 复算逐字节一致。
- E：[公开逐局结果](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/recheck_4b/data/e_episode_outcomes.jsonl)、[数据清单](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/recheck_4b/data/DATA_MANIFEST.json) 与 [独立复算说明](https://github.com/YokilyHIT/cs5446/blob/a9d837dc2ac3a54423943040551a04ae4576f3b5/recheck_4b/README.md)。公开逐局表用于数值复验，不替代原始调用审计；公开分析是脱敏副本，其哈希与本地原件分别记录。
- 四图：[plot_baseline.py](figures/plot_baseline.py) 读取已有结果；字段、数值及输入哈希见 [figure_sources.json](figures/figure_sources.json)。
- 补充测量：[来源说明](supplementary/README.md)、[127 点复核输出](supplementary/check_unbiased.txt)、[方向 B 复核输出](supplementary/dirB_screen.txt)。原数据固定到 master `a26e7e4`，本轮复制已验收脚本与输出，没有重新执行。
- 可分享的固定仓库快照：[a9d837d](https://github.com/YokilyHIT/cs5446/tree/a9d837dc2ac3a54423943040551a04ae4576f3b5)，以上既有结果与复算入口固定到该提交；本目录是在其基础上的报告文字更新。

本次整理只读取已有结果和记录，没有重跑分析、重绘图表或启动实验。

## 尚未完成与提交前事项

- **D1 独立局部验证未完成，N/P 独立复现抽查未完成。** E 和队友开发数据的补充测量均不能替代它们。
- **E 冻结时历史用途记为未核实，后续材料已有同一游戏集的团队评测记录。** 结果仅按固定候选集上的条件性比较报告，不宣称是团队未使用过的独立测试集；记录本身也不证明本组冻结前接触过队友结果。
- D0 来自开发游戏，状态有聚类与共享物理路径，且每组仅一次贪心续跑；confidence 不是校准概率。结论限于当前 4B 配置，机制解释仍需验证。
- 成本仍有范围限制：D0 历史调用记录存在缺口，E 请求耗时与 runner 墙钟不能相加，也不覆盖完整作业成本。
- **正式课程提交仍需课程指定的 AI 使用声明格式，以及成员使用情况、贡献和全体作者核对确认。** 当前主报告保留已知 AI 辅助事实，尚非最终审定稿。

## 本次整理的必要变更

- 增加本页作为阅读、结果和复算入口；报告继续使用同一份 D0 与 E 输出。
- 修正 proposal 章节定位为第 3 节 Aim 2、第 6 节 Risks and Mitigations。
- 更新 E 历史资格的解释，保留原冻结记录；队友整局成绩未纳入，已复核的局部测量与离线筛选在独立小节呈现。
- 将本地路径替换为公开来源，区分冻结结果快照、既有验收与本次文字更新；四图与结果表保持不变。
- 报告变更可由仓库提交历史追溯；内部交付记录和草稿备份由项目组保留。正式 AI 声明、成员贡献和作者确认仍待补充。
- 新增补充测量及其已有复核来源；本组 D0/E 的数据、结果表、图和统计规则保持不变，D1 状态不变。

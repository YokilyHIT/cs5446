# CS5446 GPU 研究数据与分析交接

更新：2026-10-18。本 `gpu` 分支在团队仓库 `master` 基础上增加 GPU 侧的 D0 开发数据、便携 CPU 分析代码和研究说明，以及 4B 基线报告、E 结果和队友复验包，供团队同步与复算。

**D0-var 固定 24 游戏采集及完整 CPU 描述报告已完成：71 个预选状态，68 个有完整 D/N/P 结果，3 个源 draft 失败，117 个物理续跑组。** 报告包含跨作业敏感性、全部物理路径、真实调用成本及其未知范围、固定案例和冻结 N/P 候选。N/P 实际复测及 D1 尚未完成；4B 的 E 整局评估已完成，见下一节。这里的 checkpoint 是数据与分析记录，没有训练出的新模型权重。

## 4B 基线报告、E 结果与队友复验（2026-10-18）

**参加复验的队友请先只读 [`recheck_4b/README.md`](recheck_4b/README.md)，用自己的代码算完并交回结果后，再打开本页其余链接。** 仓库公开，盲法只靠自觉。

| 位置 | 内容 |
|---|---|
| [`recheck_4b/`](recheck_4b/) | 复验任务说明、E 逐局结果（134 个 unseen 游戏 × 3 臂）、结果模板与比对脚本 |
| [`aim3_e/`](aim3_e/) | E 的 v1.1 冻结计划（与原件逐字节相同），以及最终分析和执行记录的公开副本（本机与集群路径已换成占位符） |
| [`report_4b/`](report_4b/) | 4B 基线报告草稿、四张图、绘图脚本及图表来源记录 |

逐局完整轨迹与调用审计约 8.6 GB，未上传；来源哈希见 `recheck_4b/data/DATA_MANIFEST.json` 和 `aim3_e/README.md`。

## 先读什么

1. [两位负责人的方向、分工和实验方法](gpu_analysis/docs/GPU_NPU_OWNER_ALIGNMENT.md)
2. [D0 当前结果及最小后续工作](gpu_analysis/docs/D0_STATUS_AND_NEXT_STEPS.md)
3. [D/N/P 与整局三臂协议](gpu_analysis/docs/RESEARCH_PROTOCOL.md)
4. [研究计划正文摘录](gpu_analysis/docs/RESEARCH_PLAN.md)及[与队友路线的对照](gpu_analysis/docs/ROUTE_ALIGNMENT.md)
5. [数据内容、字段语义与证据范围](gpu_analysis/data/README.md)

两人先确认 A 的交付层级、NPU 是否主跑 E、E 的资格及实验方案，再分配具体分析任务。分工建议不表示这些研究修订已被共同批准。

## 直接复算

先获取这个分支：

```sh
git clone --branch gpu --single-branch https://github.com/YokilyHIT/cs5446.git cs5446-gpu-analysis
cd cs5446-gpu-analysis
```

在仓库根目录运行，需要 Python 3.10 或以上版本，仅使用标准库，无需 GPU、NPU、模型服务或 ALFWorld 环境：

```sh
python -B tools/build_d0_report.py --out gpu_analysis/generated/d0_report_new.json
```

输出 JSON、同名 Markdown 和后缀 `_np_candidates.json` 的独立候选清单。输出已存在时会拒绝覆盖；再次运行请使用新输出文件名。临时分析结果目录 `gpu_analysis/generated/` 已被 Git 忽略。

该入口复用原字节的指标、案例、敏感性和 N/P 选择函数，保留原始权重、缺失和同分规则。它读取随包的派生证据，独立完成本轮 CPU 描述；不需要原工作区或全链 hydrated 重建。不产生确认性区间、p 值或正式 C 上界。

直接阅读[完整中文报告](gpu_analysis/checkpoints/d0_report.md)、[完整 JSON](gpu_analysis/checkpoints/d0_report.json)及[代码依赖和改动清单](gpu_analysis/docs/D0_ANALYSIS_IMPLEMENTATION.md)。原 [metrics-only checkpoint](gpu_analysis/checkpoints/d0_metrics.json) 与 `tools/analyze_d0_snapshot.py` 保留为主指标不变的基线。

## 目录内容

| 位置 | 用途 |
|---|---|
| `gpu_analysis/data/d0_snapshot.json` | 全部 71 点的 D/N/P、预测、原分数、真实 D 后继、状态与原权重 |
| `gpu_analysis/data/d0_rollout_summaries.json` | 全部 117 组的动作、观察及终止摘要；按 rollout ID 关联，未按结果挑选 |
| `gpu_analysis/data/final_accounting_summary.json` | 原接受记录的实际计数与保守扣费汇总，包含失败尝试 |
| `gpu_analysis/data/source_bindings.json` | 导出用到或核对过的 148 份原件的逻辑路径、大小和 SHA-256 |
| `gpu_analysis/checkpoints/` | 收尾完成摘要、已运行的便携指标和验证记录 |
| `gpu_analysis/docs/` | 两人同步、研究协议、路线对照和下一步 |
| `gpu_analysis/data/d0_identity_evidence.json` | 全 71 点实际局部作业/服务身份，恢复组沿原出处关联 |
| `gpu_analysis/data/d0_cost_evidence.json` | 已有逐调用审计的便携成本记录、来源及未知范围 |
| `gpu_analysis/data/d0_np_evidence.json` | 全 117 组真实恢复与调用日志绑定 |
| `tools/build_d0_report.py` | 完整 CPU 报告公共入口 |
| `tools/d0_paths.py`、`tools/d0_costs.py` | 物理轨迹和成本的薄分析模块 |
| `tools/d0_report_markdown.py` | 从同一 JSON 结果渲染中文报告 |
| `tools/analyze_d0_snapshot.py` | 保留的 metrics-only 基线入口和公共小函数 |
| `tools/export_d0_snapshot.py` | 持有完整本地原件时重新导出；普通分析不需要运行 |
| `research_progress/2026-10-10-d0-analysis/` | 原字节的分析定义、函数与 60 项纯函数测试 |
| `research_progress/2026-10-10-np-audit/` | 原字节的 N/P 选择器及冻结 spec，仅 CPU 选择 |

原研究指标沿用仓库已有的 `alfworld-preexp-npu/preexperiments/direction_b/metrics.py`。源码大小及哈希见 [analysis_sources.json](tools/analysis_sources.json)，输入合同见 [analysis_input_contract.md](tools/analysis_input_contract.md)。请从新入口分析；历史 `analysis_tool.py` 的完整数据重建 CLI 不属于这个最小包的支持范围。

该 `metrics.py` 的函数逻辑保持不变；本分支只将其换行固定为原冻结文件的 CRLF 字节，并用 Git attributes 防止跨平台转换，以维持已绑定的 SHA-256。

## 分析时必须保留的口径

- D0 是开发期测量，未对基础模型做微调；局部每组为一次续跑。观测差值不等于已知真实条件效用。
- 三个源 draft 失败点保留在原 71 点及失败分母中，局部结果缺失，不能补零。N 的已判定格式失败则保留为有效 Y=0。
- 原状态权重为 `1/(24*k_j)`；可用集合整体归一，不能删点后按每局剩余点数重新平权。报告每项指标自己的分母。
- 预测准确性参考 D 执行 draft 后的真实观察；confidence 按原 mean logprob 排序，不把 exp 分数解释成成功概率。
- 账本 `charged` 是保守预算扣额，不能当成实际模型调用或实际失败次数。报告按真实逐调用派生记录汇总，停止尝试中的未知用量仍明确保留。

原 4 份快照 JSON 合计约 2 MB，新增 3 份必要的派生分析证据。模型、环境资产、完整请求/概率日志、Slurm/SSH 原件和多版本执行包装层留在原档案中。本分支的 SHA 绑定支持追溯与完整性核对，不代表 Git 中已包含全部原件。

## 验证

本轮验证见 [d0_report_validation.json](gpu_analysis/checkpoints/d0_report_validation.json)：78 项测试通过（60 项原冻结测试及 18 项定向检查），隔离复制代码和六份数据、禁用 site packages 后，报告 JSON、Markdown 和 N/P 清单均逐字节复现。原发布验证记录 [portable_validation.json](gpu_analysis/checkpoints/portable_validation.json) 保留。

```sh
python -B -m pytest research_progress/2026-10-10-d0-analysis/tests tests -q -p no:cacheprovider
```

测试需要额外安装 pytest；分析入口自身不依赖它。验证没有新增模型调用、环境实例或集群作业。

# CS5446 GPU 研究数据与分析交接

更新：2026-10-15。本 `gpu` 分支在团队仓库 `master` 基础上增加 GPU 侧的 D0 开发数据、便携 CPU 分析代码和研究说明，供团队同步与复算。

**D0-var 固定 24 游戏采集已完成：71 个预选状态，68 个有完整 D/N/P 结果，3 个源 draft 失败，117 个物理续跑组。** 当前交付包含描述性分析；N/P 独立抽查、完整 D0 报告以及 D1/E 后续研究仍有待完成。这里的 checkpoint 是数据与执行完成记录，没有训练出的新模型权重。

## 先读什么

1. [两位负责人的方向、分工和实验方法](gpu_analysis/docs/GPU_NPU_OWNER_ALIGNMENT.md)
2. [D0 当前结果及最小后续工作](gpu_analysis/docs/D0_STATUS_AND_NEXT_STEPS.md)
3. [D/N/P 与整局三臂协议](gpu_analysis/docs/RESEARCH_PROTOCOL.md)
4. [研究计划正文摘录](gpu_analysis/docs/RESEARCH_PLAN.md)及[与队友路线的对照](gpu_analysis/docs/ROUTE_ALIGNMENT.md)
5. [数据内容、字段语义与证据范围](gpu_analysis/data/README.md)

两人先确认 A 的交付层级、NPU 是否主跑 E、E 的资格及实验方案，再分配具体分析任务。分工建议不表示这些研究修订已被共同批准。

## 直接复算

在仓库根目录运行，需要 Python 3.10 或以上版本，仅使用标准库，无需 GPU、NPU、模型服务或 ALFWorld 环境：

```sh
python -B tools/analyze_d0_snapshot.py --dataset gpu_analysis/data/d0_snapshot.json --out gpu_analysis/generated/d0_metrics.json
```

输出 JSON 和同名 Markdown。输出已存在时会拒绝覆盖；再次运行请使用新输出文件名。临时分析结果目录 `gpu_analysis/generated/` 已被 Git 忽略。

该入口复用原字节的指标、案例与敏感性函数，保留原始权重、缺失和同分规则。支持加权描述、confidence 与准确性/观测效用、分层、固定哈希案例、逐游戏删除敏感性及跨作业标签清单；跨作业剔除敏感性和完整逐调用成本关联尚未实现于此入口。输出明确标为 `metrics_only_development_description`，不产生确认性区间、p 值或正式 C 上界。

可直接查看已复算的[指标结果](gpu_analysis/checkpoints/d0_metrics.md)及[完整指标 JSON](gpu_analysis/checkpoints/d0_metrics.json)。

## 目录内容

| 位置 | 用途 |
|---|---|
| `gpu_analysis/data/d0_snapshot.json` | 全部 71 点的 D/N/P、预测、原分数、真实 D 后继、状态与原权重 |
| `gpu_analysis/data/d0_rollout_summaries.json` | 全部 117 组的动作、观察及终止摘要；按 rollout ID 关联，未按结果挑选 |
| `gpu_analysis/data/final_accounting_summary.json` | 原接受记录的实际计数与保守扣费汇总，包含失败尝试 |
| `gpu_analysis/data/source_bindings.json` | 导出用到或核对过的 148 份原件的逻辑路径、大小和 SHA-256 |
| `gpu_analysis/checkpoints/` | 收尾完成摘要、已运行的便携指标和验证记录 |
| `gpu_analysis/docs/` | 两人同步、研究协议、路线对照和下一步 |
| `tools/analyze_d0_snapshot.py` | 本分支支持的 CPU 分析入口 |
| `tools/export_d0_snapshot.py` | 持有完整本地原件时重新导出；普通分析不需要运行 |
| `research_progress/2026-10-10-d0-analysis/` | 原字节的分析定义、函数与 60 项纯函数测试 |

原研究指标沿用仓库已有的 `alfworld-preexp-npu/preexperiments/direction_b/metrics.py`。源码大小及哈希见 [analysis_sources.json](tools/analysis_sources.json)，输入合同见 [analysis_input_contract.md](tools/analysis_input_contract.md)。请从新入口分析；历史 `analysis_tool.py` 的完整数据重建 CLI 不属于这个最小包的支持范围。

该 `metrics.py` 的函数逻辑保持不变；本分支只将其换行固定为原冻结文件的 CRLF 字节，并用 Git attributes 防止跨平台转换，以维持已绑定的 SHA-256。

## 分析时必须保留的口径

- D0 是开发期测量，未对基础模型做微调；局部每组为一次续跑。观测差值不等于已知真实条件效用。
- 三个源 draft 失败点保留在原 71 点及失败分母中，局部结果缺失，不能补零。N 的已判定格式失败则保留为有效 Y=0。
- 原状态权重为 `1/(24*k_j)`；可用集合整体归一，不能删点后按每局剩余点数重新平权。报告每项指标自己的分母。
- 预测准确性参考 D 执行 draft 后的真实观察；confidence 按原 mean logprob 排序，不把 exp 分数解释成成功概率。
- 账本 `charged` 是保守预算扣额，不能当成实际模型调用或实际失败次数。完整的逐调用成本分析需要原始审计记录。

4 份导出数据 JSON 合计约 2 MB。模型、环境资产、完整请求/概率日志、Slurm/SSH 原件和多版本执行包装层留在原档案中。本分支的 SHA 绑定支持追溯与完整性核对，不代表 Git 中已包含全部原件。

## 验证

验证记录见 [portable_validation.json](gpu_analysis/checkpoints/portable_validation.json)。发布前在隔离的本分支目录运行真实 71 点入口，并运行所附 60 项纯函数测试：

```sh
python -B -m pytest research_progress/2026-10-10-d0-analysis/tests -q -p no:cacheprovider
```

测试需要额外安装 pytest；分析入口自身不依赖它。验证没有新增模型调用、环境实例或集群作业。

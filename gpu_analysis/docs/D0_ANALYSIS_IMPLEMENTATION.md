# D0 分析入口与本轮改动

本轮只整理现有 D0 数据的分析依赖，完成可复算的描述报告与 N/P 候选。原 4 份快照、冻结指标和 60 项纯函数测试保持原字节。没有新增采集、模型服务、恢复框架或账本执行路径。

## 使用入口

从仓库根目录运行，Python 3.10+，分析仅依赖标准库：

```sh
python -B tools/build_d0_report.py --out gpu_analysis/generated/d0_report_new.json
```

生成 JSON、同名中文 Markdown 和后缀 `_np_candidates.json` 的独立候选清单。任一输出已存在时拒绝覆盖；选择新名称即可。已交付的 [报告](../checkpoints/d0_report.md)、[JSON](../checkpoints/d0_report.json) 和 [N/P 清单](../checkpoints/d0_report_np_candidates.json) 由同一入口生成。JSON 中保留完整分母、逐状态指标、全部物理组诊断、案例、敏感性和 N/P 选择轨迹。

原 `tools/analyze_d0_snapshot.py` 继续用于 metrics-only 基线复算；其结果与本轮报告的 `metrics` 完全一致。历史 `analysis_tool.py` 的 hydrated CLI 不属于当前支持入口。

## 实际运行依赖

| 文件或目录 | 用途 |
|---|---|
| `tools/build_d0_report.py` | 读取六份便携证据，组合冻结分析，执行 only-verified-false 跨作业敏感性 |
| `tools/d0_report_markdown.py` | 将同一结果渲染为中文报告 |
| `tools/d0_paths.py` | 全 117 组真实路径关联、D 真观察核对、调用冻结 N/P 选择器 |
| `tools/d0_costs.py` | 逐调用成本归属、账本口径对照及未知范围 |
| `tools/analyze_d0_snapshot.py` | 保留的基线分析及文件绑定辅助函数 |
| `tools/analysis_sources.json` | 原冻结分析文件的字节清单 |
| `research_progress/2026-10-10-d0-analysis/sidecar/` | 原指标、案例、敏感性、诊断及 JSON 辅助函数 |
| `research_progress/2026-10-10-d0-analysis/ANALYSIS_SPEC.json` | 冻结指标、分母、同分和案例规则 |
| `alfworld-preexp-npu/preexperiments/direction_b/metrics.py` | 冻结 EM/token-F1 实现；原 CRLF 字节不变 |
| `research_progress/2026-10-10-np-audit/sidecar/np_selection.py` | 从原研究目录逐字节复制的两遍哈希选择器 |
| `research_progress/2026-10-10-np-audit/NP_AUDIT_SPEC.json` | 选择器对应的原冻结说明 |

实际报告使用的代码与数据文件 SHA-256 写入 JSON。`analysis_sources.json` 仍只绑定原文件，不被扩为生产执行清单。新增 N/P 冻结文件通过 `.gitattributes -text` 保留字节；没有全仓换行归一化。

## 数据和证据

| 输入 | 分析内容 |
|---|---|
| `d0_snapshot.json` | 原 24 游戏、71 点、原权重、68 个局部事件与 3 个源失败 |
| `d0_rollout_summaries.json` | 全部 117 物理组真实动作和观察 |
| `final_accounting_summary.json` | 当前 campaign 15 次尝试的接受成本口径；charged 不等于实际使用 |
| `d0_identity_evidence.json` | 实际局部 job/service 身份；67 false、1 true、0 unknown、3 not_applicable |
| `d0_cost_evidence.json` | 原逐调用审计行、终端和 HTTP 使用、物理组调用归属及缺失 |
| `d0_np_evidence.json` | 原物理组、恢复记录与调用审计出处 |

前三份输入保持原样；后三份是本轮新增的必要便携派生证据。`source_bindings.json` 保持原样，供重新导出时追溯原件。普通分析只读取本仓库文件，没有从旧工作区隐式补读的路径。

## 持有原归档时重新导出

以下三个导出器只读原件，并核对实际使用的绑定；它们不在普通报告的依赖链中。用新的输出名重建，不能覆盖交付证据。`ARCHIVE` 指包含 `cs5446_modified` 和原 `.review-cache` 作业原件的工程根目录。

```sh
python -B tools/export_d0_identity_evidence.py --source-root ARCHIVE --out gpu_analysis/generated/identity_recheck.json
python -B tools/export_d0_np_evidence.py --source-root ARCHIVE --out gpu_analysis/generated/np_evidence_recheck.json
python -B tools/export_d0_cost_evidence.py --source-root ARCHIVE --np-evidence gpu_analysis/generated/np_evidence_recheck.json --out gpu_analysis/generated/cost_evidence_recheck.json
```

导出的派生数据保留逻辑路径、文件大小、SHA 和必要记录字段；完整请求、token logprob 和运行原件仍留在原归档。该步骤核查已有记录，不等于重新执行生产验收。

## 本轮精确文件清单

修改的现有文件只有 `.gitattributes`、`README.md`、`tools/analysis_input_contract.md`、`gpu_analysis/data/README.md` 和 `gpu_analysis/docs/D0_STATUS_AND_NEXT_STEPS.md`。

新增文件：

- `tools/build_d0_report.py`
- `tools/d0_report_markdown.py`
- `tools/d0_costs.py`
- `tools/d0_paths.py`
- `tools/export_d0_identity_evidence.py`
- `tools/export_d0_cost_evidence.py`
- `tools/export_d0_np_evidence.py`
- `gpu_analysis/data/d0_identity_evidence.json`
- `gpu_analysis/data/d0_cost_evidence.json`
- `gpu_analysis/data/d0_np_evidence.json`
- `research_progress/2026-10-10-np-audit/sidecar/np_selection.py`
- `research_progress/2026-10-10-np-audit/NP_AUDIT_SPEC.json`
- `tests/test_d0_report.py`
- `tests/test_d0_identity.py`
- `tests/test_d0_costs.py`
- `tests/test_d0_paths.py`
- `gpu_analysis/checkpoints/d0_report.json`
- `gpu_analysis/checkpoints/d0_report.md`
- `gpu_analysis/checkpoints/d0_report_np_candidates.json`
- `gpu_analysis/checkpoints/d0_report_validation.json`
- `gpu_analysis/docs/D0_ANALYSIS_IMPLEMENTATION.md`

`gpu_analysis/generated/` 中的试运行、重新导出和隔离复算结果被忽略，不是新的研究数据或源代码。

## 定向验证与完成边界

```sh
python -B -m pytest research_progress/2026-10-10-d0-analysis/tests tests -q -p no:cacheprovider
```

定向检查覆盖原分母和权重、缺失 N 动作、D 真观察、物理组去重、恢复组出处、实际调用和保守计费的区别、未知终端以及冻结候选规则。真实数据入口和隔离目录复算结果见 [验证记录](../checkpoints/d0_report_validation.json)。这不是 GPU/NPU 运行或 N/P 复测验收。

到可复算报告和候选选择为止，D0 CPU 分析交付完成。下一次 N/P 运行及 D1/E 资格、规模和推断方案仍单独决定。本轮没有 commit、push、集群操作、模型调用或真实账本修改。

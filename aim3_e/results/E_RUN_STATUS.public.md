# Aim 3 E v1.1：最终执行与分析报告

状态：**complete**。更新于 2026-10-18 12:55:42（UTC+8）。固定 134 局 × 三臂共 **402 条结果**已全部取回并通过认证；十片均采用首个完整 attempt 1，无 attempt 2、无缺片、无替换游戏。冻结合并分析只调用一次，退出码 0。

主对比 **Always − no_info = +1.49 个百分点**，预定 97.5% 配对区间 **[-11.60, +14.47] 个百分点**，`direction=not_resolved`。按冻结规则，方向尚未判定；不能将正的点估计写成已证明 Always 有优势，也不能解释为等价。

数值来源：[唯一一次 analysis.json](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/analysis.json)；执行回执：[ANALYSIS_EXECUTION.json](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/ANALYSIS_EXECUTION.json)。本报告只转写预定输出、格式化百分比，并汇总输出中逐条列出的失败机制；未增加检验、改分母或重新选择 attempt。

## 1. 范围、版本与固定方法

这是 **4B 的 E 整局评估（Aim 3）**。D0 开发报告保留；本轮未执行或验收 D1，E 的结果不能替代局部独立验证。

固定 Qwen3-4B-Instruct-2507 Planner/WM、`react_single_env_action_v1`、H=30、seed 42、temperature 0、top_p 0.5、history 50、无 memory，planner/WM 上限为 384/256 tokens。三臂依次 always/no_info/none；每游戏等权、每臂一次。policy failure 与预算耗尽计 0，技术缺失保持 null。配置、prompt、解析器和源码未因中途结果修改。

采用分支 B：十片 14/14/14/14/13/13/13/13/13/13，每片单 worker、单 A100-40GB、8 CPU、48 GB、3 小时作业，runner 超时 9600 秒。`gpu` 的 sinfo 上限为 3:00:00；4 小时 test-only 被路由到 gpu-long，未满足分支 A 的联合条件。第 0 片 runner 3053 秒，严格小于哨兵放行线 6720 秒，随后才提交其余片。

方法：[EVALUATION_PLAN.md](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-evaluation-v1.1/EVALUATION_PLAN.md)；分区原始检查：[BRANCH_DECISION.md](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/BRANCH_DECISION.md)。

| 文件/版本 | SHA256 |
| --- | --- |
| v1.1 FREEZE.json | `30554636830cfc9af3b291d0054e6c2471ab6973198ca506778dc7eebabba5be` |
| 源码清单 | `0d8a589e8b5c6174309e438600f85f8c01ed2402c8de64ba79468a7f9759d14b` |
| E census | `81dfc32c29d917c62e562b9c2d3a5a7cb655e4047112a7f302f0a328821d78d3` |
| shards_manifest.json | `ce667a77eb0b190a599d9c34dd78ed85008096c09dbc87ad07a392e07b226398` |
| frozen_config.json | `7fa9d0fc6deedc126c7cb9460e0003eeb4b77edb092b279d8e150787b8623ad7` |
| attempts.json | `fa5818ed9c986d792560f680651a605a6a6dd6a6633fb663e15c6b93dbfbdead` |
| analysis.json | `8b6c90435041c174945f88b754e9dc8ee353ddc7a9bd26e9ccbdd31ce05ef24e` |

v1.1 的既有正式验收为 19 tests、41 subtests 全通过，Slurm 语法检查通过；本轮未重复测试或修改冻结包。远端每个 attempt 的 74 个源码文件均从指定冻结来源复制并核对，本地较新的五个辅助文件未上传替代。

## 2. 全部 attempt 与选择

所有片均 Slurm `COMPLETED 0:0`、C1–C7 通过、evidence/coverage 为 true，本地与集群完整 JSON 严格相等且文件逐字节一致。逐片 checker 各运行一次；唯一一次冻结合并器按其原有逻辑另做内部输入认证。

| 片 | attempt / 作业号 | 实际节点 | runner 秒 | 证据 / 覆盖 / 两端一致 | 选择 |
| --- | --- | --- | ---: | --- | --- |
| [0](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts/aim3-e-v1.1-s0-a1/CERTIFICATION.json) | 1 / 968227 | xgph11 | 3053 | true / true / true | 首个完整结果 |
| [1](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts/aim3-e-v1.1-s1-a1/CERTIFICATION.json) | 1 / 968520 | xgpg1 | 3494 | true / true / true | 首个完整结果 |
| [2](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts/aim3-e-v1.1-s2-a1/CERTIFICATION.json) | 1 / 968521 | xgpg7 | 3888 | true / true / true | 首个完整结果 |
| [3](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts/aim3-e-v1.1-s3-a1/CERTIFICATION.json) | 1 / 968522 | xgpg5 | 3756 | true / true / true | 首个完整结果 |
| [4](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts/aim3-e-v1.1-s4-a1/CERTIFICATION.json) | 1 / 968523 | xgpg4 | 3570 | true / true / true | 首个完整结果 |
| [5](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts/aim3-e-v1.1-s5-a1/CERTIFICATION.json) | 1 / 968524 | xgph10 | 3064 | true / true / true | 首个完整结果 |
| [6](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts/aim3-e-v1.1-s6-a1/CERTIFICATION.json) | 1 / 968525 | xgpg3 | 3501 | true / true / true | 首个完整结果 |
| [7](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts/aim3-e-v1.1-s7-a1/CERTIFICATION.json) | 1 / 968526 | xgpg2 | 3871 | true / true / true | 首个完整结果 |
| [8](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts/aim3-e-v1.1-s8-a1/CERTIFICATION.json) | 1 / 968527 | xgpg0 | 3664 | true / true / true | 首个完整结果 |
| [9](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts/aim3-e-v1.1-s9-a1/CERTIFICATION.json) | 1 / 968528 | xgpg6 | 3269 | true / true / true | 首个完整结果 |

十个包及 receipt 均核对远端 SHA256，再安全解压并逐文件检查：共 **631 文件、1,202,982,963 压缩字节、7,958,640,360 解压字节**，无缺失根路径或哈希/大小不一致。每个 attempt 根下保留 `TRANSFER_VERIFICATION.json`、`CERTIFICATION.json`、原始输出和本地 checker 日志。最后一次下载前可用空间 916.91 GiB。

全 attempt 清单：[attempts.json](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts.json)；合并输入认证：[MERGE_INPUT_CERTIFICATION.json](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/MERGE_INPUT_CERTIFICATION.json)。历史执行进展完整保留于 [E_RUN_HISTORY.md](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/E_RUN_HISTORY.md)。

## 3. 主对比与次要比较

主对比复用 `paired_study_comparison`：救回/伤害率的 Clopper–Pearson 区间经 Bonferroni 合成差值区间。唯一方向判据为主对比 97.5% 区间的 `direction`；精确双侧 McNemar p 只作补充。134 个计划配对全部可用，缺失为 0。`confirmatory_status=available` 仅表示可计算，不能证明 E 已具备 untouched 资格。

| 对比 | 差值（百分点） | 区间水平 | 区间（百分点） | direction | rescued / harmed | McNemar p |
| --- | ---: | --- | --- | --- | --- | ---: |
| Always − no_info | +1.49 | 97.5% | [-11.60, +14.47] | not_resolved | 13 / 11 | 0.838820 |
| Always − none | +2.24 | 95% | [-8.52, +12.84] | not_resolved | 11 / 8 | 0.647606 |
| no_info − none | +0.75 | 95% | [-9.00, +10.43] | not_resolved | 8 / 7 | 1.000000 |

主对比另外保留的描述性 95% 区间为 [-10.34, +13.22] 个百分点。Always − none 与 no_info − none 均是预定描述性比较，未作第二个确认性结论。rescued 指 treatment 成功且 control 失败，harmed 相反。

## 4. 三臂 SR@30 与失败诊断

| 臂 | 成功 / 计划 | SR@30 | 描述性 95% Wilson 区间 | policy failure / 134 | 技术缺失 / 未运行 |
| --- | --- | ---: | --- | --- | --- |
| Always | 25 / 134 | 18.66% | [12.97%, 26.09%] | 19 / 134（14.18%） | 0 / 0 |
| no_info | 23 / 134 | 17.16% | [11.72%, 24.44%] | 22 / 134（16.42%） | 0 / 0 |
| none | 22 / 134 | 16.42% | [11.10%, 23.61%] | 11 / 134（8.21%） | 0 / 0 |

失败按主分析规则计 0，没有因内容失败剔除游戏或重跑。以下分母是各角色的实际 planner 调用数，非每局计划上限。

| 臂 / 角色 | planner 调用 | policy failure | 每调用失败率 | 失败中 finish=length 且 384 tokens |
| --- | ---: | ---: | ---: | ---: |
| Always / draft | 3,374 | 9 | 0.267% | 7 |
| Always / replan | 3,365 | 10 | 0.297% | 10 |
| no_info / draft | 3,378 | 14 | 0.414% | 13 |
| no_info / no_info | 3,364 | 8 | 0.238% | 8 |
| none / draft | 3,540 | 11 | 0.311% | 11 |

其余臂/角色组合均为 0 调用、0 失败，失败率为 null，不能写作 0%。没有 no_info_fallback 调用。

按臂计，达到 384-token 上限的失败为 Always 17、no_info 21、none 11 次，共 49/52。输出中可核对的机制为：45 次 `missing_action + length + 384`，4 次 `truncated_or_unverified_finish + length + 384`，3 次 `multiple_actions + stop`（completion tokens 为 182、87、69）。本报告不读取原 Thought 来追加行为因果结论；这些字段支持输出截断/多动作的诊断。

Always/no_info 的正常决策步均设计为两次 planner 调用，但早停与内容失败会改变实际调用暴露；与 none 的比较包含额外调用所带来的成本及失败机会，不能仅归因于预测信息。planner 上限与解析器保持冻结。

## 5. 双臂均无 policy failure 的敏感性

这是按对比筛选的处理后子集，仅作描述，不能替代主结果或解释为排除失败后的因果效应。全部 `confirmatory_level=null`。

| 对比 | 保留 / 134 | 排除 | 差值（百分点） | 描述性 95% 区间 | rescued / harmed | McNemar p（描述性） |
| --- | --- | ---: | ---: | --- | --- | ---: |
| Always − no_info | 95 / 134 | 39 | +2.11 | [-13.07, +17.08] | 11 / 9 | 0.823803 |
| Always − none | 107 / 134 | 27 | +4.67 | [-8.05, +16.98] | 11 / 6 | 0.332306 |
| no_info − none | 103 / 134 | 31 | +0.00 | [-11.40, +11.40] | 6 / 6 | 1.000000 |

## 6. 成本和计时

| 臂 | 记录模型逻辑调用 / HTTP 次数 | 已知 prompt tokens | 已知 completion tokens | 已知请求耗时（秒） | token 成本完整 |
| --- | --- | ---: | ---: | ---: | --- |
| Always | 10,104 / 10,104 | 6,968,121 | 681,110 | 14,010.460 | true |
| no_info | 6,742 / 6,742 | 4,963,623 | 538,174 | 11,001.751 | true |
| none | 3,540 / 3,540 | 2,611,028 | 274,030 | 5,636.370 | true |
| 合计 | 20,386 / 20,386 | 14,542,772 | 1,493,314 | 30,648.580 | true |

记录的 402 行 token 成本完整：未知 attempt 数、usage 不完整、缺延迟及缺成本字段均为 0，`bound_unknown=false`。这些是模型请求记录的成本（Always 含 WM 调用），不包含环境与服务启动等资源。冻结输出仍明确 `all_attempts_resource_total_known=false`，因此不能宣称完整 GPU 资源总成本已知。

所有 attempt 的 **runner 墙钟合计 35,130 秒（9.7583 小时）**，没有缺失 runner 时间。每片一张 GPU，这只是单卡 runner 时间的累计口径，排除启动、收尾、排队；并行作业之和不等于端到端经过时间。请求耗时小计与 runner 时间不可相加，不能把请求秒数当作 GPU 墙钟。无废弃或重跑 attempt。

本地唯一一次最终复算耗时 527.094 秒；这是 CPU 分析耗时，单列于 [执行回执](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/ANALYSIS_EXECUTION.json)，不并入实验 GPU runner 时间。

## 7. 解释边界与事件

**历史用途未核实，结果只是候选集上的条件性计算；不显著不等于等价；整局结果不能代替局部 admission/info 的证据。**

区间依赖 iid 游戏配对总体模型；这里只覆盖一个固定的贪心解码配置与所记录的后端，不能由 T=0 推出跨后端逐字节复现。固定 always/no_info/none 顺序存在时间块局限。E 的历史使用资格仍未与负责人核对，不宣称 untouched 确认性验证完成。D1 本轮未执行或验收；Aim 2 的 Utility Gate 学习分支按 proposal 的预设条件未触发，采用 measurement study 交付路径，而非已训练 Gate 的检验失败。条件与 D0 证据见 [4B baseline draft](<LOCAL_REPO>/research_progress/2026-10-18-4b-baseline-report/MINIMAL_REPORT_DRAFT.md)。

哨兵按预定计时门槛放行；其余九片在不同指定节点运行，固定端口未改。第 2 片先因 GPU 用户配额、后因 Priority 排队，保持原作业等待；未绕过配额或换节点重提。07:37 的 SSH 中断按约暂停，用户重新登录后 09:37 恢复；这不构成集群作业失败。最后一片离开队列后 squeue 返回 Invalid job id，以 sacct 的 COMPLETED 0:0 和完整 phases 确认终态。

保留原失败预检、三处授权衔接修正、旧验证报告来源说明，以及所有 D0/P1/P2/冒烟和 E 原始数据。先前 85 条总清单与 74 条源码的临时计数错误发生在创建/提交前，诊断记录保留，不构成额外 attempt。冒烟已触发的负责人提示文本仍未发送；未向队友或外部渠道发送通知，未 push。

## 8. 文件入口与复算说明

- [最终原始分析 JSON](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/analysis.json)：所有预定比较、敏感性、逐臂成本与失败机制。
- [全部 attempt 清单](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/attempts.json)、[输入认证](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/MERGE_INPUT_CERTIFICATION.json)。
- [最终分析执行回执](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/ANALYSIS_EXECUTION.json)、[stdout](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/analysis.stdout.txt)、[stderr](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/analysis.stderr.txt)。
- [执行历史](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/E_RUN_HISTORY.md)和[执行任务](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/EXECUTION_TASK.md)。
- [4B 最小报告](<LOCAL_REPO>/research_progress/2026-10-18-4b-baseline-report/MINIMAL_REPORT_DRAFT.md)：汇合既有 D0 描述与本轮 E 结果。

既定复算命令及实际参数已完整记录在执行回执中。原始 analysis.json 保持不覆盖；如以后经授权独立复算，应使用新的输出路径并保留原结果。本轮没有第二次分析调用。

监听：`aim-3-e-v1-1` 已于 2026-10-18 12:57:13（UTC+8）通过应用工具确认为 **PAUSED**。取回、复算和两份报告均已完成，保留聊天、不归档。

2026-10-18 基线写作修订：仅更新第 7 节关于解码覆盖与 Aim 2 的解释，实验数字、执行状态和正式分析调用数不变。修订前报告保存在 [历史副本](<LOCAL_REPO>/research_progress/2026-10-18-aim3-e-run/E_RUN_STATUS.before-baseline-revision-20261018.md)；原 `COMPLETION.json` 继续对应该历史版本，新稿另由 baseline 目录的 `BASELINE_DELIVERY.json` 记录。独立 reviewer 的复算不属于这份正式执行回执的调用计数。

# Aim 3：E 评估计划 v1.1

v1.1 只修改运行参数（分支 B：分片数），总体、配置、主次分析、计分和选择规则与 v1 相同；v1 的 FREEZE sha256 为 `cc072df5aec0a78bcc2ed30ee8b79776d6fcbd1ab151f8f6ef5afedf43ee61c9`。

**2026-10-18，E 结果访问前固定方法与候选清单；尚未提交。** 用户确认历史用途尚未与负责人核对，故本版不宣称 134 局已通过 untouched 资格审查。以下分析选择在查看 E 结果前固定；后续资格结论另记，不静默替换游戏。

**总体与配置。** 全取 `e_games.json` 的 134 局 `eval_out_of_distribution`，每游戏等权、每臂一次，H=30。清单 SHA256：`81dfc32c29d917c62e562b9c2d3a5a7cb655e4047112a7f302f0a328821d78d3`。三臂依次 `always / no_info / none`，沿用冒烟的 `react_single_env_action_v1`、Qwen3-4B-Instruct-2507、seed 42、temperature 0、top_p 0.5、planner 384 tokens、WM 256、history 50、无 memory、单 worker、A100-40GB。固定顺序的时间块局限如实报告，不改 planner、prompt 或解析器。完整配置与 prompt/profile 哈希见 `frozen_config.json`；源码清单 SHA256：`0d8a589e8b5c6174309e438600f85f8c01ed2402c8de64ba79468a7f9759d14b`。

**主分析。** 唯一主对比为 Always − no_info 的 single-attempt SR@30（`Y_study`）。policy failure 和预算耗尽计 0；技术缺失保持 null，134 个计划配对分母不变。直接复用 `paired_study_comparison`，水平 0.975：救回/伤害率的 Clopper–Pearson 区间经 Bonferroni 合成差值区间。沿用协议 §6.2–6.3，唯一方向裁决是 97.5% 区间下界>0或上界<0；精确双侧 McNemar p 另报，不择其有利者。95% 区间作描述；缺任何配对即暂停主点估计和推断并报界限。区间依赖 iid 游戏配对总体模型，不覆盖跨 seed 随机性，也不把不显著解释成等价。历史资格未核实期间只作候选集上的条件性计算，不作 untouched 确认性声明。

**次要分析。** Always − none、no_info − none、六类任务、成本及失败机制均为描述性。按臂及 draft/no_info/replan 角色报告实际 planner 调用数、失败数/率、`finish=length` 与输出上限、未知 token 成本；请求秒数与 runner/作业墙钟分开。对每个对比另报告双臂均无 policy failure 的配对子集与保留数，水平设为 None；这是处理后筛选的描述敏感性，不能替代主结果或称为“排除失败后的因果效应”。与 none 的差异包含多一次 planner 调用带来的成本及失败机会；Always/no_info 的调用结构相同不保证实际暴露次数相同。整局结果不代替局部 admission/info 的确认性证据。

**执行与选择。** 游戏路径排序后按索引 modulo 10 轮转，十片为 14/14/14/14/13/13/13/13/13/13，类型跨片差最多 1；清单及哈希见 `shards_manifest.json`。每片 1 GPU、3 小时；满 30 步情景约 10.2 GPU 小时 runner 时间，非硬上界。每片每次新目录，记录全部 attempt；分片不做确认性检验，运行期间不依据效应修改方案。完整性只由 C1–C6 和冻结配置/选择身份决定；policy failure 或 C7 未覆盖不能触发重跑。每片最多因不完整整片重跑一次，不拼接两次记录，采用最早的完整 attempt（1 优先于 2），不按成绩选择，不换游戏。仍不完整则保留缺失并暂停主推断；废弃/重跑成本另列。合并后只作一次主分析。先单独运行第 0 片作为计时哨兵：其 runner 墙钟低于 runner 超时的 70%，且本地核对证据完整，才放行其余各片；否则暂停，交由用户决定。这只是运行顺序，不依据结果。启动前的技术失败（没有 runner 清单）同样算一次 attempt；这个低概率风险已被接受。

**执行前记录。** 冒烟 PASS；两臂各 2/5 policy failure 已触发负责人提示阈值，待转告文本见 `OWNER_NOTICE.md`，尚未发送。E 历史用途仍未核实（用户本轮确认）；仅完成枚举/reset 不构成未使用证明。执行与分析文件由 `FREEZE.json` 及 `FREEZE.sha256` 留存版本，原始证据不修改。

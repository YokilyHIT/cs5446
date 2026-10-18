# D0 开发数据完整描述报告

本报告分析固定 4B Planner 与一步 World Model 在 ALFWorld D0 开发游戏中的局部 D/N/P 测量。在 68 个有完整结果的状态上，按原状态权重归一后的 D/N/P 成功均值分别为 0.1313868613 / 0.1167883212 / 0.1167883212。首动作变化较多，终局差异集中于同一游戏的两个状态。confidence 与文本匹配准确性呈正向描述性关联；局部效用的非零观测很少，尚不能据此确定其稳定排序能力。

这是现有数据的完整描述性报告。每物理组仅续跑一次（r=1），D0 用于开发和诊断；本报告不估计真实条件效用，不提供确认性区间、p 值、认证 C 上界或 D1 样本量。N/P 候选已在后文列出，实际跨作业抽查仍待运行。

## 研究设置与分母

Planner 和 WM 为 Qwen3-4B-Instruct-2507，profile 为 `react_single_env_action_v1`；seed 42、temperature 0、top_p 0.5，输出上限分别为 384/256，history 50，无 memory，H=30，采集使用整卡 A100-PCIE-40GB。源轨迹使用 None 策略。D 执行原 draft，N 不看预测再次决策，P 看预测再次决策；三者从同一预选状态恢复，之后均使用无预测策略 μ。剩余预算为 30−t，包含干预动作。

期望效用定义为 U_admission=V_P−V_D、U_info=V_P−V_N、U_revision=V_N−V_D。下文的“观测差”是单次 Y 差。共享物理组只执行和计数一次，不增加独立样本。

| 覆盖项 | 数量或原权重 |
| --- | --- |
| 原计划游戏 / 预选点 | 24 / 71 |
| 完整 D/N/P 点 / 物理组 | 68 / 117 |
| 源 draft 失败点 | 3 |
| 全部原权重 | 1 |
| 可用 D/N/P 原权重 | 0.9513888889 |
| 源 draft 失败原权重 | 0.04861111111 |
| D 检查状态 | {"passed": 68, "not_applicable": 3} |
| D 新 μ 请求对 | 770 |

68 个通过的 D 检查中，67 点包含新 μ 请求比对，另 1 点只覆盖环境转移。这些 D 复现检查不替代独立 N/P 抽查。

每点原权重为 1/(24×original_k_j)。每个指标只在自己的合格集合内整体归一；删点后不按每局剩余点数重新平权。3 个源 draft 失败点没有形成局部预测事件，保留在 71 点分母中，局部 Y、confidence、accuracy 和 U 均为缺失。71 点全计划均值因此为 null；下面的可用交集结果只描述已观测部分。

## 局部结果与动作变化

| 指标 | 全计划均值 | 可用交集加权均值 | 观测点数 | 原权重覆盖 | 不加权成功点数 |
| --- | --- | --- | --- | --- | --- |
| Y_D | — | 0.1313868613 | 68 | 0.9513888889 | 9 |
| Y_N | — | 0.1167883212 | 68 | 0.9513888889 | 8 |
| Y_P | — | 0.1167883212 | 68 | 0.9513888889 | 8 |
| 观测 admission | — | -0.01459854015 | 68 | 0.9513888889 | 见下表 |
| 观测 info | — | 0 | 68 | 0.9513888889 | 见下表 |
| 观测 revision | — | -0.01459854015 | 68 | 0.9513888889 | 见下表 |

| 观测差 | +1 点数 | 0 点数 | −1 点数 | 缺失 | 加权正差比例 | 加权负差比例 |
| --- | --- | --- | --- | --- | --- | --- |
| admission | 0 | 67 | 1 | 3 | 0 | 0.01459854015 |
| info | 1 | 66 | 1 | 3 | 0.01459854015 | 0.01459854015 |
| revision | 0 | 67 | 1 | 3 | 0 | 0.01459854015 |

| 可解析首动作比较 | 改变数 / 可比较数 | 加权改变比例 | 原权重覆盖 |
| --- | --- | --- | --- |
| P 对 D | 31/68 | 0.4525547445 | 0.9513888889 |
| N 对 D | 20/67 | 0.2962962963 | 0.9375 |
| P 对 N | 28/67 | 0.4148148148 | 0.9375 |

N 的一次首动作格式失败是有效 Y=0，但没有可执行 N 动作。它保留在 P−N、N−D 的终局比较中，仅从要求双方动作可解析的比较中排除。因此 N 对 D 为 20/67。

## 预测准确性与 confidence

准确性参考是 D 执行原 draft 后的真实第一步 observation。EM 和 token-F1 使用冻结文本规范化，仅为文本匹配代理。排序使用原始 mean logprob；exp 分数仅用于展示，不是校准概率。

| 准确性 | 加权均值 | 点数 | 原权重覆盖 |
| --- | --- | --- | --- |
| EM | 0.4087591241 | 68 | 0.9513888889 |
| token_F1 | 0.7055986218 | 68 | 0.9513888889 |

展示分数的未加权中位数为 0.9911908118，其中 56/68 ≥ 0.95。原 mean logprob 有 68 个精确不同值。

| 变量一 | 变量二 | 加权 Pearson | 加权秩相关 | 点数 | 原权重覆盖 |
| --- | --- | --- | --- | --- | --- |
| mean logprob | EM | 0.4502313373 | 0.6160920513 | 68 | 0.9513888889 |
| mean logprob | token_F1 | 0.3999365026 | 0.5667952159 | 68 | 0.9513888889 |
| EM | 观测 admission | 0.101204452 | 0.101204452 | 68 | 0.9513888889 |
| EM | 观测 info | 0 | -8.828323053e-18 | 68 | 0.9513888889 |
| EM | 观测 revision | 0.101204452 | 0.101204452 | 68 | 0.9513888889 |
| token_F1 | 观测 admission | 0.2525640214 | 0.187948541 | 68 | 0.9513888889 |
| token_F1 | 观测 info | -0.01612355779 | -0.01125116344 | 68 | 0.9513888889 |
| token_F1 | 观测 revision | 0.2755344594 | 0.203977519 | 68 | 0.9513888889 |

秩相关按冻结定义为普通平均秩的加权 Pearson，精确同分保留平均秩。相关系数没有确认性显著性解释。

以下四组按 mean logprob 从高到低排序，各占合格原权重的 25%；跨边界的精确同分按相同比例分配。同一点可对相邻组贡献部分权重，组内点数不能相加视为独立样本。

| confidence 组 | 参与点数 | 原权重 | EM | token-F1 | 观测 P−D | 观测 P−N | 观测 N−D |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 18 | 0.2378472222 | 0.8248175182 | 0.9164709616 | 0 | 0 | 0 |
| 2 | 18 | 0.2378472222 | 0.4744525547 | 0.7234989494 | -0.05839416058 | -0.05839416058 | 0 |
| 3 | 18 | 0.2378472222 | 0.299270073 | 0.6959371874 | 0 | 0 | 0 |
| 4 | 17 | 0.2378472222 | 0.03649635036 | 0.4864873889 | 0 | 0.05839416058 | -0.05839416058 |

冻结 top-half 描述量为 G=Σ normalized_w×(g−0.5)×观测差，g 为精确同分规则下的前半权重归属。解析 Random 的 G=0。这里的 plug-in G 依赖单次续跑，不能据其符号判断总体收益或真实效用排序。

| 排序 | G_admission | G_info | G_revision | 共同点数 | 原权重 | 选择覆盖 |
| --- | --- | --- | --- | --- | --- | --- |
| confidence | -0.007299270073 | -0.01459854015 | 0.007299270073 | 68 | 0.9513888889 | 0.5 |
| menu_outside_first | -0.007299270073 | 0 | -0.007299270073 | 68 | 0.9513888889 | 0.5 |
| prediction_length_longer | -0.007299270073 | -0.01459854015 | 0.007299270073 | 68 | 0.9513888889 | 0.5 |

## 菜单与预算分层

每行均在该层的完整 D/N/P 交集内使用原权重归一；这些是条件描述，不可直接相加。draft 不在可见菜单中不等于环境反馈必然为 Nothing happens.。

| 层 | 完整点数 | 游戏数 | 原权重 | D | N | P | P−D | P−N | N−D |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| menu inside | 64 | 23 | 0.8958333333 | 0.09302325581 | 0.09302325581 | 0.09302325581 | 0 | 0 | 0 |
| menu outside | 4 | 2 | 0.05555555556 | 0.75 | 0.5 | 0.5 | -0.25 | 0 | -0.25 |
| menu unknown | 0 | 0 | 0 | — | — | — | — | — | — |
| budget b_1_10 | 16 | 12 | 0.2222222222 | 0 | 0 | 0 | 0 | 0 | 0 |
| budget b_11_20 | 24 | 15 | 0.3333333333 | 0.125 | 0.08333333333 | 0.08333333333 | -0.04166666667 | 0 | -0.04166666667 |
| budget b_21_30 | 28 | 17 | 0.3958333333 | 0.2105263158 | 0.2105263158 | 0.2105263158 | 0 | 0 | 0 |

每层准确性、动作变化、正负差及缺失分母保留于 JSON 的 `metrics.by_menu` 与 `metrics.by_budget`。

## 跨作业与逐游戏删除敏感性

跨作业分类沿实际物理组恢复出处关联 job_id 和 service_instance_id；源 draft 采集阶段不计入局部分支的跨作业比较。主分析保留全部原资格集合，敏感性只保留身份核实为 false 的状态。true、unknown 和 not_applicable 分列。

| 实际身份分类 | 点数 | 游戏数 | 原权重 |
| --- | --- | --- | --- |
| false | 67 | 24 | 0.9375 |
| true | 1 | 1 | 0.01388888889 |
| unknown | 0 | 0 | 0 |
| not_applicable | 3 | 3 | 0.04861111111 |

| 层 | 完整点数 | 游戏数 | 原权重 | D | N | P | P−D | P−N | N−D |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 主分析可用交集 | 68 | 24 | 0.9513888889 | 0.1313868613 | 0.1167883212 | 0.1167883212 | -0.01459854015 | 0 | -0.01459854015 |
| 仅 verified false | 67 | 24 | 0.9375 | 0.1333333333 | 0.1185185185 | 0.1185185185 | -0.01481481481 | 0 | -0.01481481481 |

| 关系 | 主 Pearson | 排除后 Pearson | 主秩相关 | 排除后秩相关 |
| --- | --- | --- | --- | --- |
| EM | 0.4502313373 | 0.4446425901 | 0.6160920513 | 0.6052527529 |
| token_F1 | 0.3999365026 | 0.3945533623 | 0.5667952159 | 0.555120334 |

完整的排除后准确性、三项观测差、分层、重新分箱及排序见 JSON；没有把剩余状态重新按游戏平权。

逐游戏删除时移除整局，再用剩余原权重整体归一。下表范围是敏感性描述，不是置信区间。

| 指标 | 可用均值 | 点数 | 原权重 | 删除一局的范围 | 范围不可用原因 |
| --- | --- | --- | --- | --- | --- |
| EM | 0.4087591241 | 68 | 0.9513888889 | [0.38167938931297707, 0.4274809160305343] | — |
| token_F1 | 0.7055986218 | 68 | 0.9513888889 | [0.692114589254999, 0.7370180468212315] | — |
| Y_D | 0.1313868613 | 68 | 0.9513888889 | [0.0916030534351145, 0.13740458015267176] | — |
| Y_N | 0.1167883212 | 68 | 0.9513888889 | [0.07633587786259542, 0.12213740458015267] | — |
| Y_P | 0.1167883212 | 68 | 0.9513888889 | [0.07633587786259542, 0.12213740458015267] | — |
| U_admission | -0.01459854015 | 68 | 0.9513888889 | [-0.015267175572519083, 0.0] | — |
| U_info | 0 | 68 | 0.9513888889 | [0.0, 0.0] | — |
| U_revision | -0.01459854015 | 68 | 0.9513888889 | [-0.015267175572519083, 0.0] | — |

两个终局差异状态都来自第 14 局；删除这局后，三项观测差均为零。这说明效用描述对单个游戏敏感，也说明更多同游戏状态不能当成新的独立游戏证据。

## 物理轨迹诊断与固定案例

全部物理组按真实 rollout ID 去重，以下是路径计数，不使用状态总体权重。μ 相邻重复包含第一条 μ 动作与缓存首动作的比较；最长连续重复也包含缓存首动作。

| 物理行为 | 结果 |
| --- | --- |
| 物理组 / 已执行动作 | 117 / 1397 |
| 新 μ 逻辑调用 / 已执行 μ 动作 | 1295 / 1280 |
| μ 相邻动作重复 | 277/1280 = 0.21640625 |
| μ 精确 Nothing happens. | 123/1280 = 0.09609375 |
| 最长相同动作连续段 | 20 |
| 终止 budget_exhausted | 88 |
| 终止 env_done | 14 |
| 终止 policy_failure | 15 |

新 μ 调用包括结尾策略失败调用，因而调用数可以大于已执行动作数。共享分支的失败只形成一个物理失败事件，不能按 D/N/P 引用次数重复计费或当成独立失败。上述重复和无变化反馈是路径描述，不能直接用来解释终局效用的因果机制。

- `observed_admission_positive`：合格 0 点；类别不存在，不补样。
- `observed_admission_negative`：合格 1 点；按冻结哈希选择 `15dd60d435738a0b4307159aee939a1f110d0ed3ece83f4c726cd968cce375ac:16`。
- `EM1_and_same_PD_action_or_observed_admission_zero`：合格 28 点；按冻结哈希选择 `40945f3e9214f2d475b3c80f62f107c7c8c9498b088581ed004454ba4abbd726:19`。
- `policy_failure_or_insufficient_evidence`：合格 18 点；按冻结哈希选择 `e9f431271ce0c84584a2f289359ba0b8a26da49726ec93ee6fb59de0d832ca57:1`。

固定案例从全部原 71 点的合格池选择；额外列出全部终局差异点用于核对，二者不混作案例抽样规则。

### 第 5 局 t=19 固定哈希案例

游戏：`pick_heat_then_place_in_recep-Cup-None-Fridge-23/trial_T20190908_045659_449231`。状态：`40945f3e9214f2d475b3c80f62f107c7c8c9498b088581ed004454ba4abbd726:19`；剩余预算 11。

D/N/P=0/0/0。

预测：On the coffeemachine 1, you see nothing.

D 真实首步观察：On the coffeemachine 1, you see nothing.

| 分支 | 首动作 | 结果状态 | Y |
| --- | --- | --- | --- |
| D | examine coffeemachine 1 | complete | 0 |
| N | examine countertop 1 | complete | 0 |
| P | move bowl 1 to countertop 1 | complete | 0 |

物理组 `40945f3e9214f2d475b3c80f62f107c7c8c9498b088581ed004454ba4abbd726:19/g0`，共享分支 D，终止 `budget_exhausted`，11 个已执行动作、10 次新 μ 调用。

| 步 | 阶段 | 动作 | 真实观察 | 成功 |
| --- | --- | --- | --- | --- |
| 19 | first_action | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 20 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 21 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 22 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 23 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 24 | continuation | go to fridge 1 | You arrive at fridge 1. The fridge 1 is closed. | False |
| 25 | continuation | examine coffeemachine 1 | Nothing happens. | False |
| 26 | continuation | open fridge 1 | You open the fridge 1. The fridge 1 is open. In it, you see a apple 3, a bread 2, a egg 2, a pot 2, and a potato 3. | False |
| 27 | continuation | cool bowl 1 with fridge 1 | You cool the bowl 1 using the fridge 1. | False |
| 28 | continuation | move bowl 1 to fridge 1 | You move the bowl 1 to the fridge 1. | False |
| 29 | continuation | examine coffeemachine 1 | Nothing happens. | False |

物理组 `40945f3e9214f2d475b3c80f62f107c7c8c9498b088581ed004454ba4abbd726:19/g1`，共享分支 N，终止 `budget_exhausted`，11 个已执行动作、10 次新 μ 调用。

| 步 | 阶段 | 动作 | 真实观察 | 成功 |
| --- | --- | --- | --- | --- |
| 19 | first_action | examine countertop 1 | On the countertop 1, you see a apple 2, a bread 1, a glassbottle 3, a glassbottle 2, a glassbottle 1, a saltshaker 3, and a spoon 2. | False |
| 20 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 21 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 22 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 23 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 24 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 25 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 26 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 27 | continuation | go to fridge 1 | You arrive at fridge 1. The fridge 1 is closed. | False |
| 28 | continuation | examine coffeemachine 1 | Nothing happens. | False |
| 29 | continuation | open fridge 1 | You open the fridge 1. The fridge 1 is open. In it, you see a apple 3, a bread 2, a egg 2, a pot 2, and a potato 3. | False |

物理组 `40945f3e9214f2d475b3c80f62f107c7c8c9498b088581ed004454ba4abbd726:19/g2`，共享分支 P，终止 `budget_exhausted`，11 个已执行动作、10 次新 μ 调用。

| 步 | 阶段 | 动作 | 真实观察 | 成功 |
| --- | --- | --- | --- | --- |
| 19 | first_action | move bowl 1 to countertop 1 | You move the bowl 1 to the countertop 1. | False |
| 20 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 21 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 22 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 23 | continuation | examine countertop 1 | On the countertop 1, you see a apple 2, a bowl 1, a bread 1, a glassbottle 3, a glassbottle 2, a glassbottle 1, a saltshaker 3, and a spoon 2. | False |
| 24 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 25 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 26 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 27 | continuation | examine coffeemachine 1 | On the coffeemachine 1, you see nothing. | False |
| 28 | continuation | go to fridge 1 | You arrive at fridge 1. The fridge 1 is closed. | False |
| 29 | continuation | examine coffeemachine 1 | Nothing happens. | False |

### 第 14 局 t=10 全部差异点补充说明

游戏：`pick_clean_then_place_in_recep-DishSponge-None-CounterTop-427/trial_T20190909_010951_843989`。状态：`15dd60d435738a0b4307159aee939a1f110d0ed3ece83f4c726cd968cce375ac:10`；剩余预算 20。

D/N/P=1/0/1。

预测：The dishsponge 4 is now on countertop 1.

D 真实首步观察：Nothing happens.

| 分支 | 首动作 | 结果状态 | Y |
| --- | --- | --- | --- |
| D | move dishsponge 4 to countertop 1 | complete | 1 |
| N | — | policy_failed | 0 |
| P | move dishsponge 4 to sinkbasin 1 | complete | 1 |

物理组 `15dd60d435738a0b4307159aee939a1f110d0ed3ece83f4c726cd968cce375ac:10/g0`，共享分支 D，终止 `env_done`，15 个已执行动作、14 次新 μ 调用。

| 步 | 阶段 | 动作 | 真实观察 | 成功 |
| --- | --- | --- | --- | --- |
| 10 | first_action | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 11 | continuation | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 12 | continuation | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 13 | continuation | look | You are facing the sinkbasin 1. Next to it, you see nothing. | False |
| 14 | continuation | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 15 | continuation | look | You are facing the sinkbasin 1. Next to it, you see nothing. | False |
| 16 | continuation | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 17 | continuation | move dishsponge 4 to sinkbasin 1 | You move the dishsponge 4 to the sinkbasin 1. | False |
| 18 | continuation | go to countertop 1 | You arrive at countertop 1. On the countertop 1, you see a candle 2, a cloth 2, a spraybottle 2, a spraybottle 1, a tissuebox 1, and a toiletpaper 1. | False |
| 19 | continuation | go to sinkbasin 1 | You arrive at sinkbasin 1. On the sinkbasin 1, you see a dishsponge 4. | False |
| 20 | continuation | take dishsponge 4 from sinkbasin 1 | You pick up the dishsponge 4 from the sinkbasin 1. | False |
| 21 | continuation | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 22 | continuation | look | You are facing the sinkbasin 1. Next to it, you see nothing. | False |
| 23 | continuation | go to countertop 1 | You arrive at countertop 1. On the countertop 1, you see a candle 2, a cloth 2, a spraybottle 2, a spraybottle 1, a tissuebox 1, and a toiletpaper 1. | False |
| 24 | continuation | move dishsponge 4 to countertop 1 | You move the dishsponge 4 to the countertop 1. | True |

物理组 `15dd60d435738a0b4307159aee939a1f110d0ed3ece83f4c726cd968cce375ac:10/g1`，共享分支 P，终止 `env_done`，9 个已执行动作、8 次新 μ 调用。

| 步 | 阶段 | 动作 | 真实观察 | 成功 |
| --- | --- | --- | --- | --- |
| 10 | first_action | move dishsponge 4 to sinkbasin 1 | You move the dishsponge 4 to the sinkbasin 1. | False |
| 11 | continuation | take dishsponge 4 from sinkbasin 1 | You pick up the dishsponge 4 from the sinkbasin 1. | False |
| 12 | continuation | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 13 | continuation | examine dishsponge 4 | This is a clean dishsponge 4. | False |
| 14 | continuation | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 15 | continuation | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 16 | continuation | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 17 | continuation | go to countertop 1 | You arrive at countertop 1. On the countertop 1, you see a candle 2, a cloth 2, a spraybottle 2, a spraybottle 1, a tissuebox 1, and a toiletpaper 1. | False |
| 18 | continuation | move dishsponge 4 to countertop 1 | You move the dishsponge 4 to the countertop 1. | True |

### 第 14 局 t=16 固定哈希案例

游戏：`pick_clean_then_place_in_recep-DishSponge-None-CounterTop-427/trial_T20190909_010951_843989`。状态：`15dd60d435738a0b4307159aee939a1f110d0ed3ece83f4c726cd968cce375ac:16`；剩余预算 14。

D/N/P=1/1/0。

预测：You are facing the sinkbasin 1. Next to it, you see nothing. On the countertop 1, you now see a candle 2, a cloth 2, a spraybottle 2, a spraybottle 1, a tissuebox 1, a toiletpaper 1, and a dishsponge 4.

D 真实首步观察：Nothing happens.

| 分支 | 首动作 | 结果状态 | Y |
| --- | --- | --- | --- |
| D | move dishsponge 4 to countertop 1 | complete | 1 |
| N | go to countertop 1 | complete | 1 |
| P | move dishsponge 4 to sinkbasin 1 | complete | 0 |

物理组 `15dd60d435738a0b4307159aee939a1f110d0ed3ece83f4c726cd968cce375ac:16/g1`，共享分支 N，终止 `env_done`，5 个已执行动作、4 次新 μ 调用。

| 步 | 阶段 | 动作 | 真实观察 | 成功 |
| --- | --- | --- | --- | --- |
| 16 | first_action | go to countertop 1 | You arrive at countertop 1. On the countertop 1, you see a candle 2, a cloth 2, a spraybottle 2, a spraybottle 1, a tissuebox 1, and a toiletpaper 1. | False |
| 17 | continuation | look | You are facing the countertop 1. Next to it, you see nothing. | False |
| 18 | continuation | look | You are facing the countertop 1. Next to it, you see nothing. | False |
| 19 | continuation | examine dishsponge 4 | This is a clean dishsponge 4. | False |
| 20 | continuation | move dishsponge 4 to countertop 1 | You move the dishsponge 4 to the countertop 1. | True |

物理组 `15dd60d435738a0b4307159aee939a1f110d0ed3ece83f4c726cd968cce375ac:16/g2`，共享分支 P，终止 `budget_exhausted`，14 个已执行动作、13 次新 μ 调用。

| 步 | 阶段 | 动作 | 真实观察 | 成功 |
| --- | --- | --- | --- | --- |
| 16 | first_action | move dishsponge 4 to sinkbasin 1 | You move the dishsponge 4 to the sinkbasin 1. | False |
| 17 | continuation | go to countertop 1 | You arrive at countertop 1. On the countertop 1, you see a candle 2, a cloth 2, a spraybottle 2, a spraybottle 1, a tissuebox 1, and a toiletpaper 1. | False |
| 18 | continuation | go to countertop 1 | Nothing happens. | False |
| 19 | continuation | go to countertop 1 | Nothing happens. | False |
| 20 | continuation | go to countertop 1 | Nothing happens. | False |
| 21 | continuation | go to sinkbasin 1 | You arrive at sinkbasin 1. On the sinkbasin 1, you see a dishsponge 4. | False |
| 22 | continuation | go to countertop 1 | You arrive at countertop 1. On the countertop 1, you see a candle 2, a cloth 2, a spraybottle 2, a spraybottle 1, a tissuebox 1, and a toiletpaper 1. | False |
| 23 | continuation | go to sinkbasin 1 | You arrive at sinkbasin 1. On the sinkbasin 1, you see a dishsponge 4. | False |
| 24 | continuation | go to countertop 1 | You arrive at countertop 1. On the countertop 1, you see a candle 2, a cloth 2, a spraybottle 2, a spraybottle 1, a tissuebox 1, and a toiletpaper 1. | False |
| 25 | continuation | go to sinkbasin 1 | You arrive at sinkbasin 1. On the sinkbasin 1, you see a dishsponge 4. | False |
| 26 | continuation | go to countertop 1 | You arrive at countertop 1. On the countertop 1, you see a candle 2, a cloth 2, a spraybottle 2, a spraybottle 1, a tissuebox 1, and a toiletpaper 1. | False |
| 27 | continuation | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 28 | continuation | look | You are facing the countertop 1. Next to it, you see nothing. | False |
| 29 | continuation | look | You are facing the countertop 1. Next to it, you see nothing. | False |

物理组 `15dd60d435738a0b4307159aee939a1f110d0ed3ece83f4c726cd968cce375ac:16/g0`，共享分支 D，终止 `env_done`，9 个已执行动作、8 次新 μ 调用。

| 步 | 阶段 | 动作 | 真实观察 | 成功 |
| --- | --- | --- | --- | --- |
| 16 | first_action | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 17 | continuation | move dishsponge 4 to sinkbasin 1 | You move the dishsponge 4 to the sinkbasin 1. | False |
| 18 | continuation | go to countertop 1 | You arrive at countertop 1. On the countertop 1, you see a candle 2, a cloth 2, a spraybottle 2, a spraybottle 1, a tissuebox 1, and a toiletpaper 1. | False |
| 19 | continuation | go to sinkbasin 1 | You arrive at sinkbasin 1. On the sinkbasin 1, you see a dishsponge 4. | False |
| 20 | continuation | take dishsponge 4 from sinkbasin 1 | You pick up the dishsponge 4 from the sinkbasin 1. | False |
| 21 | continuation | move dishsponge 4 to countertop 1 | Nothing happens. | False |
| 22 | continuation | look | You are facing the sinkbasin 1. Next to it, you see nothing. | False |
| 23 | continuation | go to countertop 1 | You arrive at countertop 1. On the countertop 1, you see a candle 2, a cloth 2, a spraybottle 2, a spraybottle 1, a tissuebox 1, and a toiletpaper 1. | False |
| 24 | continuation | move dishsponge 4 to countertop 1 | You move the dishsponge 4 to the countertop 1. | True |

### 第 19 局 t=1 固定哈希案例

游戏：`pick_two_obj_and_place-Pencil-None-CoffeeTable-229/trial_T20190910_231706_006365`。状态：`e9f431271ce0c84584a2f289359ba0b8a26da49726ec93ee6fb59de0d832ca57:1`；剩余预算 29。

D/N/P=0/0/0。

预测：Drawer 1 is now open.

D 真实首步观察：You open the drawer 1. The drawer 1 is open. In it, you see nothing.

| 分支 | 首动作 | 结果状态 | Y |
| --- | --- | --- | --- |
| D | open drawer 1 | policy_failed | 0 |
| N | open drawer 1 | policy_failed | 0 |
| P | open drawer 1 | policy_failed | 0 |

物理组 `e9f431271ce0c84584a2f289359ba0b8a26da49726ec93ee6fb59de0d832ca57:1/g0`，共享分支 D, N, P，终止 `policy_failure`，2 个已执行动作、2 次新 μ 调用。

| 步 | 阶段 | 动作 | 真实观察 | 成功 |
| --- | --- | --- | --- | --- |
| 1 | first_action | open drawer 1 | You open the drawer 1. The drawer 1 is open. In it, you see nothing. | False |
| 2 | continuation | go to sidetable 1 | You arrive at sidetable 1. On the sidetable 1, you see a houseplant 1, a pencil 2, and a pencil 1. | False |

第 14 局 t=10 的 N 首动作不可解析，因此 N=0，P−N=+1；D 与 P 都成功，P−D=0。t=16 的 P 预算耗尽，而 D/N 成功。两点 P 首动作均把 dishsponge 放入 sinkbasin，故动作名称本身不是已确认的失败原因。

## 成本与未知范围

成本只覆盖当前 campaign 的 15 次尝试，既保留接受样本，也保留旧失败和未完成片段。逐调用按原日志文件与 call ID 去重；共享分支不会重复计费。下面先列原接受账本，再列实际审计记录，二者口径分别保留。

| 账本范围 | 记录逻辑调用 | observed HTTP charged | 保守 charged 逻辑调用 | 保守 charged HTTP | 观测 allocation 秒 | charged allocation 秒 |
| --- | --- | --- | --- | --- | --- | --- |
| D0-var 13 次尝试 | 1613 | 1615 | 8946 | 16556 | 13883 | 42782 |
| 源阶段 2 次尝试 | 586 | 586 | 1306 | 2036 | 5700 | 16234 |
| campaign 合计 15 次 | 2199 | 2201 | 10252 | 18592 | 19583 | 59016 |
| 其中 10 个接受批次 | 1336 | 1336 | 1336 | 1336 | 10382 | 10382 |

这些集合互相包含，不可逐行相加。charged allocation 是保守预算扣额，不是 GPU 忙碌时间。

### 真实逐调用记录

| 调用归属 | request starts | 完整终端 | 已保存 HTTP 尝试 | 已知 prompt tokens | 已知 completion tokens | 已知请求耗时秒 | 缺终端 starts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 后端验收 | 130 | 130 | 130 | 23153 | 5213 | 159.8224361 | 0 |
| 局部 N/WM/P 与 μ | 1504 | 1503 | 1503 | 1361960 | 129948 | 2905.967753 | 1 |
| 源轨迹 | 566 | 566 | 566 | 443706 | 45195 | 1055.791369 | 0 |

合计 2200 条 request_start、2199 条完整终端记录、2199 条已保存 HTTP 尝试。已知 prompt/completion tokens 为 1828819/180356，已知请求耗时合计 4121.581558 秒。这些是已保存记录的已知小计；未知调用的 HTTP、tokens、耗时和结果保持 null，不能当成完整实际成本。

后端验收共 130 次，其中源阶段 20 次、D0-var 阶段 110 次。因此账本源阶段 586 次包含 566 次源轨迹调用和 20 次验收。10 个完整接受批次的 1,336 次调用分为 100 次验收与 1,236 次采集。

| 阶段 | request starts | 完整终端 | 可见 HTTP 尝试 | 策略内容失败 | 缺终端 starts |
| --- | --- | --- | --- | --- | --- |
| acceptance/backend_acceptance | 130 | 130 | 130 | 0 | 0 |
| local/continuation | 1300 | 1299 | 1299 | 15 | 1 |
| local/first_action | 204 | 204 | 204 | 1 | 0 |
| source/source_episode | 566 | 566 | 566 | 5 | 0 |

局部 first_action 共 204 次，即 68 个局部事件各有 N、WM、P 调用。全部局部 continuation 有 1,300 条开始记录，而最终接受的 117 物理组只有 1,295 次新 μ 调用；差额属于旧失败或未完成片段，不能加入最终轨迹步数。

| 最终接受物理组的时间记录 | 已知合计秒 | 已知组数 | 未知组数 |
| --- | --- | --- | --- |
| rollout elapsed | 6740.871809 | 117 | 0 |
| 恢复 wall | 1998.37285 | 117 | 0 |
| 恢复 cleanup | 0.003177619981 | 117 | 0 |
| 恢复 total | 1998.376028 | 117 | 0 |

这里仅统计最终接受的 117 个物理组，不含旧中断或失效片段。恢复 total 已含恢复 wall 与 cleanup，build/reset/replay/validation 子项另留 JSON，不把这些重叠时间相加。这些物理组耗时也不能代替完整 runner 或作业 wall；跨已接受、恢复与停止尝试的完整 runner wall 未形成统一输入，保持 null。

### 935310 的未知调用与账本对照

935310 原审计有 278 条唯一 request_start、277 条完整终端和 277 条已保存 HTTP 尝试；最终账本保留 recorded logical=277、observed http_attempts_charged=279。多出的请求开始记录没有终端，实际 HTTP 次数、usage 和结果未知。HTTP 的 2 个计费单位差额是保守会计口径，不能据此断言发生了两次真实 HTTP 请求。request_start 本身也不证明请求已到达服务器。

因此当前 campaign 的真实开始记录为 2,200，而账本记录逻辑调用为 2,199；已保存 HTTP 尝试为 2,199，而账本 observed HTTP charged 为 2,201。原账本不改，未知 start 不删。这条旧中断片段中的调用不纳入最终接受物理组的新 μ 调用数。

### 失败与成本覆盖

逐调用记录中已观测策略内容失败为 21 次，其中源轨迹 5 次、局部 16 次。源阶段 5 次是调用层失败，不等于原预选点中的 3 个源 draft 失败。D0-var 停止线另将 1 次未知保守计入，形成 17/30；账本 charged 中的 95 个策略失败预算单位不是 95 次观测失败。已有终端记录未出现 request_error，但 1 条缺终端记录的结果未知，不能据此声称没有技术缺失。

计数未完整的作业为 934277、935310、943125、944500。其中 943125 的 stage 原件未在固定归档位置找到，最终账本记零调用；保留此覆盖缺口，不构造空审计冒充已核实零成本。源阶段的后端验收报告通过自身 seal 与 audit artifact SHA 核对；最终账本只直接绑定 stage result，没有独立绑定这两份 backend report。

逐调用 usage、耗时及错误分类、每次尝试的账本差额、全部来源 SHA 见 JSON `costs` 和 `d0_cost_evidence.json`。请求耗时、恢复、runner wall 和 allocation 有重叠，不能相加；本报告不把它们换算成货币价格或完整 GPU 成本。

## 冻结 N/P 候选

候选由冻结两遍哈希选择器生成，完整选择记录见 JSON `np_candidates`。要求 6 个严格异 D 首动作物理组、至少 4 游戏、每游戏最多 2 组，且每组至少 10 次新 μ 调用。策略失败结尾的合格长尾组保留，候选选择不代表复测通过。

选择状态：`ready`。全 117 组中，严格资格且满足长度阈值的候选为 26 组、12 游戏；最终选择 6 组、6 游戏，合计 83 次原新 μ 调用。

| 顺序 | 游戏 | 状态步 | 分支 | 首动作 | 新 μ 调用 | 结果状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | pick_two_obj_and_place-KeyChain-None-Dresser-318/trial_T20190910_122758_510336 | 3 | P | go to drawer 1 | 17 | policy_failed |
| 2 | pick_clean_then_place_in_recep-Cloth-None-Toilet-426/trial_T20190910_045221_427487 | 19 | N=P | take cloth 3 from toilet 1 | 10 | complete |
| 3 | pick_cool_then_place_in_recep-Pan-None-DiningTable-23/trial_T20190909_005731_236253 | 10 | N=P | go to cabinet 4 | 19 | complete |
| 4 | pick_two_obj_and_place-CellPhone-None-Bed-322/trial_T20190906_181156_010327 | 18 | N | go to sidetable 2 | 11 | complete |
| 5 | pick_two_obj_and_place-Pen-None-SideTable-330/trial_T20190908_121048_491026 | 12 | N | examine drawer 5 | 16 | policy_failed |
| 6 | pick_heat_then_place_in_recep-Cup-None-Fridge-23/trial_T20190908_045659_449231 | 19 | N | examine countertop 1 | 10 | complete |

这是按冻结规则选择的长尾工程抽查，不是代表性样本或通过复现的证据。实际 N/P 作业尚未启动，当前交付到候选清单为止。

## 结论与后续边界

本配置的 WM confidence 能在 D0 中区分部分文本匹配准确性，首动作也经常因再次决策或预测而改变。这些变化只在同一游戏的两个状态形成终局差异；P−N 的正差包含一次 N 格式失败，P−D 没有正差。现有证据支持继续做有界 N/P 复核，尚不足以证明 confidence 无用、真实效用为零或整局 Always 无用。低成功率与后续 μ 可能影响差异显现，但本次轨迹观察不能确认这些机制。

后续 N/P 实际抽查与 D1/E 的资格、样本量和分析方案是独立决定。本报告沿用现有 4B 数据，不把未核实的 32B NPU 配置混入同配置结论。

## 复算与来源

在仓库根目录使用 Python 3.10+ 标准库运行：

```sh
python -B tools/build_d0_report.py --out gpu_analysis/generated/d0_report_new.json
```

输出 JSON 和同名 Markdown；已有文件不会覆盖。全部分析只读取本仓库便携数据，普通复算无需原归档、SSH、GPU 或模型服务。重新导出逐调用、身份和候选证据才需要原归档。输入与实际分析代码的 SHA-256 记录在 JSON 中。

数据内容 SHA-256：`9767747c57cd434f31bc7d93d0153048b6b9e79be16dde5f44138be2f6074a18`。

原 71 点快照、117 组摘要、冻结分析模块及指标字节保持；新增证据是从已有原件导出的派生数据。真实逐调用成本的已知部分与不可恢复部分分开，身份绑定是对已接受原件的本地核查，不是新的服务运行验收。

| 输入 | 字节数 | SHA-256 |
| --- | --- | --- |
| d0_snapshot.json | 1237000 | `83a434c2eaac1bb8b6ad90b6d2b5c83716cfd24ea96411b7e43321f59bf0c82d` |
| d0_rollout_summaries.json | 668049 | `db10811e9c4ea784d9853bdc187f7efa162a71345dbf876bce842391c73355c4` |
| d0_identity_evidence.json | 376737 | `f2c71959d9684a5c99f0cb7ee60dc615f2e3e95f32e5d5813e9a44dec00fb699` |
| d0_cost_evidence.json | 6018204 | `e990974610020249ab0f2f25f4bfb7d9c9357730031c755f6a75ac5bdc22b109` |
| final_accounting_summary.json | 16592 | `56e0813feaeffa9bbb8bc298196b252ed62b515beaf04463aff16704ba4d98d0` |
| d0_np_evidence.json | 237488 | `35246b59c3a2b7dde1fea1bb33422d541a5586f2ea528e8ec77b12ff89439d45` |

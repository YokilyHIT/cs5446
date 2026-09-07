# Stage 0：基线成功率测量

**目的**：规范 §39 规定，当 Qwen3-4B 成功率太低时，按固定顺序检查三件事再补救。
本轮测量是为了用数据（而不是感觉）判断该走哪一条，并把结论钉在纸面上。

**为什么必须先做**：在此之前关于"模型行不行"的证据全是极小样本且互相矛盾
（5 个 episode 是 1/5、2 个 episode 是 1/2）。而"要不要改实验设计"完全取决于这个数——
如果真实成功率本来就有 25% 以上，任何改动都是多余的干预。

## 方法

- 从 `eval_in_distribution`（valid_seen，140 个任务）里**等距抽 30 个**，
  与 `evaluate_topk_vs_all.py::_select_eval_subset` 同一规则，完全确定性，六类任务都覆盖到
- seed=13，无记忆、无教训，走的是 `collect_failures` / `collect_decision_points` 完全相同的
  rollout 路径
- 每个 episode 额外记录"打转"证据：某个动作**连续**重复的最长次数、
  出现最多的动作及次数、用到的不同动作种类数
- 复现命令：见 `../REPRODUCE.md` 第 9 步；脚本 `../tools/measure_baseline.py`

## 结果

| | 规范提示词<br>30 步 | 规范提示词<br>50 步 | AdaMEM `<think>`<br>30 步 |
|---|---|---|---|
| **成功率** | 3/30 = 10.0% | 4/30 = 13.3% | **8/30 = 26.7%** |
| 打转 episode（同一动作连续≥5次） | 7/30 (23%) | 8/30 (27%) | **3/30 (10%)** |
| 强制动作率 | 0.0% | 0.0% | 0.0% |
| 平均步数 | 27.9 | 45.4 | 24.9 |
| 模型调用次数 | 838 | 1361 | 748 步 × 2 次调用 |
| 成功 episode 用了几步 | 5, 11, 12 | 5, 11, 12, 33 | 4, 5, 6, 8, 8, 13, 14, 30 |

分任务类型：

| task_type | spec30 | spec50 | adamem30 |
|---|---|---|---|
| `pick_and_place_simple` | 0/8 | 1/8 | **4/8** |
| `pick_heat_then_place_in_recep` | 0/3 | 0/3 | **2/3** |
| `look_at_obj_in_light` | 1/3 | 1/3 | 1/3 |
| `pick_clean_then_place_in_recep` | 1/6 | 1/6 | 1/6 |
| `pick_cool_then_place_in_recep` | 1/5 | 1/5 | 0/5 |
| `pick_two_obj_and_place` | 0/5 | 0/5 | 0/5 |

原始数据：`baseline_spec30.jsonl` / `baseline_spec50.jsonl` / `baseline_adamem30.jsonl`
（每行一个 episode）。

## §39 三条检查的结论

**① 提示词是否要求从合法动作里选 —— 已满足。**
三组的强制动作率都是 0.0%。这是通过 vLLM `guided_choice` 约束解码达成的；
在加约束之前实测是 **51.3%**（详见 `../CHANGES_AND_KNOWN_ISSUES.md` 的 VALID-1）。

**② 步数上限是否太低 —— 用数据排除。**
30 → 50 步，多花 62% 算力（838 → 1361 次调用），只多换来 **1 个**成功。更有说服力的是细节：

- 成功的 episode 只用了 **5 / 11 / 12 步**，根本碰不到 30 的上限
- 失败但**不打转**的 20 个 episode，30 步里只用了**中位数 12 种**不同动作，
  最常用的那个动作平均重复 **5.8 次**

也就是说它不是在系统地翻 30 个柜子找东西，而是在十来个动作之间来回兜圈。
给一个在兜圈的 agent 更多步数，它只会兜更多圈。

**③ 复用 AdaMEM 官方 no-memory 提示词 —— 生效。**
成功率 10.0% → 26.7%（2.7 倍），打转率 23% → 10%，且**没有靠加步数**（平均步数反而降了）。

改善集中在**需要多阶段规划**的任务上：`pick_and_place_simple` 0/8 → 4/8，
`pick_heat_then_place` 0/3 → 2/3。这与诊断一致——ALFWorld 的任务有套路
（要用台灯照东西得**先拿起来**再 `use desklamp`；要洗东西得先拿再去水池），
规范 §5.1 那版提示词是"看状态 → 直接吐动作"，中间没有任何思考余地，小模型悟不出来。

7 个卡死 episode 卡住的动作也印证了这一点，全是"再看一眼"类：

```
连续 29 次  examine desk 1
连续  8 次  look
连续  7 次  examine drawer 1
连续  7 次  examine cabinet 1
连续  5 次  help
```

换成 AdaMEM 提示词后，那个连续 29 步卡在 `examine desk 1` 的任务，
**第 3 步就找到了关键动作 `take bowl 1 from desk 1`**（此前从未找到过）。

## 决策

**通过 25% 门槛，可以进入正式实验。**

`sampling.prompt_style` 的默认值**仍然是 `"spec"`**（未擅自改动）。
要用 AdaMEM 提示词需在 `preexperiments/configs/preexperiment.yaml` 里显式设为
`"adamem_think"`，或用 `--prompt_style` 覆盖。

## 三点必须写进最终报告的说明

1. **适用范围变了。** 用 `adamem_think` 时，测出的 Δ 是"教训对一个**会推理的** agent 的价值"，
   不是"对规范 §5.1 那个裸 agent 的价值"。它对所有条件一视同仁
   （有教训/无教训、base/foresight），不偏袒任何一方，但结论的适用对象变了。

2. **仍有两类任务全军覆没**：`pick_cool_then_place`（0/5）和 `pick_two_obj_and_place`（0/5），
   都在 30 步耗尽。这两类天然更长。

3. **`<think>` 必须预填。** 这个模型面对"请在 `<think></think>` 里推理"的提示词会
   **立刻输出 EOS**（空回复、1 个 token、finish_reason=stop），温度 0.2 和 0.7 都一样。
   必须预填 `<think>` 让它接着写。这是模型的怪癖，不是 vLLM/Ascend 的问题。

## 顺带发现的两个工程问题（已修）

- **全程串行，vLLM 的批处理完全没用上。** 实测吞吐：单路 37 tok/s → 8 路 273 → **16 路 513
  （14 倍）**，而单请求延迟几乎不变。30 个 episode 从串行预估 3 小时降到 16 分钟。
- **并发暴露了 TextWorld 两处线程不安全**，报错都指向完全无关的地方：
  `fast_downward` 的 PDDL→SAS 翻译器（`KeyError: (2, 0)`）、
  文本生成的模块级 tatsu 解析器（`IndexError: pop from empty list`）。
  已用一把 `_ENV_LOCK` 串行化所有进入 TextWorld 的调用。

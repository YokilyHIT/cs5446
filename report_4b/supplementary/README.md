# Step 0c 与方向 B：补充测量的既有来源

本目录支持主报告第 4.6 节，包含实验答案。这里的两个脚本和两份输出逐字节复制自 2026-10-19 已通过增量复验的离线材料；2026-10-20 的报告整合只复用它们，没有重新运行脚本、实验或统计分析，也没有更改本组冻结的 D0/E 数据。

队友数据固定为团队仓库 master 提交 [`a26e7e45c88716efc38279dd0d7af68ddba3826d`](https://github.com/YokilyHIT/cs5446/tree/a26e7e45c88716efc38279dd0d7af68ddba3826d)。输入在该提交的 `alfworld-preexp-npu/outputs/react_study/` 下：

- [Step 0c](https://github.com/YokilyHIT/cs5446/tree/a26e7e45c88716efc38279dd0d7af68ddba3826d/alfworld-preexp-npu/outputs/react_study/step0_protocol_v2_measurement)：`raw/branch_points.jsonl`、`raw/branch_k.shard*.jsonl`、开发游戏清单，以及 `tables/branch_k_unbiased_points.csv`、`tables/per_task_per_rep_dev600.csv`、`tables/per_task_dev600_v2.csv`。
- [方向 B](https://github.com/YokilyHIT/cs5446/tree/a26e7e45c88716efc38279dd0d7af68ddba3826d/alfworld-preexp-npu/outputs/react_study/dirB_planner_uncertainty)：`raw/signals.jsonl` 和 `tables/offline_signal_screen.json`，复用 Step 0c 的效用标签。

## 文件与口径

| 文件 | 内容与适用范围 |
| --- | --- |
| [check_unbiased.py](check_unbiased.py) | 原有子集核对和 D/N/P 再分析脚本；按游戏聚类 bootstrap 10,000 次，95% 百分位区间；状态均值等权，随机数种子 2026。 |
| [check_unbiased.txt](check_unbiased.txt) | 已验收输出。第 17 行起是 127 点／81 游戏的结果；P−N、0.580／0.505 的准确性相关和 changed-state 相关来自这份复核再分析，不是原 README 中已有的全部数字。 |
| [recheck_dirB_screen.py](recheck_dirB_screen.py) | 原有离线信号复核脚本；按公开方向把低 logprob／低 confidence 取反号，目标为 WM 相对 base 的 PR 效用。 |
| [dirB_screen.txt](dirB_screen.txt) | 已验收输出。主报告仅选录 127 点子集。文件也保留全部 200 点的旧标签与两项修正对照，不能将其混作 127 点结果。 |

Step 0c 的原 README 对 P−D 给出区间 `[−0.042, +0.025]`；既有复核脚本给出 `[−0.043, +0.023]`。主报告统一引用后者，并明确来源，不将 bootstrap 端点说成逐字一致。原 `branch_k_summary` 的 `solvable` 组有 160 点；本报告不借用其 confidence/coverage 结果替代 127 点统计。原代码中的“unbiased”仅指通过 rep1 定义可解、减少对 rep0 轨迹未来结果的选择，不表示对全部游戏或状态无偏。

方向 B 的 `U>0`、`U<0` AUROC 是各自对其他所有状态的分类，不是只在非零状态上区分帮助与伤害。浮点残差（point 76）和合法伪动作（point 166）两项修正不影响 127 点子集。完整输出保留更多检查量，但主报告未选录的 G、超额方差等量不新增为报告结论。

两份输出在已有增量复验中与原保留结果逐字节一致；这不是新的盲复验。Step 0c 子集还用于门控训练，方向 B 又在同批标签上筛选信号，因此本目录提供开发数据的探索性再分析，不能替代 D1。队友的原 README 中更强的结论不随链接自动成为本报告的结论。

## 复算方式（供读者使用，本轮未执行）

在另一个 checkout 中检出上述固定 master 提交，例如放在当前仓库旁的 `../cs5446-master/`。从本报告所在仓库根目录运行：

```powershell
python -B report_4b/supplementary/check_unbiased.py ../cs5446-master/alfworld-preexp-npu/outputs/react_study/step0_protocol_v2_measurement
python -B report_4b/supplementary/recheck_dirB_screen.py ../cs5446-master/alfworld-preexp-npu/outputs/react_study
```

已有逐字节复验使用 Python 3.10.21、NumPy 2.2.6、SciPy 1.15.3。脚本只读取输入并向终端打印；若保存新输出，请使用新文件名，保留这里的既有输出。跨库版本的文本格式或 bootstrap 结果应单独核对，不能直接覆盖已有文件。

## 复制完整性：SHA-256

| 文件 | SHA-256 |
| --- | --- |
| check_unbiased.py | `6aef19ce18bc8714c6267a3b16a2cc1e4d886c5347b3c12e650fade23af4d551` |
| check_unbiased.txt | `d4c6b94022a92175a1ba0e9cac9642edb41bd5c7f35c735d3b385837b0beb758` |
| recheck_dirB_screen.py | `277f9aba00f744f1d12a3e4fdc2bd70f00790e1fe58341a90881557f8b3604a8` |
| dirB_screen.txt | `fac1e4344c019524bc1ac06b27c30ddeec439cb7ca7ac77d48f0555c5c6fba86` |

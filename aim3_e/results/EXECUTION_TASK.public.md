# 执行任务：Aim 3 E 评估 v1.1 冻结与运行

> 交给执行 agent。只依据本文件和其中列出的文件工作，不需要阅读聊天记录或 `research_progress/` 里其他的 review、handoff 文档。按顺序执行；遇到"停止条件"就停下来报告，不要自行变通。

## 0. 背景（一段话）

CS5446 项目 Aim 3：在 ALFWorld 的 134 局 unseen 游戏（E）上，比较 Always（每步用世界模型预测再决策）、no_info（再决策但不给预测）、none（不再决策）三臂的单次成功率 SR@30。主对比为 Always − no_info。

方法已在 v1 冻结：`research_progress/2026-10-18-aim3-e-evaluation/`，`FREEZE.json` 的 sha256 为 `cc072df5aec0a78bcc2ed30ee8b79776d6fcbd1ab151f8f6ef5afedf43ee61c9`。review 发现 v1 的分片超时余量只有约 30%，而温度 0 下重跑会停在同一位置（详见 `research_progress/2026-10-18-aim3-e-review/FREEZE_SUMMARY.md` 的 F1）。所以先做 v1.1，只改运行参数，不改分析，再运行 E。

## 1. 授权范围与禁止事项

用户交付本文件，即授权以下范围内的操作：

- 在本地新建 v1.1 执行包和本运行目录，运行本地测试与分析脚本；
- 通过与作业 967880 相同的 SSH 访问，在集群上新建目录、上传文件、提交本文件规定的 E 作业（每片最多 2 个 attempt）、查看状态、打包并下载结果；
- 恢复冒烟目录中的 checker（第 3 步）。

**禁止：**

- 修改 v1 执行包的任何文件，或在 v1.1 冻结后再改它；
- 修改 planner、prompt、解析器、模型配置或 74 个源码文件；
- 替换游戏、按结果挑选 attempt、拼接两次 attempt、提交第三个 attempt；
- 因 policy failure 或 C7 未覆盖而重跑；
- 在合并分析完成前计算或报告效应，或依据中途看到的结果改变任何决定；
- 做 `EVALUATION_PLAN.md` 规定以外的分析；
- 发送 `OWNER_NOTICE.md` 或任何消息给负责人、队友或外部渠道；
- `git push`、提交到团队仓库、删除集群上的任何证据。

超出以上范围的操作，先问用户。

## 2. 固定事实

| 项目 | 值 |
|---|---|
| 本地仓库 | `<LOCAL_REPO>` |
| 本地 Python | `<LOCAL_CONDA>/envs/CS5446/python.exe` |
| 本地认证代码 | `<仓库>/alfworld-preexp-npu`（参与认证的文件与集群包一致） |
| v1 执行包 | `<仓库>/research_progress/2026-10-18-aim3-e-evaluation/` |
| v1.1 执行包（新建） | `<仓库>/research_progress/2026-10-18-aim3-e-evaluation-v1.1/` |
| 本运行目录 | `<仓库>/research_progress/2026-10-18-aim3-e-run/`（本文件所在处） |
| 集群 Python | `<CLUSTER_VENV>/bin/python` |
| 集群上已核对的 74 个源码文件 | `<CLUSTER_PROJECT>/aim3-smoke-20261019-frozen/` |
| 源码清单 sha256 | `0d8a589e8b5c6174309e438600f85f8c01ed2402c8de64ba79468a7f9759d14b` |
| E 名单 sha256（`e_games.json`） | `81dfc32c29d917c62e562b9c2d3a5a7cb655e4047112a7f302f0a328821d78d3` |
| 冒烟实测 | 每步 always 4.47 秒、no_info 3.23 秒、none 1.42 秒；满 30 步每局三臂约 273 秒 |

## 3. 先做：恢复冒烟 checker（独立的小事）

冒烟目录 `research_progress/2026-10-18-aim3-gpu-smoke/check_smoke.py` 在冒烟验收后被原地替换成了 E 版本（sha256 `75becf60…a5d`）。冒烟时实际用的版本仍在集群上。

1. 下载 `<CLUSTER_PROJECT>/aim3-smoke-20261019-frozen/plan/check_smoke.py` 到本运行目录下的 `smoke-checker/check_smoke.py`，记下 sha256。
2. 用它复算冒烟：
   ```powershell
   & '<LOCAL_CONDA>/envs/CS5446/python.exe' -B <本运行目录>/smoke-checker/check_smoke.py `
     --code-root <仓库>/alfworld-preexp-npu `
     --output-root <仓库>/research_progress/2026-10-19-aim3-gpu-smoke-results/alfworld-preexp-npu `
     --run-id aim3-smoke-967880 --games 5 `
     --phases <仓库>/research_progress/2026-10-19-aim3-gpu-smoke-results/logs/aim3-smoke-967880/phases.tsv `
     --out <本运行目录>/smoke-checker/recheck.json
   ```
   **验收**：`recheck.json` 与 `research_progress/2026-10-19-aim3-gpu-smoke-results/logs/aim3-smoke-967880/check.json` 解析为 JSON 后完全相等（只忽略换行符差异）。
3. 验收通过后，用它覆盖冒烟目录的 `check_smoke.py`。再写 `research_progress/2026-10-19-aim3-gpu-smoke-results/SMOKE_CHECKER_PROVENANCE.json`，记录两个版本的 sha256、来源路径和复算结论。

**停止条件**：集群文件不存在，或复算结果不相等。这时只报告，不覆盖；这一项不阻塞第 4 步以后的工作。

## 4. 选分支：查 GPU 分区的最长墙钟

在集群登录节点上执行：

```bash
sinfo -h -p gpu -o "%l"
sbatch --test-only --partition=gpu --gres=gpu:a100-40:1 --cpus-per-task=8 --mem=48G --time=04:00:00 --wrap "true"
```

- 两者都表明允许 4 小时（`sinfo` 显示 ≥ `4:00:00` 或 `infinite`，且 `--test-only` 没有报时间限制错误）→ **分支 A**：5 片，每片 4 小时作业，runner 超时 12,900 秒。
- 否则 → **分支 B**：10 片，每片 3 小时作业，runner 超时保持 9,600 秒。

把两条命令的原始输出和所选分支写进本运行目录的 `BRANCH_DECISION.md`。**停止条件**：命令失败或结果含糊，先问用户。

| | 分支 A | 分支 B |
|---|---|---|
| 分片 | 5 片：27/27/27/27/26（沿用 v1 分片文件） | 10 片：14/14/14/14/13/13/13/13/13/13（重新生成） |
| 作业墙钟 / runner 超时 | 4 小时 / 12,900 秒 | 3 小时 / 9,600 秒 |
| 满 30 步最坏 runner 时间 | 约 7,380 秒（余量约 1.75 倍） | 约 3,830 秒（余量约 2.5 倍） |
| 哨兵放行线（runner 超时的 70%） | 9,030 秒 | 6,720 秒 |

## 5. 建 v1.1 执行包并冻结

1. 把 v1 执行包整个复制为 `research_progress/2026-10-18-aim3-e-evaluation-v1.1/`，删除副本中的 `FREEZE.json` 和 `FREEZE.sha256`。之后只改 v1.1 副本。

2. **分支 A 的修改**（只改这两处参数）：
   - `run_aim3_e.slurm`：`#SBATCH --time=03:00:00` 改为 `04:00:00`；runner 那行的 `9600s` 改为 `12900s`。
   - `README.md` 和 `EVALUATION_PLAN.md` 中对应的"3 小时""9,600 秒"同步修改。

3. **分支 B 的修改**：
   - `make_e_shards.py`：`N_SHARDS = 10`；把 manifest 里 `assignment` 字符串中的 `% 5` 改为 `% 10`。删除副本里旧的 `shards/` 目录和 `shards_manifest.json`，然后重新生成：
     ```powershell
     & '<LOCAL_CONDA>/envs/CS5446/python.exe' -B make_e_shards.py --census e_games.json --out-dir .
     ```
     验收：10 片，大小依次为 14、14、14、14、13、13、13、13、13、13；恰好覆盖 134 局、无重复；每类任务跨片差 ≤ 1。
   - `run_aim3_e.slurm`：`SHARD_INDEX` 的正则改为 `^[0-9]$`（提示文字改为 0..9）；`(27 if index < 4 else 26)` 改为 `(14 if index < 4 else 13)`；开头注释中的 "five" 改为 "ten"，"0..4" 改为 "0..9"。
   - `analyze_e.py`：新增常量 `N_SHARDS = 10`，替换所有表示分片数的 5。共 7 处：`n_shards != 5`，四处 `range(5)`，`len(selected) == 5`，`len(selected) != 5`。错误信息里的 "five shards" 一并改。
   - `validation/test_e_analysis.py`：三处 `range(5)` 改为 `range(10)`；另有三个期望值随片大小变化：
     - 第 2 片不完整时的缺失配对数 `27` 改为 `14`；
     - 第 0 片两次 attempt 的记录行数 `162`（2 × 27 × 3）改为 `84`（2 × 14 × 3）；
     - 第 0 片 always 臂的入选行数 `27` 改为 `14`。

     只改这些随分片数变化的值，不放宽其他断言（例如 134、402、133、−1/134 保持不变）。
   - `README.md` 和 `EVALUATION_PLAN.md` 中的片数、片大小、片号范围同步修改。

4. **两个分支都要做的修改**：
   - `EVALUATION_PLAN.md`：
     - 标题改为 v1.1；
     - 开头加一句："v1.1 只修改运行参数（[分支 A：墙钟与 runner 超时 / 分支 B：分片数]），总体、配置、主次分析、计分和选择规则与 v1 相同；v1 的 FREEZE sha256 为 `cc072df5…61c9`。"
     - 执行段落加两句：(1) "先单独运行第 0 片作为计时哨兵：其 runner 墙钟低于 runner 超时的 70%，且本地核对证据完整，才放行其余各片；否则暂停，交由用户决定。这只是运行顺序，不依据结果。"(2) "启动前的技术失败（没有 runner 清单）同样算一次 attempt；这个低概率风险已被接受。"
   - `README.md`：E_ROOT 示例改为 `aim3-e-v1.1-s<片号>-a<attempt>`，并补上哨兵顺序。

5. 在 v1.1 目录里跑测试和语法检查：
   ```powershell
   cd <仓库>/research_progress/2026-10-18-aim3-e-evaluation-v1.1
   & '<LOCAL_CONDA>/envs/CS5446/python.exe' -B -m pytest validation/test_e_checker.py validation/test_e_analysis.py -q -p no:cacheprovider
   bash -n run_aim3_e.slurm
   ```
   验收：全部通过（v1 是 19 项加 41 个子测试，约 4 分钟）；`bash -n` 无输出。测试完成后，`validation/` 下不应残留 `checker-*` 或 `synthetic-*` 临时目录。**停止条件**：任何失败，只报告，不改测试去迁就。

6. 生成冻结文件。在 v1.1 目录里运行下面的 Python 片段：
   ```python
   import datetime, hashlib, json, pathlib
   pkg = pathlib.Path(".").resolve()
   v1 = json.loads((pkg.parent / "2026-10-18-aim3-e-evaluation" / "FREEZE.json").read_text(encoding="utf-8"))
   assert not any(p.is_dir() for pattern in ("validation/checker-*", "validation/synthetic-*") for p in pkg.glob(pattern)), "leftover test temp dirs"
   files = []
   for p in sorted((p for p in pkg.rglob("*") if p.is_file()), key=lambda p: p.relative_to(pkg).as_posix().lower()):
       rel = p.relative_to(pkg).as_posix()
       if rel in ("FREEZE.json", "FREEZE.sha256") or "__pycache__" in rel.split("/"):
           continue
       data = p.read_bytes()
       files.append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
   shards = json.loads((pkg / "shards_manifest.json").read_text(encoding="utf-8"))["shards"]
   freeze = dict(
       schema_version=1, version="aim3-e-v1.1",
       frozen_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
       status=v1["status"], history_status=v1["history_status"],
       execution_status_at_freeze="not_submitted_no_E_outcomes_accessed",
       source_reference=v1["source_reference"], n_games=134,
       shard_sizes=[s["n_games"] for s in shards],
       supersedes={"version": "aim3-e-v1", "freeze_sha256": "cc072df5aec0a78bcc2ed30ee8b79776d6fcbd1ab151f8f6ef5afedf43ee61c9"},
       changes=["<逐条写明本次修改>"],
       local_validation={"tests": "<pytest 输出的通过数>", "slurm_syntax": "PASS"},
       files=files)
   raw = (json.dumps(freeze, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
   (pkg / "FREEZE.json").write_bytes(raw)
   (pkg / "FREEZE.sha256").write_text(hashlib.sha256(raw).hexdigest() + "  FREEZE.json\n", encoding="utf-8", newline="\n")
   print(hashlib.sha256(raw).hexdigest())
   ```
   记下输出的 sha256，下文称为 `V11_SHA`。从此 v1.1 目录不再修改。

7. 在 `research_progress/2026-10-18-aim3-e-review/FREEZE_SUMMARY.md` 末尾追加一节"v1.1 记录"：所选分支、修改清单、`V11_SHA`、测试结果。

## 6. 运行 E

### 6.1 上传执行包（一次）

用 `scp -r` 或 `rsync` 把 v1.1 目录原样上传到集群 `<CLUSTER_PROJECT>/aim3-e-v1.1-plan/`。**不要经过 git**，以免换行符被转换，导致哈希不符。上传后在集群上执行 `sha256sum FREEZE.json`，应等于 `V11_SHA`。

### 6.2 为每个 attempt 准备目录

每片、每次 attempt 都用一个全新的目录：`E_ROOT=<CLUSTER_PROJECT>/aim3-e-v1.1-s<片号>-a<attempt>`（目录已存在就停下）。

```bash
mkdir "$E_ROOT"
cp -a <CLUSTER_PROJECT>/aim3-e-v1.1-plan "$E_ROOT/plan"
cp "$E_ROOT/plan/source_package.json" "$E_ROOT/source_package.json"
# 接着运行 v1.1 README"准备每次独立运行目录"一节中的 Python 片段：只复制清单里的 74 个源码文件，并逐个校验哈希
<CLUSTER_VENV>/bin/python -B "$E_ROOT/plan/verify_code.py" "$E_ROOT"   # 应为 checked 74、mismatches []
```

### 6.3 选节点与提交

- 查看可用节点：`sinfo -p gpu -N -h -o "%N %t %G"`。同时运行的作业必须在**不同节点**上（服务固定用端口 8002）。
- 提交：
  ```bash
  cd "$E_ROOT"
  sbatch --parsable --nodelist=<节点> \
    --export=ALL,E_ROOT="$E_ROOT",E_FREEZE_SHA256=<V11_SHA>,SHARD_INDEX=<片号>,ATTEMPT=<1或2> \
    plan/run_aim3_e.slurm
  ```
- 节点不够分时，其余作业不加 `--nodelist`，改加 `--dependency=singleton`。同名作业会因此一个接一个地串行。

### 6.4 顺序

1. **哨兵**：只提交第 0 片 attempt 1。完成后按 6.5 取回并核对。
   - 放行条件：Slurm 状态 `COMPLETED 0:0`；本地 checker 的 `evidence_complete=true`，且与集群 `check.json` 一致；`phases.tsv` 中 runner 秒数低于第 4 节表格里的哨兵放行线。
   - 第 0 片不完整：按 6.6 重跑一次。重跑后完整且低于放行线 → 放行；否则停止。
   - 完整但 runner 秒数达到或超过放行线：**停止**，报告用户，不提交其他片。
2. **其余各片**：提交 attempt 1，节点能分开就并发，否则串行。
3. 轮询状态（`squeue -u $USER`，`sacct -j <作业号> --format=JobID,State,ExitCode,Elapsed,NodeList`）的间隔不少于 15 分钟。轮询时不要去读或汇总行内成功率。

### 6.5 取回与逐片核对（每个 attempt，包括失败的）

1. 在集群上打包，并记录哈希：
   ```bash
   mkdir -p <CLUSTER_PROJECT>/aim3-e-v1.1-results
   T=<CLUSTER_PROJECT>/aim3-e-v1.1-results/$(basename "$E_ROOT").tar.gz
   tar -czf "$T" -C "$E_ROOT" execution.json logs alfworld-preexp-npu/data alfworld-preexp-npu/outputs $(cd "$E_ROOT" && ls cs5446-aim3-e-*.out cs5446-aim3-e-*.err 2>/dev/null)
   sha256sum "$T"
   ```
   启动前就失败的 attempt 可能缺 `data/` 或 `outputs/`。打包时去掉不存在的路径即可，但必须保留 `execution.json` 和 `logs/`。
2. 下载到本地 `<本运行目录>/attempts/`，核对 sha256 后解压到 `<本运行目录>/attempts/<E_ROOT 目录名>/`。保持 `execution.json`、`logs/`、`alfworld-preexp-npu/` 的相对结构，合并器依赖这个结构。预计解压后共 5–8 GB，本地至少留 15 GB 空间。
3. 本地复核：
   ```powershell
   & '<LOCAL_CONDA>/envs/CS5446/python.exe' -B <v1.1 目录>/check_smoke.py `
     --code-root <仓库>/alfworld-preexp-npu `
     --output-root <本运行目录>/attempts/<目录名>/alfworld-preexp-npu `
     --run-id <run_id> --split eval_out_of_distribution --games <该片局数> `
     --games-file <v1.1 目录>/shards/e-shard-<片号>.json `
     --phases <本运行目录>/attempts/<目录名>/logs/<run_id>/phases.tsv `
     --out <本运行目录>/attempts/<目录名>/check-local.json
   ```
   `run_id` 的格式为 `aim3-e-s<片号>-a<attempt>-<作业号>`。

**完整的定义**：Slurm 为 `COMPLETED 0:0`，**且** 本地 `evidence_complete=true`，**且** 本地结果与集群 `check.json` 解析后相等。只有 C7 未覆盖（`INSUFFICIENT_COVERAGE`）仍算完整，不重跑。**停止条件**：集群与本地的结论不一致。

### 6.6 重跑规则

attempt 1 不完整（超时、技术失败、启动失败、`evidence_complete=false`）时，在新目录提交该片 attempt 2，且只此一次。attempt 2 仍不完整，该片记为缺失，不再提交。policy failure 和 C7 未覆盖都不是重跑理由。

## 7. 合并分析（只做一次）

1. 写 `<本运行目录>/attempts.json`，格式为 `{"attempts": [...]}`。**列出全部 attempt**，包括失败和未被采用的。每条形如：
   ```json
   {"shard_index": 0, "attempt": 1, "run_id": "aim3-e-s0-a1-<作业号>",
    "output_root": "<本运行目录>/attempts/aim3-e-v1.1-s0-a1/alfworld-preexp-npu",
    "phases": "<本运行目录>/attempts/aim3-e-v1.1-s0-a1/logs/<run_id>/phases.tsv"}
   ```
2. 运行：
   ```powershell
   & '<LOCAL_CONDA>/envs/CS5446/python.exe' -B <v1.1 目录>/analyze_e.py `
     --code-root <仓库>/alfworld-preexp-npu --plan-dir <v1.1 目录> `
     --attempts <本运行目录>/attempts.json --out <本运行目录>/analysis.json
   ```
   有缺片时输出状态为 `incomplete_inference_suspended`，这是预定行为，照实报告。

## 8. 最终报告：`<本运行目录>/E_RUN_STATUS.md`

只报告 `analysis.json` 和各片核对结果中已有的内容，不另算、不另作检验：

1. 版本与指纹：`V11_SHA`、所选分支、第 4 节的分区检查结果。
2. attempt 表：片号、attempt、作业号、节点、Slurm 状态、runner 秒数、`evidence_complete`、`coverage_complete`、本地与集群是否一致、是否被采用。
3. 分析状态：`complete` 或 `incomplete_inference_suspended`。
4. 主对比 Always − no_info：差值、**97.5% 区间及其 direction 字段**（方向只按它判定）、McNemar p（补充）、rescued/harmed、计划配对数、缺失配对数。
5. 次要分析（描述性）：Always − none、no_info − none。
6. 敏感性（处理后子集，描述性）：保留配对数及其比较。
7. 各臂成功率与失败诊断：policy failure 按臂、按角色的调用数和失败数，以及达到 384 输出上限的次数。
8. 成本与时间：已知成本分量、是否完整（未知不记为 0）；各 attempt 的 runner 墙钟。
9. 解释边界（照写）：历史用途未核实，结果只是候选集上的条件性计算；不显著不等于等价；整局结果不能代替局部 admission/info 的证据。
10. 偏差与事件：例如重跑、缺片、哨兵触发、节点或端口问题。

完成后告诉用户报告路径。不要发送通知，也不要推送任何内容。


## 2026-10-18 用户追加授权：停止后的三处衔接修正

用户明确授权：“修三处衔接问题，标明旧报告来源，完整跑两个 E 离线验证文件。通过后冻结 v1.1，按原计划先跑第0片哨兵，满足条件继续其余；保留原数据，遇停止条件再找用户。”

本次仅授权以下衔接修正：v1.1 的 `validation/test_e_checker.py` 使用 `HERE.parent / "check_smoke.py"`；`validation/test_e_analysis.py` 的已知 completion-token 期望由 54 改为 28；第 5.6 节临时目录 guard 仅检查 `p.is_dir()`。其余测试断言和运行停止条件不变。旧四份验证 JSON 保留原字节并注明冻结 v1 来源；真实 v1.1 使用新的完整 pytest 日志、退出码、当前被测文件哈希及分片核对作为验收记录，不新增 pytest 插件或包装层。

原失败日志、停止记录及原执行任务副本保留。职责分离：执行 agent 仅负责本地修正、完整测试与冻结；主线程独占 SSH、上传、提交和后续作业操作。禁止并发提交。

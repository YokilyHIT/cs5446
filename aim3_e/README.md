# Aim 3 E（4B）：冻结方法与结果的公开副本

English summary: frozen v1.1 method and the final results of the 4B whole-episode evaluation (134 unseen ALFWorld games × always / no_info / none). Files marked `.public` are copies whose machine and cluster-home path prefixes were masked; nothing else was changed. If you take part in the blind recheck (`recheck_4b/`), finish it before opening `results/`.

## 目录

| 文件 | 说明 |
|---|---|
| `plan/EVALUATION_PLAN.md` | v1.1 一页评估计划，与冻结原件逐字节相同 |
| `plan/FREEZE.json` | v1.1 冻结清单（文件路径均为包内相对路径），与原件逐字节相同 |
| `plan/shards_manifest.json` | 十片分配与冻结选择文件的 SHA-256，与原件逐字节相同 |
| `plan/shards_public.json` | 十片的游戏成员与顺序，游戏用 `<task>/<trial>` 表示；哈希指向冻结原件 |
| `plan/frozen_config.public.json` | 冻结 planner/WM 配置的公开副本 |
| `results/analysis.public.json` | 唯一一次正式合并分析的公开副本 |
| `results/E_RUN_STATUS.public.md` | 完整执行与分析记录的公开副本 |
| `results/EXECUTION_TASK.public.md` | 执行任务书的公开副本 |

## 公开副本的处理

只把本机路径和集群个人主目录前缀替换为占位符：`<CLUSTER_HOME>`、`<CLUSTER_PROJECT>`、`<CLUSTER_VENV>`、`<ALFWORLD_DATA>`、`<MODEL_PATH>`、`<LOCAL_REPO>`、`<LOCAL_CACHE>`、`<LOCAL_PROJECT>`、`<LOCAL_CONDA>`、`<LOCAL_HOME>`。其余内容不变；JSON 按原样式（缩进 2、UTF-8）重新输出，因此公开副本的哈希与原件不同。记录中指向本机文件的链接在公开副本里不可点击，属预期情况。

| 原件 | 原件 SHA-256 | 公开副本 SHA-256 |
|---|---|---|
| `analysis.json` | `8b6c90435041c174945f88b754e9dc8ee353ddc7a9bd26e9ccbdd31ce05ef24e` | `527644ce446c4fcf3fee5e2f97b0642523eadd70bee8fe3f107842c6f81123cf` |
| `frozen_config.json` | `7fa9d0fc6deedc126c7cb9460e0003eeb4b77edb092b279d8e150787b8623ad7` | `6e97f5f6a7710b86f56ac931d8c8850de94afd32a046c6775225654562adfef1` |
| `E_RUN_STATUS.md` | `f70817c30918aca41af20f122df876c1a70fb6e93cef6d3c58f4ca884f992020` | `30fbdc9db07a7f50739fffab9c09372051aaf74b9ab4e1e72e01dfcc7a8d363d` |
| `EXECUTION_TASK.md` | `20503f212ce7f68965e95ae7a31bb5b95d9036b5d5fafd660ff8201bb0b97839` | `108b2613174600af8de2ae6d50b2688dce451564556609f59791573c9d4ca276` |

报告中引用的 `analysis.json` SHA-256（`8b6c…f24e`）指原件。三次核对都与它一致：集群与本地各片 checker 认证、冻结合并器重跑（逐字节相同），以及不调用项目代码的独立重算。

## 没有上传的内容

约 8.6 GB 的逐局完整轨迹和调用审计、集群作业脚本与执行包装层（含个人路径）、未发送的负责人通知草稿均未上传。复验所需的逐局结果见 [`recheck_4b/data/`](../recheck_4b/data/)，其来源文件哈希记录在 `DATA_MANIFEST.json` 中；完整原件可应要求由数据负责人在本地提供。

# Report 与 slides 插图

按 `report.tex`、`WHEN_WHAT_HOW_Slides逐页方案.docx` 和 `agent.py` / `preconditions.py` 核对内容，使用内置 image_gen 生成。全套为白底彩色栅格插图，PNG 原生尺寸 1672 × 941，接近 16:9。未将低分辨率图片插值放大；并非矢量图。英文文字与报告语言一致。

| 文件 | 内容 | Slides 建议 | Report 建议 |
|---|---|---|---|
| 01_method_overview.png | 执行前合法性检查、WM 建议校验、Planner 修订与反馈 | 第 8 页 | Study 3 / Repair Interface |
| 02_when_what_how.png | WHEN–WHAT–HOW 研究主线 | 第 1 或 18 页 | Introduction |
| 03_failure_loop.png | 持有番茄时拿苹果的失败循环 | 第 2 或 6 页 | Introduction 或 Failure Analysis |
| 04_repair_example.png | 缺失前提解释与第一步建议 | 第 7–8 页 | Illustrative interaction |
| 05_interface_ablation.png | 等信息预测/修复对比，以及反馈组件消融 | 第 14–15 页 | Ablation Study |

报告优先放 01 和 04；05 可用于解释消融设计。图片较宽，建议按整行宽度插入，避免缩成单栏小图。PNG 可直接插入 PowerPoint、Keynote、Word 和 LaTeX。机器人和厨房是对文本环境的概念可视化，不是 ALFWorld 原始截图或真实机器人实验。示例话语经过简化，不是逐字模型日志或可直接执行的环境命令。02 中动作清单只是概念图标，不是具体状态的有效动作集合。

方法图中的正常路径也包含 `check valid actions` 接口命令；该命令由交互协议处理，并非一定产生物理环境动作。建议校验只检查动作合法性，不保证原因正确或任务成功。04 表示 Planner 选择接受建议的一种可能，不表示强制执行。05 的 failure-only 不调用 WM，后三种反馈组件来自相同 WM 调用，仅改变展示字段。

`insert_figures.tex` 给出五个独立 figure 环境，复制需要的环境到正文对应位置即可；也可用 `\input{figures/illustrations/insert_figures}` 一次插入全部五张，但不建议集中堆放。当前 `report.tex` 已加载 graphicx，无须额外图形包。没有改动原报告正文；当前环境没有 pdflatex，因此未验证插入后的排版。

`prompts.json` 保存全部生成与修正提示词，模式为内置 image_gen（非 CLI）。修正了方法图的具体动作清单，以及消融图中 failure-only 的连接，避免与实现冲突。

from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'WHEN_WHAT_HOW_Slides逐页方案.docx'

# Content is a presentation plan, not a new experimental report.
slides = [
    dict(n=1, section='开场', title='标题页', en='From Prediction to Repair: World-Model Guidance for LLM Planning',
         points=['展示小组成员、课程和学校。', '核心问题：What should a world model tell a planner when an action cannot be executed?', '标题页不强调模型大小；具体配置在实验环境页说明。'],
         source='报告标题与 Introduction；不放实验表。',
         visual='用简洁箭头表达 Prediction → Diagnosis → Repair。',
         takeaway='用“世界模型应该提供什么帮助”引出整个研究。'),
    dict(n=2, section='背景', title='为什么 Planner 需要 World Model？', en='Why Does a Planner Need World-Model Guidance?',
         points=['LLM Planner 根据任务和交互历史选择动作。', '动作可能违反位置、持有物品、容器状态等前置条件。', '环境返回 “Nothing happens”，但 Planner 可能重复同一个错误。', 'WM 可以提供动作后果或执行条件相关知识。'],
         source='Introduction；根据文字新画示意图。',
         visual='Task → Planner → Action → Environment → Observation，反馈回 Planner。在失败反馈处标注 “Failure feedback does not explain how to recover.”',
         takeaway='失败反馈告诉我们“没有成功”，却不一定告诉我们“下一步怎么做”。'),
    dict(n=3, section='现有方法及不足', title='现有 WM 指导方式', en='Existing Approaches to World-Model Guidance',
         points=['先介绍各类方法的机制与待检验问题，不提前把所有 baseline 判定为无效。'],
         table=(['方法类别', '提供什么', '需要检验的问题'], [
             ['Predictive foresight', '下一步观测', '预测是否真正帮助决策？'],
             ['Selective invocation', '挑选提供预测的时机', '是否优于随机调用？'],
             ['WM-based judging', '失败判断与反馈', '是否错误干预合法动作？'],
             ['Rules / learned insights', '规则或经验知识', '知识来源与适用条件是什么？']]),
         source='Related Work 与 Aligned Baselines 的方法描述。',
         visual='用四行概念对照表；这一页暂不放成功率。',
         takeaway='现有方法在“何时提供、提供什么、知识从哪里来”三个方面不同。'),
    dict(n=4, section='现有方法及不足 · WHEN', title='更好的预测与调用时机是否足够？', en='WHEN: Can Better Timing Make Forecasts Useful?',
         points=['选择性调用相对随机调用：SR +0.6 pp，95% CI [−2.7, 4.2]，差异不显著。', '加入记忆后预测准确率由 37.7% 提高到约 60–62%，但任务 SR 从 22.8% 变为 22.3%。', '学习路由器 AUROC 从 0.70–0.74 降到新状态上的 0.42–0.43。'],
         source='Study 1 正文的早期 timing、memory 和 router 实验。',
         visual='三个并列结果卡片，每个卡片分别标注其任务集或实验背景。',
         takeaway='Better prediction and selective timing did not reliably produce better decisions.',
         note='这些结果来自不同早期实验，不能画成同一条性能变化曲线，也不能说成所有预测方法都无效。'),
    dict(n=5, section='现有方法及不足 · WHEN', title='收益是否只是来自“再想一次”？', en='Does Foresight Help beyond Another Decision Opportunity?',
         points=['在相同的随机 30% 触发步骤比较预测与无信息重采样。', 'WM prediction 相对 resampling：PR +1.4 pp，CI [−0.4, 3.2]，不显著。', 'Oracle observation 相对 resampling：PR +3.0 pp，CI [1.2, 4.8]，显著。'],
         table=(['条件', 'PR'], [['No intervention', '32.8%'], ['Resampling', '33.0%'], ['WM prediction', '34.5%'], ['Oracle observation', '36.0%']]),
         source='Table 3，tab:when-resampling；dev460，每任务两次运行。',
         visual='四根 PR 柱；在两组主要对比旁标注区间或显著性，避免只凭柱高解读。',
         takeaway='If timing alone is insufficient, what information is the planner missing?',
         note='本页是 dev460，不是 fresh600；此处 resampling 的触发是随机步骤。'),
    dict(n=6, section='方法动机 · WHAT', title='Planner 到底卡在哪里？', en='WHAT: The Bottleneck Is Action Feasibility',
         points=['31.3%：动作提议非法。', '74%：失败 episode 以重复循环结束。', '84%：加热、冷却、清洁尝试非法。', '例子：尝试加热 → 没拿着物品或不在设备旁 → Nothing happens → 重复尝试。'],
         source='Table 4，tab:failure-signals；dev460 的失败分析。',
         visual='左侧三个大数字，右侧一个失败循环示例。',
         takeaway='The planner needs help satisfying action preconditions.',
         note='三个百分比的分母不同，必须分别写清楚；循环率以失败 episode 为分母。'),
    dict(n=7, section='方法动机 · WHAT', title='完美预测与修复信息哪个更有用？', en='From Knowing Failure to Knowing How to Recover',
         points=['所有干预使用相同的非法动作触发条件。', '在这个触发点，真实下一步观测就是 “Nothing happens”。', '原因与第一步比仅报告失败提供更多决策价值。'],
         table=(['提供的信息', 'SR', 'PR'], [['Failure notification', '18.3%', '36.7%'], ['Legal projection', '14.2%', '36.2%'], ['Oracle cause + first step', '29.1%', '41.0%']]),
         source='Table 5，tab:what-oracle；dev460，每任务两次运行。',
         visual='保留三行对照，突出 Oracle repair；可配 “失败事实 → 原因 → 下一步” 信息层次图。',
         takeaway='Can a frozen WM provide this repair information without an explicit rule base?',
         note='这是 Oracle 信息价值探针，不是最终 WM 的性能。该页承接 WHEN 并引出 HOW，应保留。'),
    dict(n=8, section='我们的方法 · HOW', title='Failure-Triggered WM Repair', en='HOW: Diagnose, Suggest, and Let the Planner Decide',
         points=['仅在动作提议非法时调用 WM；检查使用环境提供的 valid-action list。', 'WM 输出缺失前提（Reason）和一个合法建议步骤（Repair）。', '建议步骤经过合法性校验，不合法的建议被丢弃。', 'Planner 接收建议后重新决定，保留最终动作选择权。'],
         source='Study 3 的 Repair Interface；报告暂无现成方法 Figure，需要根据方法新画。',
         visual='Planner proposes action → Check valid actions。合法分支直接执行；非法分支进入 WM: Reason + Repair → Planner revises → Execute。',
         takeaway='WM supplies recovery advice; the planner makes the final decision.',
         note='可配说明性例子：Already holding another object → Put the held object down first。标注是 illustrative example，不是新增实验轨迹。'),
    dict(n=9, section='实验环境及 baseline', title='实验环境与协议', en='Experimental Setup',
         points=['ALFWorld：六类任务，每个 episode 最多 30 步。', 'Planner：Qwen3-4B-Instruct-2507；WM：Qwen3-14B，thinking off。模型冻结，无微调。', 'dev460 用于开发与选择；fresh600 每类 100 个任务，每个配置重复三次。', 'SR 衡量任务成功；PR 衡量子目标完成进度。', '使用 paired task bootstrap 和预注册主要检验。'],
         source='Table 2，tab:protocol；Shared Experimental Setup。',
         visual='精简配置表，重点保留模型、任务、数据划分与指标；解码参数可放脚注或备份页。',
         takeaway='The frozen method is evaluated on tasks not run before method selection.',
         note='fresh600 是训练场景分布内未运行过的实例，不是 OOD 数据。模型大小在本页清楚交代，后续无需重复强调。'),
    dict(n=10, section='实验环境及 baseline', title='Baseline 分别回答什么问题？', en='Baselines and Experimental Controls',
         points=['区分用于解释机制的控制组与用于比较系统的对齐基线。'],
         table=(['组别', '条件', '对照目的'], [
             ['基础控制', 'None / Failure only / Reflection', '是否超越失败提示与反思？'],
             ['知识参考', 'Rule cards / Oracle repair', '与显式知识和真实诊断相比如何？'],
             ['WM 方法', 'WALL-E-style / WorldEvolver-style', '不同调用与指导方式如何？'],
             ['经验与规则方法', 'ExpeL-style / RPMS-style', '学习知识与规则状态系统如何？']]),
         source='Shared Experimental Setup 的 Controls；Study 3 的 Aligned Baselines。',
         visual='四行分类表，不在本页重复结果数值。',
         takeaway='Aligned implementations under shared evaluation conditions—not full reproductions.'),
    dict(n=11, section='实验结果', title='主实验：Repair 是否有效？', en='Repair Improves Task Completion',
         points=['突出主结果：20.9% → 36.2%，提升 15.3 个百分点。', '相对 Failure only：PR +4.2 pp；说明收益超越失败提示本身。', '满足相对 Rule cards 的 PR 非劣标准。'],
         table=(['条件', 'SR'], [['None', '20.9%'], ['Failure only', '28.3%'], ['Generic reflection', '28.6%'], ['Rule cards', '33.3%'], ['WM repair', '36.2%'], ['Oracle repair', '36.7%']]),
         source='Table 7，tab:main；显著性和非劣结论来自 Table 8，tab:hypotheses。',
         visual='横向 SR 柱状图；WM repair 用强调色；右侧放 +15.3 pp 大数字与两个统计结论。',
         takeaway='Repair adds useful information beyond detecting an invalid action.',
         note='接近 Oracle 的成功率不等于具有 Oracle 的诊断准确率。'),
    dict(n=12, section='实验结果', title='与其他方法比较：效果与调用成本', en='Comparison with Aligned Baselines',
         points=['Repair 的 SR 高于这里的 WM 与经验学习对照。', '与 RPMS-style 表现接近，不能说全面胜过规则方法。', '相比所测试的 WM 判断与预测方法，在线调用更少。'],
         table=(['方法', 'SR', 'PR', 'Calls'], [['WM repair', '36.2%', '49.0%', '5.3'], ['WALL-E-style', '26.8%', '48.2%', '54.5'], ['RPMS-style', '37.2%', '48.1%', '0'], ['ExpeL-style, failure gate', '28.1%', '43.4%', '0'], ['WorldEvolver-style', '22.1%', '41.4%', '25.9']]),
         source='Table 13，tab:baselines；只取重点行与 SR、PR、Calls 三列。',
         visual='精简对照表；效果与调用数可用两个独立图展示，避免单位混用。',
         takeaway='Environment-grounded repair is effective with fewer advisory calls than the tested WM alternatives.',
         note='Calls 是每 episode 在线调用数，不包含离线知识学习成本；不能据此声称总体效率最优。'),
    dict(n=13, section='实验结果', title='不同任务上效果是否一致？', en='Where Does Repair Help—and Where Does It Fall Short?',
         points=['Repair 在六类任务上的 SR 均高于 None。', '与规则卡相比，look-at、简单放置、清洁和冷却的数值更高。', '加热与双物体任务中，规则卡更强。', '双物体任务仍暴露库存约束方面的弱点。'],
         source='Table 10，tab:tasks；取 None、Rule cards、WM repair 三列，保留全部六类任务。',
         visual='六类任务的分组柱状图；任务名用简写并在图下注释。',
         takeaway='Repair helps broadly, but specific rules remain valuable for some task types.',
         note='Task-wise comparisons are descriptive；不要将每类数值差异都称为显著提升。'),
    dict(n=14, section='消融实验及分析', title='Repair 优势是否来自更多输入？', en='Ablation: Repair versus Prediction under Equal Information',
         points=['给预测接口更多输入信息，确实可以改善结果。', '但在相同输入条件下，Repair 仍高出 4.1 pp PR。', '该差异通过 Holm 校正。'],
         table=(['接口', 'PR'], [['Original prediction', '42.4%'], ['Prediction with repair inputs', '44.9%'], ['Repair', '49.0%']]),
         source='Table 9，tab:ablation；选择两种预测与完整修复三行。',
         visual='三根 PR 柱；突出 equal-information prediction → repair 的 4.1 pp 对比。',
         takeaway='What we ask the WM matters beyond what we give it.',
         note='这是直接支撑 From Prediction to Repair 题目的核心消融页。'),
    dict(n=15, section='消融实验及分析', title='原因还是建议步骤更重要？', en='Ablation: Which Repair Components Matter?',
         points=['只给原因，相对失败提示的 PR 提升不显著。', '建议步骤提供可执行的方向。', '原因与步骤组合表现最好。'],
         table=(['输出内容', 'PR'], [['Failure only', '44.8%'], ['Cause only', '45.6%'], ['First step only', '47.0%'], ['Cause + first step', '49.0%']]),
         source='Table 9，tab:ablation；取失败提示、原因、步骤、组合四行。',
         visual='四根 PR 柱，配“原因 / 步骤”的勾选标记。',
         takeaway='The suggested step is useful; an accompanying explanation improves its use.',
         note='Step-only 与组合相对 step-only 的比较属于 secondary、uncorrected；不要将它们误写成 Holm 校正后的主要检验。'),
    dict(n=16, section='消融实验及分析', title='要保留记忆或强制执行建议吗？', en='Ablation: Memory and Action Execution',
         points=['两个变体都没有显著提高主要 PR 指标。', '保留诊断记忆的 SR 下降，属于探索性结果。', '直接执行建议没有可靠增益。', '过时或错误的诊断可能影响后续决策，但这只是解释假设。'],
         table=(['变体', 'SR', 'PR'], [['WM repair', '36.2%', '49.0%'], ['Retain five diagnoses', '31.8%', '47.9%'], ['Execute suggested step', '36.9%', '49.2%']]),
         source='Table 12，tab:followups。',
         visual='三行表，或 SR 与 PR 分开的双图；突出“不显著提高 PR”的结论。',
         takeaway='Local repair does not automatically benefit from persistence or forced adoption.'),
    dict(n=17, section='消融实验及分析', title='收益发生在什么阶段？', en='Repair Helps the Planner Progress after Object Acquisition',
         points=['左侧展示 Saw target → Picked target → Success 的边际完成率。', '右侧展示拿到目标后的条件成功率：None 44%、Failure only 55%、WM repair 66%、Oracle repair 71%。', 'WM 诊断类别匹配率约 30%；有效指导不等于每次诊断都精确。'],
         source='Table 11，tab:funnel；30% 类别匹配率来自 Subgoal Progress and Remaining Failures 正文。',
         visual='左侧阶段图；右侧独立柱状图展示 P(success | picked)。',
         takeaway='A substantial part of the observed gain occurs after object acquisition.',
         note='条件成功率与前三个边际比例的分母不同，不能混成同一漏斗。该机制分析是描述性、相关性证据。'),
    dict(n=18, section='总结', title='回到 WHEN → WHAT → HOW', en='From Prediction to Repair',
         points=['WHEN：所测试的预测调用策略未带来可靠的额外收益。', 'WHAT：Planner 需要缺失前提与可行的恢复步骤。', 'HOW：失败触发、原因＋步骤、Planner 保留决策权。', '边界：依赖环境提供 valid-action list；更大 Planner 或接管动作可能更强，不主张最优模型资源配置。'],
         source='Table 1，tab:research-roadmap；Discussion and Limitations 与 Conclusion。',
         visual='三个相连的结论框；底部用较小字体保留两条适用边界。',
         takeaway='A world model should help the planner recover, not merely forecast failure.'),
]


def font(style, size, bold=False, color=None):
    style.font.name = 'Calibri'
    style.font.size = Pt(size)
    style.font.bold = bold
    style.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'), '微软雅黑')
    if color:
        style.font.color.rgb = RGBColor.from_string(color)


doc = Document()
section = doc.sections[0]
section.page_width, section.page_height = Cm(21), Cm(29.7)
section.top_margin = section.bottom_margin = Cm(1.7)
section.left_margin = section.right_margin = Cm(1.8)
section.header_distance = section.footer_distance = Cm(.8)
font(doc.styles['Normal'], 10)
doc.styles['Normal'].paragraph_format.space_after = Pt(4)
doc.styles['Normal'].paragraph_format.line_spacing = 1.12
font(doc.styles['Title'], 24, True, '16324F')
font(doc.styles['Heading 1'], 15, True, '16324F')
font(doc.styles['Heading 2'], 11, True, '247C8C')
for name in ['List Bullet', 'List Number']:
    font(doc.styles[name], 10)
    doc.styles[name].paragraph_format.space_after = Pt(3)
header = section.header.paragraphs[0]
header.text = 'CS5446  |  From Prediction to Repair  |  Slides 逐页方案'
header.style = doc.styles['Caption']
footer = section.footer.paragraphs[0]
footer.alignment = 2
footer.add_run('第 ')
field = OxmlElement('w:fldSimple')
field.set(qn('w:instr'), 'PAGE')
footer._p.append(field)
footer.add_run(' 页')
doc.core_properties.title = 'From Prediction to Repair — Slides 逐页方案'
doc.core_properties.subject = 'WHEN → WHAT → HOW 汇报结构与报告图表映射'
doc.core_properties.author = 'CS5446 Project Team'


def label(text, value):
    p = doc.add_paragraph()
    p.add_run(text + '：').bold = True
    p.add_run(value)


def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Light Shading Accent 1'
    for c, text in zip(t.rows[0].cells, headers):
        c.text = text
        for r in c.paragraphs[0].runs:
            r.bold = True
    for row in rows:
        for c, text in zip(t.add_row().cells, row):
            c.text = str(text)
    for row in t.rows:
        trpr = row._tr.get_or_add_trPr()
        trpr.append(OxmlElement('w:cantSplit'))
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.space_before = Pt(2)
                for run in p.runs:
                    run.font.size = Pt(9)
    return t


doc.add_heading('Slides 逐页方案', 0)
doc.add_paragraph('From Prediction to Repair:\nWorld-Model Guidance for LLM Planning', style='Subtitle')
label('建议规模', '18 页主 slides，约 18–22 分钟；另备 3 页答疑材料。')
label('整理日期', '2026 年 11 月 8 日')
doc.add_heading('研究主线与展示顺序', 1)
doc.add_paragraph('背景 → 现有方法与 WHEN 的不足 → WHAT 定位问题 → HOW 提出方法 → 实验环境与 baseline → 结果 → 消融及分析 → 总结。')
doc.add_paragraph('WHEN 解释为什么仅改善预测与调用时机不够；WHAT 用失败分析和 Oracle 探针定位所需信息；HOW 检验冻结 WM 能否提供这种修复建议。')
doc.add_heading('使用说明', 1)
for text in [
    '本文档是 slides 制作方案，逐页列出建议标题、正文要点、报告来源、图表呈现方式与讲解结论。',
    '表号按当前 report.tex 的正文顺序核对，共 13 张表。报告尚无正式 Figure；标为“新画”的图是建议制作的示意图，不是已有实验图。',
    '尽量将结果表重画为可读的图，避免截取整页论文。图表仍须保留数据集、指标和必要的统计说明。',
    '推荐每页只讲一个主要结论。模型大小在实验环境页说明，不作为整个汇报的叙事中心。',
]:
    doc.add_paragraph(text, style='List Bullet')
table(['部分', 'Slides'], [['背景与开场', '1–2'], ['现有方法及 WHEN', '3–5'], ['WHAT 与 HOW', '6–8'], ['实验环境与 baseline', '9–10'], ['实验结果', '11–13'], ['消融与分析', '14–17'], ['总结', '18']])

for i, slide in enumerate(slides):
    if i % 2 == 0:
        doc.add_page_break()
    doc.add_heading(f"第 {slide['n']} 页｜{slide['title']}", 1)
    en = doc.add_paragraph(slide['en'])
    en.paragraph_format.keep_with_next = True
    for r in en.runs:
        r.italic = True
        r.font.color.rgb = RGBColor.from_string('247C8C')
    label('所属部分', slide['section'])
    for point in slide['points']:
        doc.add_paragraph(point, style='List Bullet')
    if 'table' in slide:
        table(*slide['table'])
    label('报告来源', slide['source'])
    label('图表呈现', slide['visual'])
    label('本页结论／转场', slide['takeaway'])
    if 'note' in slide:
        label('注意', slide['note'])

doc.add_page_break()
doc.add_heading('备份页与图表索引', 1)
table(['备份页', '建议内容', '报告来源'], [
    ['B1 开发集选型', '为什么选择当前修复方法；开发集与测试集分开', 'Table 6 / tab:development'],
    ['B2 模型容量与接管', '4B/14B WM、不同 Planner、接管动作对照', '附录 Model-Size Controls、Decision Authority and Memory Controls'],
    ['B3 规则组合与统计', '校验与直接拼接、主要假设及非劣标准', '附录 Combining Repair with Explicit Rules；Table 8'],
])
doc.add_heading('正文表格到 slides 的映射', 2)
table(['报告表', 'LaTeX label', '建议使用位置'], [
    ['Table 1', 'tab:research-roadmap', 'Slide 18，总结框架'],
    ['Table 2', 'tab:protocol', 'Slide 9，实验协议'],
    ['Table 3', 'tab:when-resampling', 'Slide 5，WHEN 对照'],
    ['Table 4', 'tab:failure-signals', 'Slide 6，失败分析'],
    ['Table 5', 'tab:what-oracle', 'Slide 7，Oracle 信息探针'],
    ['Table 6', 'tab:development', '备份 B1'],
    ['Table 7', 'tab:main', 'Slide 11，主结果'],
    ['Table 8', 'tab:hypotheses', 'Slide 11 注释；备份 B3'],
    ['Table 9', 'tab:ablation', 'Slides 14–15，接口和组件消融'],
    ['Table 10', 'tab:tasks', 'Slide 13，任务分类'],
    ['Table 11', 'tab:funnel', 'Slide 17，阶段分析'],
    ['Table 12', 'tab:followups', 'Slide 16，记忆与直接执行'],
    ['Table 13', 'tab:baselines', 'Slide 12，baseline 对比'],
])
doc.add_heading('统一呈现规则', 2)
for text in [
    'WM repair 统一使用一种强调色，baseline 使用中性色；所有结果图注明 SR 或 PR、百分比单位与任务集。',
    'pp 表示百分点，不是相对百分比；只在有对应检验支持时标注显著。',
    'Slide 5 的 resampling 在随机步骤触发，Slide 7 的 resampling 在非法动作处触发；不可当作同一个实验条件。',
    '保留局限：有效动作列表依赖、同场景分布测试、规则优势和强模型接管结果。',
]:
    doc.add_paragraph(text, style='List Bullet')

# Ensure table labels still match the report used to construct this plan.
tex = (ROOT / 'report.tex').read_text(encoding='utf-8')
labels = []
for block in re.findall(r'\\begin\{table\}.*?\\end\{table\}', tex, re.S):
    labels.append(re.search(r'\\label\{([^}]+)\}', block).group(1))
assert labels == ['tab:research-roadmap', 'tab:protocol', 'tab:when-resampling', 'tab:failure-signals', 'tab:what-oracle', 'tab:development', 'tab:main', 'tab:hypotheses', 'tab:ablation', 'tab:tasks', 'tab:funnel', 'tab:followups', 'tab:baselines']
doc.save(OUTPUT)
with zipfile.ZipFile(OUTPUT) as z:
    assert z.testzip() is None
    for name in z.namelist():
        if name.endswith('.xml'):
            ElementTree.fromstring(z.read(name))
check = Document(OUTPUT)
headings = [p.text for p in check.paragraphs if p.style.name == 'Heading 1']
assert len([t for t in headings if re.match(r'第 \d+ 页', t)]) == 18
assert 'WHEN' in '\n'.join(p.text for p in check.paragraphs)
print('Created:', OUTPUT)
print('Verified: 18 slide entries, 13 report-table labels, DOCX archive and XML structure.')

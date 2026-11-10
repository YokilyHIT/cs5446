from pathlib import Path
import ast
import re
import shutil
import zipfile
from xml.etree import ElementTree
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'WHEN_WHAT_HOW_Slides逐页方案.docx'
# Read the original slide metadata without executing the old document builder.
tree = ast.parse((ROOT / 'build_slides_plan_docx.py').read_text(encoding='utf-8'))
node = next(n.value for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'slides' for t in n.targets))
slides = eval(compile(ast.Expression(node), '<slide metadata>', 'eval'), {'__builtins__': {}, 'dict': dict})

chapters = [
    ('Background and WHEN', '背景与预测调用时机', '1–5'),
    ('WHAT and HOW: From Failure to Repair', '信息需求与修复方法', '6–8'),
    ('Experimental Setup and Main Results', '实验设置与主要结果', '9–13'),
    ('Ablations, Analysis, and Conclusion', '消融、分析与总结', '14–18'),
]

# Each entry contains text that can be copied directly into the English slides.
copy = [
('From Prediction to Repair: World-Model Guidance for LLM Planning', [
 'CS5446 Project | National University of Singapore',
 'When should we ask a world model?', 'What information does the planner need?',
 'How can the model help the planner recover?'],
 'WHEN → WHAT → HOW', 'Scope: world-model advice for language-model planning in ALFWorld.'),
('Our Task: Text-Based Household Planning', [
 'Environment: ALFWorld household tasks with text observations and actions.',
 'Tasks: place, clean, heat, cool, inspect in light, and place two objects.',
 'Planner: an LLM that chooses the next action from the goal and history.',
 'World model (WM): an LLM used to predict what an action will do.',
 'Our question: how should WM advice help the planner complete the task?'],
 'The environment gives feedback; the planner acts; the WM advises.',
 'Our setup shows the current valid actions to the planner and allows up to 30 steps. Both models stay frozen. Example task: heat an apple and place it on a table.'),
('Existing Methods: Help and Open Problems', [
 'Methods differ in when they give advice and what knowledge they use.',
 'We compare four related approaches under the same evaluation setup.',
 'Starting question: can choosing better moments make forecasts useful?'],
 'We start with WHEN: when should the planner receive a forecast?',
 'The table describes our aligned baselines and their limits or questions. These are not full reproductions or claims that the original methods always fail.'),
('WHEN: Can Better Timing Make Forecasts Useful?', [
 'Start with a predictive interface: propose → forecast → choose again.',
 'Test always-on, random, confidence-based, and learned gates.',
 'Compare selective use with random use to test the value of timing.',
 'Also test whether more accurate forecasts lead to more task success.'],
 'Our tests find no reliable gain from timing alone.',
 'Separate historical studies: unseen134 (timing), dev600 (memory), 127 / 374 states (router). Timing 95% CI: [−2.7, 4.2] pp. SR = success rate; pp = percentage points.'),
('WHEN Finding: Forecasts Add Little beyond Trying Again', [
 'Use the same random trigger at 30% of steps.',
 'Resampling asks the planner again without new information.',
 'WM forecasts: +1.4 pp PR vs. resampling; not significant.',
 'True next observations: +3.0 pp PR; significant.'],
 'Next, WHAT information would help the planner recover?',
 'dev460; 2 runs per task. PR = subgoal progress rate. 95% CIs: WM [−0.4, 3.2], oracle [1.2, 4.8] pp; Holm p = 0.594 / 0.005.'),
('WHAT: The Planner Repeats Invalid Actions', [
 '31.3% of all proposed actions are invalid.',
 '74% of failed episodes end in a loop.',
 '84% of heat, cool, and clean attempts are invalid.',
 'These errors occur even with valid actions shown in the prompt.'],
 'The planner needs help meeting action preconditions.',
 'dev460; 2 runs per task. Loop ending: at most 4 distinct actions in the final 10 steps. Each percentage has a different denominator.'),
('WHAT: Explain the Failure and Give a First Step', [
 'Hold the invalid-action trigger fixed.',
 'At this trigger, the true next observation is “Nothing happens.”',
 'Oracle repair adds the missing condition and a valid first step.',
 'Oracle repair gains +4.2 pp PR over a failure notice.'],
 'Can a frozen WM provide this repair advice?',
 'dev460; 2 runs per task. Repair vs. failure notice: 95% CI [2.4, 6.0] pp; Holm p < 0.001. Oracle probe, not learned-WM performance.'),
('HOW: Diagnose, Suggest, and Let the Planner Decide', [
 'Check the proposed action against the environment’s valid-action list.',
 'If invalid, ask the WM for a reason and a first step.',
 'Discard suggested steps outside the valid-action list.',
 'Show the advice to the planner; the planner chooses the action.',
 'Both models stay frozen; the WM receives no explicit rule base.'],
 'The WM gives local advice; the planner keeps control.',
 'The check occurs before execution. “check valid actions” is exempt. Validation checks step validity, not the truth of the reason. No separate repair memory.'),
('Experimental Setup', [
 'ALFWorld: 6 task types; at most 30 steps per episode.',
 'Planner: Qwen3-4B-Instruct-2507; WM: Qwen3-14B, thinking off.',
 'dev460: method selection; 2 runs per task.',
 'fresh600: 100 tasks per type; 3 runs per condition.',
 'SR measures task completion; PR measures subgoal progress.'],
 'Freeze the method before running fresh600.',
 'fresh600 contains new task instances within the training scene distribution. 1,800 runs, 600 task-level units per condition; paired bootstrap with 20,000 resamples.'),
('What Do the Controls Test?', [
 'Failure notices and reflection test the value of trying again.',
 'Rule cards and oracle repair test the value of action knowledge.',
 'Aligned baselines test other ways to use models and knowledge.'],
 'Compare advice under a shared planner and evaluation set.',
 'Baseline mechanisms are aligned to this setup; the full original systems are not reproduced.'),
('Repair Improves Task Completion', [
 'Success rises from 20.9% to 36.2%: +15.3 pp.',
 'Repair adds +4.2 pp PR beyond a failure notice.',
 'Repair meets the −2 pp PR non-inferiority margin vs. rule cards.'],
 'Repair adds useful information beyond detecting failure.',
 'fresh600; 3 runs per task. 95% CIs: +15.3 SR [12.7, 17.8]; +4.2 PR [2.6, 5.7]; both Holm p < 0.001. Repair − rules: +2.2 PR [0.5, 3.9].'),
('Comparison with Aligned Baselines', [
 'Repair has higher SR than the tested WM and learned-insight baselines.',
 'RPMS-style rules and state remain competitive.',
 'Repair uses fewer online WM calls than judging or forecasting.'],
 'Repair is useful, but explicit rules remain a strong option.',
 'fresh600; 3 runs per task. Calls = online advisory-model calls per episode; offline learning costs are excluded. Calls do not measure latency or energy.'),
('Where Does Repair Help?', [
 'Repair improves SR over no intervention in all 6 task types.',
 'Repair leads rule cards on look-at, placement, cleaning, and cooling.',
 'Rule cards lead on heating and two-object placement.',
 'Handling more than one object remains difficult.'],
 'Repair helps across tasks, but does not solve every constraint.',
 'fresh600; 100 tasks per type, 3 runs each. Task-wise differences are descriptive, not corrected significance claims.'),
('Same Inputs, Different Outputs', [
 'Keep the WM, failure trigger, and input context fixed.',
 'Change the requested output: a forecast or repair advice.',
 'Repair gains +4.1 pp PR over equal-input prediction.'],
 'The requested output matters beyond the input information.',
 'fresh600; 3 runs per task. Repair − equal-input prediction: 95% CI [2.5, 5.7] pp; Holm p < 0.001.'),
('Which Repair Components Help?', [
 'Cause only: no significant PR gain over a failure notice.',
 'First step only: a higher observed PR.',
 'Cause + first step: the highest PR among these formats.'],
 'A useful next step works best with an explanation in this test.',
 'fresh600. Cause vs. notice: +0.8 pp [−0.5, 2.1]. Step vs. notice: +2.2 [0.6, 3.8]; full vs. step: +2.0 [0.3, 3.6]. The last two tests are secondary and uncorrected.'),
('Should Advice Persist or Be Executed Directly?', [
 'Keeping the last 5 diagnoses does not improve PR.',
 'Memory lowers SR by 4.4 pp in an exploratory comparison.',
 'Directly executing the suggested step gives no significant PR gain.'],
 'Neither change reliably improves progress in this test.',
 'fresh600. PR contrasts vs. repair: memory −1.0 pp [−2.5, 0.4]; direct execution +0.2 [−1.4, 1.8]. Direct execution differs from asking the 14B model to choose the action.'),
('Repair Helps after Object Pickup', [
 'Success after pickup rises from 44% to 66%.',
 'Target visibility and pickup improve by smaller amounts.',
 'Only about 30% of WM reasons match the reference cause category.',
 'Useful advice does not require every diagnosis to be correct.'],
 'The gains are consistent with better progress after pickup.',
 'fresh600. Conditional rates are descriptive and use different episode subsets. Cause matching covers 9,495 triggered steps; it does not establish a causal effect.'),
('From Prediction to Repair', [
 'WHEN: tested forecast schedules give no reliable extra benefit.',
 'WHAT: a missing-condition explanation and a first step help.',
 'HOW: a frozen WM can give useful repair advice.',
 'Main result: +15.3 pp SR; +4.1 pp PR over equal-input prediction.'],
 'Evaluate world-model advice by how it helps the next decision.',
 'Limits: requires a valid-action list; one environment and model family; fresh600 is not an OOD test. Stronger decision-makers perform better: 14B planner alone 59.1% SR; failure-step takeover 49.0% SR.'),
]

for s, (title, bullets, takeaway, footnote) in zip(slides, copy):
    s.update(en=title, points=bullets, takeaway=takeaway, footnote=footnote)
    s['chapter'] = 1 if s['n'] <= 5 else 2 if s['n'] <= 8 else 3 if s['n'] <= 13 else 4

slides[2]['table'] = (['Aligned baseline', 'How it helps', 'Limit / question in our study'], [
 ['WorldEvolver-style', 'Confidence-gated forecasts; optional memory', 'Do better forecasts and timing improve decisions?'],
 ['WALL-E-style', 'Judge each action; feedback; optional learned rules', 'Repeated judging adds online model calls.'],
 ['ExpeL-style', 'Add insights learned from past experience', 'Usefulness depends on when insights are shown.'],
 ['RPMS-style', 'Provide explicit rules and tracked state', 'Needs explicit rules and state tracking.']])
slides[3]['table'] = (['Test', 'Our finding', 'Implication'], [
 ['Selective vs. random (unseen134)', '+0.6 pp SR; CI includes zero', 'No clear benefit from selection'],
 ['Memory (dev600)', 'Forecast accuracy: 37.7% → 60–62%; SR: 22.8% → 22.3%', 'Prediction accuracy is not task success'],
 ['Learned router (127 / 374 states)', 'AUROC: 0.70–0.74 → 0.42–0.43 on new states', 'Routing does not generalize here']])
slides[4]['table'] = (['Condition', 'PR (%)'], [['No intervention', '32.8'], ['Resampling', '33.0'], ['WM forecast', '34.5'], ['Oracle observation', '36.0']])
slides[6]['table'] = (['Information', 'SR (%)', 'PR (%)'], [['Failure notice', '18.3', '36.7'], ['Legal projection', '14.2', '36.2'], ['Oracle cause + first step', '29.1', '41.0']])
slides[9]['table'] = (['Baseline', 'Mechanism'], [['WALL-E-style', 'Judge each action; feedback and revision'], ['WorldEvolver-style', 'Show confidence-gated forecasts'], ['ExpeL-style', 'Use 15 learned insights'], ['RPMS-style', 'Use rule cards and tracked state']])
slides[10]['table'] = (['Condition', 'SR (%)', 'PR (%)'], [['No intervention','20.9','39.4'],['Failure only','28.3','44.8'],['Generic reflection','28.6','45.9'],['Rule cards','33.3','46.8'],['WM repair','36.2','49.0'],['Oracle repair','36.7','47.5']])
slides[11]['table'] = (['Method','SR (%)','PR (%)','Calls / episode'], [['WM repair','36.2','49.0','5.3'],['WALL-E-style','26.8','48.2','54.5'],['RPMS-style','37.2','48.1','0'],['ExpeL-style, failure gate','28.1','43.4','0'],['WorldEvolver-style','22.1','41.4','25.9']])
slides[12]['table'] = (['Task type','None SR (%)','Rules SR (%)','Repair SR (%)'], [['Look at object in light','27.3','33.0','46.3'],['Pick and place','44.7','56.0','61.7'],['Clean then place','19.0','27.0','34.7'],['Cool then place','6.7','13.3','21.7'],['Heat then place','27.0','46.7','37.7'],['Place two objects','1.0','24.0','15.3']])
slides[13]['table'] = (['Output / input setting','PR (%)'],[['Original prediction','42.4'],['Prediction with repair inputs','44.9'],['Repair','49.0']])
slides[14]['table'] = (['Information shown','PR (%)'],[['Failure only','44.8'],['Cause only','45.6'],['First step only','47.0'],['Cause + first step','49.0']])
slides[15]['table'] = (['Variant','SR (%)','PR (%)'],[['WM repair','36.2','49.0'],['Retain 5 diagnoses','31.8','47.9'],['Execute suggested step','36.9','49.2']])
slides[16]['table'] = (['Condition','Saw target (%)','Picked target (%)','Success (%)','Success given pickup (%)'],[['None','54','47','20.9','44'],['Failure only','58','52','28.3','55'],['WM repair','60','55','36.2','66'],['Oracle repair','57','51','36.7','71']])

# Keep the Chinese production notes consistent with the revised opening.
slides[1].update(title='任务环境与两个模型的角色',
    source='report.tex: Introduction; Related Work; Shared Experimental Setup; tab:tasks。',
    visual='上方简述 ALFWorld 与六类任务；中部画 Planner–Environment 交互环，旁边放 WM 建议支路；底部用一个任务例子串联。此页先定义研究对象，不提前下 repair 结论。',
    note='Planner 和 WM 是本研究中 LLM 的不同角色；WM 不是实际环境，也不是已知真实转移规则的 oracle。此处先定义研究起点的预测角色，Slide 8 再介绍修复角色。')
slides[2].update(title='已有方法、对应基线与待解决问题',
    source='report.tex: Related Work; Study 3 / Aligned Baselines; tab:baselines。',
    visual='四行三列表：方法、提供的帮助、局限或待检验问题。方法名称与 Slide 10、12 完全对应。用强调色标记 WorldEvolver-style 行及底部 WHEN 切入问题。',
    note='WALL-E-style 的调用成本、ExpeL-style 的投放时机差异由后面的对齐实验支撑；RPMS-style 的规则依赖是适用条件，不代表它效果弱。这里不提前展示完整结果排名，也不把对齐实现的结果推广为原论文缺陷。')
slides[3].update(title='以 WHEN 为切入点：设计与初步发现',
    visual='顶部用 propose → forecast → choose again 定义预测接口；下方三个结果卡分别呈现 timing、memory、router 的发现与问题。每个卡片注明自己的数据集，不能连接成一条曲线。',
    note='先讲假设“也许只是问 WM 的时机不对”，再讲结果。选择性预测相对不干预虽有 +3.9 pp SR，但相对随机调用仅 +0.6 pp；因此必须用随机对照判断选择策略的价值。')
slides[4].update(title='WHEN 的关键对照与转向 WHAT',
    visual='左侧画 WM forecast 与 no-information resampling 两条分支，强调相同随机触发；右侧四根 PR 柱及区间；底部给出转向 WHAT 的问题。',
    note='WM forecast 相对 resampling 不显著，但 oracle observation 显著，说明预测信息仍可能有用；结论限于本研究测试的 WM 与时机策略。顺接 Slide 6：先分析 planner 实际卡在哪里，再决定应提供什么信息。')

repo = 'alfworld-preexp-npu/'
code = repo + 'preexperiments/react_study/'
results = repo + 'outputs/react_study/'
sources = {
 4: results+'step2_episodic_memory/; '+results+'p4_router/',
 5: results+'p3_mechanism_matrix/tables/p3_matrix.md',
 6: results+'failure_analysis/tables/failure_analysis.md',
 7: code+'agent.py (inv_fail / inv_proj / inv_repair); '+code+'preconditions.py',
 8: code+'agent.py (inv_wmrepair); '+code+'preconditions.py (wm_repair_block)',
 9: results+'p7_final/README.md',
 10: code+'baselines_r6.py',
 11: results+'p7_final/tables/final_fresh600.md',
 12: results+'r6_baselines/tables/baselines_fresh600.md',
 13: 'report.tex: tab:tasks',
 14: results+'p7_final/tables/confounds_followups.md; '+code+'preconditions.py (wm_pred_info)',
 15: code+'preconditions.py (wm_repair_block: mode); '+results+'p7_final/tables/confounds_followups.md',
 16: code+'agent.py (inv_wmrepair_exec / inv_wmrepair_mem); '+code+'preconditions.py (RepairMemory)',
 17: results+'failure_analysis/tables/deep_analysis.md',
 18: 'report_supplement.tex: Decision Authority and Memory Controls',
}

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.top_margin = sec.bottom_margin = Cm(1.6)
sec.left_margin = sec.right_margin = Cm(1.8)
for name, size in [('Normal',10),('Title',23),('Subtitle',13),('Heading 1',16),('Heading 2',11),('List Bullet',11)]:
    st = doc.styles[name]
    st.font.name = 'Calibri'; st.font.size = Pt(size)
    st.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'微软雅黑')
    st.paragraph_format.space_after = Pt(5)
    if name.startswith('Heading'): st.font.color.rgb = RGBColor.from_string('16324F')
sec.header.paragraphs[0].text = 'CS5446 | From Prediction to Repair | English Slide Copy'
f = sec.footer.paragraphs[0]; f.alignment = 2
field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'PAGE'); f._p.append(field)
doc.core_properties.title = 'WHEN–WHAT–HOW：四章结构与逐页英文 PPT 文案'

def para(label, value):
    p=doc.add_paragraph(); p.add_run(label+'：').bold=True; p.add_run(value)

def table(headers, rows):
    t=doc.add_table(rows=1,cols=len(headers)); t.style='Light Shading Accent 1'
    for c,v in zip(t.rows[0].cells,headers): c.text=v
    for row in rows:
        for c,v in zip(t.add_row().cells,row): c.text=str(v)
    for row in t.rows:
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for c in row.cells:
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(2)
                for r in p.runs: r.font.size=Pt(9)

doc.add_heading('四章结构与逐页英文 PPT 文案',0)
doc.add_paragraph('From Prediction to Repair:\nWorld-Model Guidance for LLM Planning',style='Subtitle')
para('版本','2026-11-08；18 页主讲 + 3 页备份；建议约 18–22 分钟。')
para('编排原则','开场按“任务环境与模型角色 → 已有方法及问题 → WHEN 的设计与发现 → WHAT → HOW”展开。保留 18 页与四章结构，第 1 页属于第一章，第 18 页属于第四章；不额外插入章节封面。')
table(['章节','英文章名（可直接用于目录）','页码'],[[str(i+1)+' · '+c[1],c[0],c[2]] for i,c in enumerate(chapters)])
doc.add_heading('如何使用',1)
for t in ['每页“英文标题 / 正文 / 图表 / 结论 / 脚注”均可直接复制到 PPT；中文仅供制作和讲解参考。',
          '正文以 3–5 条短句为主。图表以重画为主，表格是完整数据稿，不必与图重复展示。',
          '章节名放页眉或进度条。第 1 页可用四章名作底部导航；不增加目录页。',
          '关键数字按 report.tex 和仓库汇总表核对；没有重跑模型实验。区间按报告保留，差值来自未四舍五入的任务级估计。',
          '第 1 页成员名单请从团队确认名单填写；report.tex 仍含 Name Six / six@example.com 占位，不能直接照抄。',
          'SR = success rate；PR = progress rate；pp = percentage points；CI = confidence interval。首次出现写全称。']:
    doc.add_paragraph(t,style='List Bullet')

for s in slides:
    doc.add_page_break()
    doc.add_heading(f"Slide {s['n']:02d}｜{s['title']}",1)
    para('所属章节',f"Chapter {s['chapter']} — {chapters[s['chapter']-1][0]}")
    doc.add_heading('英文标题｜Title',2); doc.add_paragraph(s['en'])
    doc.add_heading('英文正文｜Slide bullets',2)
    for b in s['points']: doc.add_paragraph(b,style='List Bullet')
    if 'table' in s:
        doc.add_heading('英文图表文字与数据｜Chart / table copy',2); table(*s['table'])
    if s['n']==2:
        para('流程图英文','Goal + History + Valid actions → Planner → Proposed action → Environment → Observation → Planner; Advice branch: Proposed action + Context → WM → Predicted observation → Planner')
        para('示例框英文','Goal: Heat an apple and place it on a table. Action sequence: Pick up apple → Go to microwave → Heat apple → Go to table → Put apple on table. Illustrative sequence; each action needs the right conditions.')
    if s['n']==8:
        para('流程图英文','Propose action → Check valid actions → Valid: Execute | Invalid: WM reason + first step → Validate step → Planner revises → Execute')
        para('示例框英文','Illustrative example: Reason: You are already holding another object. Repair: Put the held object down first.')
    doc.add_heading('英文结论｜Takeaway',2); doc.add_paragraph(s['takeaway'])
    doc.add_heading('英文脚注｜Footnote',2); doc.add_paragraph(s['footnote'])
    para('版式建议（不上屏）',s['visual'])
    para('报告依据（不上屏）',s['source'])
    if s['n'] in sources: para('代码／结果定位（不上屏）',sources[s['n']])
    if 'note' in s: para('讲解提醒（不上屏）',s['note'])

backups = [
 ('B1','Development and Method Freeze',[
  'Select the method on dev460; 2 runs per task.',
  'WM repair reaches 26.5% SR and 42.2% PR.',
  'Freeze the method, prompts, decoding, and test-set hash before fresh600.',
  'Do not compare absolute dev460 and fresh600 scores as a method gain.'
 ],(['Condition','SR (%)','PR (%)'],[['Failure only','18.3','36.7'],['Generic reflection','18.7','37.8'],['Rule cards','26.4','40.9'],['WM prediction','15.3','35.1'],['WM repair','26.5','42.2'],['Oracle repair','29.1','41.0']]),
 'Method selection and final evaluation use different task sets.', 'report.tex: tab:development; p7_final/tables/preregistration_round5_final.json'),
 ('B2','Model Size and Decision Control',[
  'A 4B WM reaches 29.7% SR; its gain over a failure notice is not significant.',
  'Executing a suggested step differs from letting the 14B model choose.',
  'A 14B planner alone and failure-step takeover both outperform repair.',
  'The planner-controlled scope was chosen after observing takeover results.'
 ],(['Configuration','SR (%)','PR (%)'],[['4B planner + 4B WM repair','29.7','46.6'],['4B planner + 14B WM repair','36.2','49.0'],['Execute the repair step','36.9','49.2'],['14B takes over failing steps','49.0','58.3'],['14B planner alone','59.1','70.3']]),
 'Repair is useful advice, but is not the best model allocation tested.', 'report_supplement.tex: Model-Size Controls; Decision Authority and Memory Controls'),
 ('B3','Primary Tests and Rule-Based Variants',[
  'Average runs within each task before paired bootstrap sampling.',
  'Use 20,000 resamples; fresh600 has 600 task-level units.',
  'Apply Holm correction to H1 and H3; test H2 separately.',
  'Rule checking does not significantly beat simply adding rules and state.'
 ],(['Primary test','Contrast','Result'],[['H1','Repair − failure notice, PR','+4.2 pp [2.6, 5.7]'],['H2','Repair − rule cards, PR','+2.2 pp [0.5, 3.9]'],['H3','Repair − no intervention, SR','+15.3 pp [12.7, 17.8]']]),
 'Match each claim to its metric, control, and statistical test.', 'report.tex: tab:hypotheses; report_supplement.tex: Combining Repair with Explicit Rules'),
]
for num,title,bullets,tbl,takeaway,source in backups:
    doc.add_page_break(); doc.add_heading(f'Backup {num}｜{title}',1)
    para('用途','答疑备用，不计入四章主讲页数。')
    doc.add_heading('英文正文｜Slide bullets',2)
    for b in bullets: doc.add_paragraph(b,style='List Bullet')
    table(*tbl); para('Takeaway',takeaway); para('依据（不上屏）',source)
    if num=='B3': para('Footnote','95% paired bootstrap CIs. H2 margin: −2 pp PR; its lower CI bound must exceed the margin. Rule-checking comparisons are separate from H1–H3.')

doc.add_page_break(); doc.add_heading('制作与核对清单（不上屏）',1)
for t in ['18 页主讲各有英文标题、分条正文、结论与脚注；B1–B3 同样提供英文内容。',
          'Slide 4 是多个历史实验；Slide 5–7 是 dev460；Slide 11–17 是 fresh600。',
          'Slide 5 随机 30% 触发与 Slide 7 非法动作触发不能混为同一实验。',
          '合法性检查不保证诊断正确，也不保证建议是最优动作；Oracle 是局部信息参照，不是所有任务的严格上界。',
          'Main SR 的 20.9% → 36.2% 来自 fresh600；相同输入预测对比的 +4.1 pp 是 PR。',
          'Slide 17 的前三列是全体 episode 比例；最后一列只以已拾取目标的 episode 为分母，绘图时单独展示。',
          '报告中的表号可能随编辑变化，优先按 tab: 标签定位；代码及汇总表相对路径均从仓库根目录起算。']:
    doc.add_paragraph(t,style='List Bullet')

backup=OUT.with_name(OUT.stem+'_修改前备份.docx')
if OUT.exists() and not backup.exists(): shutil.copy2(OUT,backup)
try:
    doc.save(OUT)
except PermissionError:
    OUT = OUT.with_name(OUT.stem + '_开场修订版.docx')
    doc.save(OUT)
with zipfile.ZipFile(OUT) as z:
    assert z.testzip() is None
    for name in z.namelist():
        if name.endswith('.xml'): ElementTree.fromstring(z.read(name))
check=Document(OUT)
assert sum(p.text.startswith('Slide ') and p.style.name=='Heading 1' for p in check.paragraphs)==18
assert sum(p.text.startswith('Backup ') and p.style.name=='Heading 1' for p in check.paragraphs)==3
for s in slides:
    assert all(not re.search('[\u4e00-\u9fff]',b) for b in s['points']+[s['en'],s['takeaway'],s['footnote']])
    if 'table' in s: assert all(not re.search('[\u4e00-\u9fff]',v) for row in [s['table'][0]]+s['table'][1] for v in row)
print('Saved:',OUT)
print('Verified: 4 chapters, 18 main slides, 3 backup slides; English copy; DOCX/XML integrity.')

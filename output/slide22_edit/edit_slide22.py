from pathlib import Path
import shutil,zipfile,copy
from lxml import etree as E
import win32com.client as w

src=Path('E:/26fall/cs5446/cs5446-pre.pptx')
root=Path('E:/26fall/cs5446/cs5446-master/output/slide22_edit')
backup=src.with_name('cs5446-pre.before-slide22-responsibilities.pptx')
original=src.read_bytes()
if backup.exists():assert backup.read_bytes()==original or (root/'validated.pptx').read_bytes()==original,'Source changed externally'
else:shutil.copy2(src,backup)
work=root/'working.pptx';app=w.Dispatch('PowerPoint.Application')
for i in range(app.Presentations.Count,0,-1):
 q=app.Presentations(i)
 if q.FullName.lower().replace('\\','/')==str(work).lower().replace('\\','/'):
  q.Saved=True;q.Close()
shutil.copy2(backup,work)
p=app.Presentations.Open(str(work),False,False,False);s=p.Slides(22)
def rgb(h):return int(h[:2],16)+(int(h[2:4],16)<<8)+(int(h[4:],16)<<16)
title=next(x for x in s.Shapes if x.Id==26)
title.TextFrame.TextRange.Text='Team Responsibilities'
title.TextFrame.TextRange.Font.Name='Arial';title.TextFrame.TextRange.Font.Size=26
title.TextFrame.TextRange.Font.Bold=True;title.TextFrame.TextRange.Font.Color.RGB=rgb('003D7C')
rows=[
 ['Member','Primary responsibility','Specific tasks'],
 ['1','Infrastructure &\nevaluation protocol','Set up ALFWorld and model serving; implement ReAct interaction and action parsing. Manage task splits and repeated runs; implement task-level bootstrap, Holm correction and non-inferiority tests.'],
 ['2','WHEN: Forecasting &\ninvocation strategies','Evaluate random and confidence-gated forecasts, resampling and oracle observations. Study episodic memory, prediction quality, router generalization and prediction model-size comparisons.'],
 ['3','WHAT: Failure analysis &\noracle probes','Analyze invalid actions and loops; implement state tracking and precondition diagnosis. Compare failure notices, legal projection and oracle repair; analyze subgoal progress and inventory failures.'],
 ['4','HOW: WM repair &\nmain evaluation','Implement the invalid-action gate, repair prompts, output parsing, suggestion validation and planner revision. Select and freeze the method; evaluate fresh600, task-wise performance and unseen134.'],
 ['5','Aligned baselines &\nknowledge integration','Implement WALL-E-, WorldEvolver-, ExpeL- and RPMS-style baselines. Learn rules and insights, calibrate forecast gates, compare online costs, and evaluate rule concatenation and rule-checked repair.'],
 ['6','Ablations, capacity &\ndecision authority','Run equal-input and cause/step ablations; test diagnosis memory, direct execution and model takeover. Compare model sizes; analyze confounds and limitations, and integrate the discussion and conclusions.'],
]
shape=s.Shapes.AddTable(7,3,46,130,868,359);shape.Name='Team_responsibility_table'
t=shape.Table
for j,width in enumerate([80,220,568],1):t.Columns(j).Width=width
t.Rows(1).Height=29
for i in range(2,8):t.Rows(i).Height=55
for i,row in enumerate(rows,1):
 for j,value in enumerate(row,1):
  c=t.Cell(i,j);sh=c.Shape;sh.Fill.Solid()
  sh.Fill.ForeColor.RGB=rgb('003D7C' if i==1 else ('EDF3F9' if i%2==0 else 'F8FAFC'))
  tf=sh.TextFrame;tf.MarginLeft=8;tf.MarginRight=8;tf.MarginTop=4;tf.MarginBottom=4
  tf.WordWrap=True;tf.VerticalAnchor=3
  tr=tf.TextRange;tr.Text=value;tr.Font.Name='Arial';tr.Font.Size=14 if i==1 else (13.5 if j<3 else 12.5)
  tr.Font.Bold=(i==1 or j<3);tr.Font.Color.RGB=rgb('FFFFFF' if i==1 else ('003D7C' if j<3 else '263747'))
  tr.ParagraphFormat.Alignment=2 if j==1 else 1
  tr.ParagraphFormat.SpaceBefore=0;tr.ParagraphFormat.SpaceAfter=0
  for k in range(1,5):c.Borders(k).ForeColor.RGB=rgb('FFFFFF');c.Borders(k).Weight=1
  assert tr.BoundHeight<=sh.Height-7,(i,j,tr.BoundHeight,sh.Height)
  assert tr.BoundWidth<=sh.Width-14,(i,j,tr.BoundWidth,sh.Width)
foot=s.Shapes.AddTextbox(1,46,496,850,26);foot.Name='Shared_team_responsibilities'
tf=foot.TextFrame;tf.MarginLeft=tf.MarginRight=tf.MarginTop=tf.MarginBottom=0
tr=tf.TextRange;tr.Text='Shared responsibilities: write and present each assigned section; cross-check results and code; jointly review the report and slides.'
tr.Font.Name='Arial';tr.Font.Size=11;tr.Font.Color.RGB=rgb('536273')
p.Save();p.Close()
# Only slide 22 is changed; all other original package parts are preserved.
part='ppt/slides/slide22.xml'
with zipfile.ZipFile(work) as z:updated=z.read(part)
final=root/'validated.pptx'
with zipfile.ZipFile(backup) as zin,zipfile.ZipFile(final,'w') as zout:
 for info in zin.infolist():zout.writestr(info,updated if info.filename==part else zin.read(info.filename))
with zipfile.ZipFile(backup) as a,zipfile.ZipFile(final) as b:
 changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
 assert changed==[part],changed
 assert b.testzip() is None
p=app.Presentations.Open(str(final),True,False,False)
p.Slides(22).Export(str(root/'after.png'),'PNG',1600,900);p.Close()
assert src.read_bytes()==original,'Source changed during editing'
shutil.copyfile(final,src)
print('Saved',src,'; changed:',changed)

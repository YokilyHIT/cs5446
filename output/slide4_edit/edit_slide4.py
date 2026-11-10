from pathlib import Path
import shutil, zipfile, hashlib
import win32com.client as win32

root = Path('E:/26fall/cs5446/cs5446-master/output/slide4_edit')
src = Path('E:/26fall/cs5446/cs5446-pre.pptx')
backup = src.with_name('cs5446-pre.before-slide4-addition.pptx')
original = src.read_bytes()
if backup.exists():
    assert backup.read_bytes()==original, 'Source differs from backup'
else:
    shutil.copy2(src, backup)
work = root / 'working.pptx'
app = win32.Dispatch('PowerPoint.Application')
for i in range(app.Presentations.Count,0,-1):
    opened=app.Presentations(i)
    if opened.FullName.lower().replace('\\','/')==str(work).lower().replace('\\','/'):
        opened.Saved=True
        opened.Close()
shutil.copy2(src, work)
p = app.Presentations.Open(str(work), False, False, False)
s = p.Slides(4)
def rgb(h):
    return int(h[0:2],16) + (int(h[2:4],16)<<8) + (int(h[4:6],16)<<16)
navy, orange, gray = '003D7C', 'D97000', '536273'
added=[]
def text(label,x,y,w,h,size=14,bold=False,color=navy,align=1):
    sh=s.Shapes.AddTextbox(1,x,y,w,h)
    sh.Name='Added_S4_'+str(len(added))
    tf=sh.TextFrame
    tf.MarginLeft=0;tf.MarginRight=0;tf.MarginTop=0;tf.MarginBottom=0
    tf.WordWrap=True;tf.AutoSize=0
    tr=tf.TextRange;tr.Text=label
    tr.Font.Name='Arial';tr.Font.Size=size;tr.Font.Bold=bold;tr.Font.Color.RGB=rgb(color)
    tr.ParagraphFormat.Alignment=align
    added.append(sh)
    return sh
def box(label,x,y,w,h,fill='EDF3F9',color=navy,size=14,bold=False):
    sh=s.Shapes.AddShape(5,x,y,w,h)
    sh.Name='Added_S4_'+str(len(added))
    sh.Fill.Solid();sh.Fill.ForeColor.RGB=rgb(fill)
    sh.Line.ForeColor.RGB=rgb('B6C8DA');sh.Line.Weight=0.8
    tf=sh.TextFrame;tf.MarginLeft=5;tf.MarginRight=5;tf.MarginTop=2;tf.MarginBottom=2
    tf.WordWrap=True;tf.AutoSize=0;tf.VerticalAnchor=3
    tr=tf.TextRange;tr.Text=label;tr.Font.Name='Arial';tr.Font.Size=size;tr.Font.Bold=bold
    tr.Font.Color.RGB=rgb(color);tr.ParagraphFormat.Alignment=2
    added.append(sh);return sh
def line(x1,y1,x2,y2,color=navy,arrow=True):
    sh=s.Shapes.AddLine(x1,y1,x2,y2)
    sh.Name='Added_S4_'+str(len(added));sh.Line.ForeColor.RGB=rgb(color);sh.Line.Weight=1.4
    if arrow:sh.Line.EndArrowheadStyle=3
    added.append(sh)

text('INTERACTION LOOP',56,265,230,17,12,True)
nodes=[(56,180,'Goal + History +\nValid actions'),(266,98,'Planner'),(394,118,'Proposed action'),(552,128,'Environment'),(720,136,'Observation')]
for x,w,label in nodes:
    box(label,x,287,w,37,fill=navy if label=='Planner' else 'EDF3F9',color='FFFFFF' if label=='Planner' else navy,size=13.5,bold=label=='Planner')
for left,right in zip(nodes,nodes[1:]):line(left[0]+left[1]+3,305.5,right[0]-4,305.5)
line(788,324,788,339,arrow=False)
line(788,339,315,339,arrow=False)
line(315,339,315,325)

text('ADVICE BRANCH',56,350,150,17,12,True,orange)
advice=[(56,224,'Proposed action + Context'),(320,86,'WM'),(446,208,'Predicted observation'),(704,152,'Planner')]
for x,w,label in advice:
    box(label,x,372,w,35,fill='FFF5E9',color=orange,size=13.5,bold=label in ('WM','Planner'))
for left,right in zip(advice,advice[1:]):line(left[0]+left[1]+3,389.5,right[0]-4,389.5,color=orange)

bg=box('',56,426,800,77,fill='F5F7FA')
text('Goal: Heat an apple and place it on a table.',69,435,770,19,14,True)
text('Action sequence: Pick up apple → Go to microwave → Heat apple → Go to table → Put apple on table.',69,460,773,18,12.5,False,'263747')
text('Illustrative sequence; each action needs the right conditions.',69,483,770,16,11.5,False,gray)
overflow=[]
for sh in added:
    if sh.HasTextFrame and sh.TextFrame.HasText:
        tr=sh.TextFrame.TextRange
        if tr.BoundHeight>sh.Height+1 or tr.BoundWidth>sh.Width+1:
            overflow.append((sh.Name,tr.Text,tr.BoundWidth,tr.BoundHeight,sh.Width,sh.Height))
print('text_overflow',overflow)
if overflow:raise RuntimeError('Text overflow')
p.Save()
s.Export(str(root/'after.png'),'PNG',1600,900)
p.Close()
# Preserve every other slide and all other package parts byte-for-byte.
with zipfile.ZipFile(work) as z: updated=z.read('ppt/slides/slide4.xml')
tmp=root/'validated.pptx'
with zipfile.ZipFile(backup) as zin,zipfile.ZipFile(tmp,'w') as zout:
    for info in zin.infolist():
        zout.writestr(info,updated if info.filename=='ppt/slides/slide4.xml' else zin.read(info.filename))
with zipfile.ZipFile(backup) as a,zipfile.ZipFile(tmp) as b:
    changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
    assert changed==['ppt/slides/slide4.xml'],changed
    assert b.testzip() is None
if src.read_bytes()!=original:raise RuntimeError('Source changed during edit')
shutil.copyfile(tmp,src)
print('Saved:',src)
print('Backup:',backup)
print('Changed package parts:',changed)

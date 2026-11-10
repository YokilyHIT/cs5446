from pathlib import Path
import shutil,zipfile,copy
import win32com.client as w
from lxml import etree as E

src=Path('E:/26fall/cs5446/cs5446-pre.pptx')
root=Path('E:/26fall/cs5446/cs5446-master/output/slide21_edit')
backup=src.with_name('cs5446-pre.before-slide21-comparison.pptx')
original=src.read_bytes()
if backup.exists():assert backup.read_bytes()==original,'Backup differs'
else:shutil.copy2(src,backup)
work=root/'working.pptx'
app=w.Dispatch('PowerPoint.Application')
for i in range(app.Presentations.Count,0,-1):
 q=app.Presentations(i)
 if q.FullName.lower().replace('\\','/')==str(work).lower().replace('\\','/'):
  q.Saved=True;q.Close()
shutil.copy2(src,work)
p=app.Presentations.Open(str(work),False,False,False);s=p.Slides(21)
before_ids={x.Id for x in s.Shapes}
def rgb(h):return int(h[:2],16)+(int(h[2:4],16)<<8)+(int(h[4:],16)<<16)
navy='003D7C';orange='D97000';gray='536273';added=[]
def text(txt,x,y,width,height,size=13,bold=False,color=navy):
 sh=s.Shapes.AddTextbox(1,x,y,width,height);sh.Name='Comparison_'+str(len(added))
 tf=sh.TextFrame;tf.MarginLeft=0;tf.MarginRight=0;tf.MarginTop=0;tf.MarginBottom=0
 tf.WordWrap=True;tf.AutoSize=0
 tr=tf.TextRange;tr.Text=txt;tr.Font.Name='Arial';tr.Font.Size=size;tr.Font.Bold=bold;tr.Font.Color.RGB=rgb(color)
 tr.ParagraphFormat.SpaceBefore=0;tr.ParagraphFormat.SpaceAfter=0
 sh.Height=height;sh.Width=width
 added.append(sh);return sh
def card(y,height):
 sh=s.Shapes.AddShape(5,535,y,382,height);sh.Name='Comparison_card_'+str(len(added))
 sh.Fill.Solid();sh.Fill.ForeColor.RGB=rgb('F2F6FA');sh.Line.ForeColor.RGB=rgb('C4D3E2');sh.Line.Weight=0.8
 added.append(sh)
def arrow(y):
 sh=s.Shapes.AddLine(711,y,733,y);sh.Line.ForeColor.RGB=rgb(orange);sh.Line.Weight=1.6;sh.Line.EndArrowheadStyle=3
 added.append(sh)

text('Compared with',535,131,382,25,20,True)
data=[
 (170,94,'Predictive guidance','WorldEvolver-style','Cause + a recovery\nstep','More actionable\nrevision guidance'),
 (277,94,'Per-action judging','WALL-E-style','Environment-based\ninvalid-action trigger','Fewer online\nadvisory calls'),
 (384,110,'Insights / explicit rules','ExpeL- / RPMS-style','Local advice without\na supplied rule base\nor insight collection','Less reliance on\nseparately built\nknowledge'),
]
for y,h,title,method,left,right in data:
 card(y,h)
 text(title,548,y+9,240,18,14,True)
 text(method,548,y+28,335,16,11,False,gray)
 text('Our distinction',548,y+47,155,15,11,True,navy)
 text('Advantage',743,y+47,160,15,11,True,orange)
 text(left,548,y+64,158,h-65,12,False,navy)
 text(right,743,y+64,160,h-65,12,False,navy)
 arrow(y+76)
text('Aligned implementations; rules remain competitive.',535,501,374,14,10,False,gray)
for sh in added:
 if sh.HasTextFrame and sh.TextFrame.HasText:
  tr=sh.TextFrame.TextRange
  assert tr.BoundHeight<=sh.Height+1,(tr.Text,tr.BoundHeight,sh.Height)
  assert tr.BoundWidth<=sh.Width+1,(tr.Text,tr.BoundWidth,sh.Width)
p.Save();p.Close()
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
part='ppt/slides/slide21.xml'
with zipfile.ZipFile(backup) as z:base=E.fromstring(z.read(part))
with zipfile.ZipFile(work) as z:edited=E.fromstring(z.read(part))
dest=base.find('p:cSld/p:spTree',ns)
for el in edited.find('p:cSld/p:spTree',ns):
 ids=el.xpath('.//p:cNvPr/@id',namespaces=ns)
 if ids and int(ids[0]) not in before_ids:dest.append(copy.deepcopy(el))
updated=E.tostring(base,xml_declaration=True,encoding='UTF-8',standalone=True)
final=root/'validated.pptx'
with zipfile.ZipFile(backup) as zin,zipfile.ZipFile(final,'w') as zout:
 for info in zin.infolist():zout.writestr(info,updated if info.filename==part else zin.read(info.filename))
with zipfile.ZipFile(backup) as a,zipfile.ZipFile(final) as b:
 changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
 assert changed==[part],changed
 assert b.testzip() is None
p=app.Presentations.Open(str(final),True,False,False)
p.Slides(21).Export(str(root/'after.png'),'PNG',1600,900);p.Close()
assert src.read_bytes()==original,'Source changed during edit'
shutil.copyfile(final,src)
print('Saved',src,'; changed:',changed)

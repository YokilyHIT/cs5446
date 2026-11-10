from pathlib import Path
import shutil,zipfile
import win32com.client as w

src=Path('E:/26fall/cs5446/cs5446-pre.pptx')
root=Path('E:/26fall/cs5446/cs5446-master/output/slide8_edit')
backup=src.with_name('cs5446-pre.before-slide8-table.pptx')
original=src.read_bytes()
if backup.exists():
    assert backup.read_bytes()==original,'Backup differs from source'
else:shutil.copy2(src,backup)
work=root/'working.pptx'
app=w.Dispatch('PowerPoint.Application')
for i in range(app.Presentations.Count,0,-1):
    q=app.Presentations(i)
    if q.FullName.lower().replace('\\','/')==str(work).lower().replace('\\','/'):
        q.Saved=True;q.Close()
shutil.copy2(src,work)
p=app.Presentations.Open(str(work),False,False,False)
s=p.Slides(8)
def rgb(h):return int(h[:2],16)+(int(h[2:4],16)<<8)+(int(h[4:],16)<<16)
rows=[
 ['Information','SR (%)','PR (%)'],
 ['Failure notice','18.3','36.7'],
 ['Legal projection','14.2','36.2'],
 ['Oracle cause + first step','29.1','41.0'],
]
sh=s.Shapes.AddTable(4,3,100,252,760,220)
sh.Name='Oracle_information_comparison_table'
t=sh.Table
for j,width in enumerate([440,160,160],1):t.Columns(j).Width=width
t.Rows(1).Height=46
for i in range(2,5):t.Rows(i).Height=58
for i,row in enumerate(rows,1):
    for j,value in enumerate(row,1):
        cell=t.Cell(i,j);shape=cell.Shape
        shape.Fill.Solid();shape.Fill.ForeColor.RGB=rgb('003D7C' if i==1 else ('E3EDF7' if i==4 else ('EDF3F9' if i%2==0 else 'F8FAFC')))
        tf=shape.TextFrame
        tf.MarginLeft=12;tf.MarginRight=12;tf.MarginTop=6;tf.MarginBottom=6
        tf.WordWrap=True;tf.VerticalAnchor=3
        tr=tf.TextRange;tr.Text=value
        tr.Font.Name='Arial';tr.Font.Size=18
        tr.Font.Bold=(i==1 or i==4)
        tr.Font.Color.RGB=rgb('FFFFFF' if i==1 else ('003D7C' if j==1 else '263747'))
        tr.ParagraphFormat.Alignment=1 if j==1 else 2
        tr.ParagraphFormat.SpaceBefore=0;tr.ParagraphFormat.SpaceAfter=0
        for k in range(1,5):
            edge=cell.Borders(k);edge.ForeColor.RGB=rgb('FFFFFF');edge.Weight=1.2
        assert tr.BoundHeight<=shape.Height-10,(i,j,'height overflow')
        assert tr.BoundWidth<=shape.Width-20,(i,j,'width overflow')
p.Save();p.Close()
p=app.Presentations.Open(str(work),True,False,False)
p.Slides(8).Export(str(root/'after.png'),'PNG',1600,900)
p.Close()
with zipfile.ZipFile(work) as z:updated=z.read('ppt/slides/slide8.xml')
tmp=root/'validated.pptx'
with zipfile.ZipFile(backup) as zin,zipfile.ZipFile(tmp,'w') as zout:
    for info in zin.infolist():zout.writestr(info,updated if info.filename=='ppt/slides/slide8.xml' else zin.read(info.filename))
with zipfile.ZipFile(backup) as a,zipfile.ZipFile(tmp) as b:
    changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
    assert changed==['ppt/slides/slide8.xml'],changed
    assert b.testzip() is None
assert src.read_bytes()==original,'Source changed during editing'
shutil.copyfile(tmp,src)
print('Saved',src)
print('Changed parts:',changed)
print('Backup',backup)

from pathlib import Path
import shutil,zipfile,copy
from lxml import etree as E
from PIL import Image
import win32com.client as w

src=Path('E:/26fall/cs5446/cs5446-pre.pptx')
root=Path('E:/26fall/cs5446/cs5446-master/output/slide14_edit')
backup=src.with_name('cs5446-pre.before-slide14-figure.pptx')
original=src.read_bytes()
if backup.exists():assert backup.read_bytes()==original,'Backup differs'
else:shutil.copy2(src,backup)
work=root/'working.pptx';shutil.copy2(src,work)
app=w.Dispatch('PowerPoint.Application')
p=app.Presentations.Open(str(work),False,False,False);s=p.Slides(14)
body=None
for shape in s.Shapes:
    if shape.HasTextFrame and shape.TextFrame.HasText and 'ALFWorld:' in shape.TextFrame.TextRange.Text:
        body=shape;break
assert body is not None
body.Width=535
tr=body.TextFrame.TextRange
tr.Replace('Eveluation sets:','Evaluation sets:')
tr.Replace('3 runs per condition.','3 runs per task per condition.')
body_id=body.Id
im=root/'alfworld_task_types.png'
iw,ih=Image.open(im).size
pw=300;ph=pw*ih/iw
pic=s.Shapes.AddPicture(str(im),False,True,610,132,pw,ph)
pic.Name='ALFWorld_six_task_types';pic.AlternativeText='Six ALFWorld task types: pick and place, clean and place, heat and place, cool and place, look in light, and pick two and place. Conceptual illustrations.'
pic_id=pic.Id
assert tr.BoundTop+tr.BoundHeight<502
p.Save();p.Close()
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
slide='ppt/slides/slide14.xml';rel='ppt/slides/_rels/slide14.xml.rels'
with zipfile.ZipFile(backup) as z:
    base=E.fromstring(z.read(slide));rels=E.fromstring(z.read(rel))
with zipfile.ZipFile(work) as z:edited=E.fromstring(z.read(slide))
def find_shape(tree,sid):return tree.xpath('.//p:cNvPr[@id="%s"]/../..'%sid,namespaces=ns)[0]
oldbody=find_shape(base,body_id);newbody=find_shape(edited,body_id)
oldbody.getparent().replace(oldbody,copy.deepcopy(newbody))
newpic=copy.deepcopy(find_shape(edited,pic_id))
rid='rIdCodexTaskTypes'
assert not any(x.get('Id')==rid for x in rels)
newpic.find('.//a:blip',ns).set('{'+ns['r']+'}embed',rid)
base.find('p:cSld/p:spTree',ns).append(newpic)
E.SubElement(rels,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',Id=rid,Type=ns['r']+'/image',Target='../media/codex_slide14_task_types.png')
updates={slide:E.tostring(base,xml_declaration=True,encoding='UTF-8',standalone=True),rel:E.tostring(rels,xml_declaration=True,encoding='UTF-8',standalone=True)}
final=root/'validated.pptx'
with zipfile.ZipFile(backup) as zin,zipfile.ZipFile(final,'w') as zout:
    ct=E.fromstring(zin.read('[Content_Types].xml'))
    assert any(x.get('Extension')=='png' for x in ct),'PNG type not declared'
    for info in zin.infolist():zout.writestr(info,updates.get(info.filename,zin.read(info.filename)))
    zout.writestr('ppt/media/codex_slide14_task_types.png',im.read_bytes())
with zipfile.ZipFile(backup) as a,zipfile.ZipFile(final) as b:
    changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
    assert set(changed)=={slide,rel},changed
    assert b.testzip() is None
p=app.Presentations.Open(str(final),True,False,False)
p.Slides(14).Export(str(root/'after.png'),'PNG',1600,900)
p.Close()
assert src.read_bytes()==original,'Source changed during edit'
shutil.copyfile(final,src)
print('Saved',src,'; changed existing parts:',changed)

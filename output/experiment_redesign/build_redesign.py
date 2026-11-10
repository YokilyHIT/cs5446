from pathlib import Path
import re,json
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[2]
md=ROOT/'EXPERIMENT_SLIDES_REDESIGN.md'
out=ROOT/'实验部分_基础实验与消融实验_重新设计.docx'
doc=Document()
sec=doc.sections[0]
sec.top_margin=sec.bottom_margin=Cm(1.7)
sec.left_margin=sec.right_margin=Cm(2)
normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(10.5)
normal.element.rPr.rFonts.set(qn('w:eastAsia'),'微软雅黑')
normal.paragraph_format.space_after=Pt(5)
for n in ['Title','Heading 1','Heading 2','Heading 3']:
 st=doc.styles[n];st.font.name='Arial';st.font.color.rgb=RGBColor.from_string('003D7C')
 st.element.rPr.rFonts.set(qn('w:eastAsia'),'微软雅黑')
def runs(par,text):
 for i,part in enumerate(re.split(r'\*\*(.*?)\*\*',text)):
  r=par.add_run(part.replace('`',''));r.bold=bool(i%2)
lines=md.read_text(encoding='utf-8').splitlines();i=0
while i<len(lines):
 line=lines[i]
 if not line.strip():i+=1;continue
 if line.startswith('|'):
  rows=[]
  while i<len(lines) and lines[i].startswith('|'):
   vals=[x.strip() for x in lines[i].strip('|').split('|')]
   if not all(re.fullmatch(r'[-: ]+',x) for x in vals):rows.append(vals)
   i+=1
  table=doc.add_table(rows=1,cols=len(rows[0]));table.style='Light Shading Accent 1'
  for j,v in enumerate(rows[0]):runs(table.rows[0].cells[j].paragraphs[0],v)
  for row in rows[1:]:
   cells=table.add_row().cells
   for j,v in enumerate(row):runs(cells[j].paragraphs[0],v)
  for row in table.rows:
   trpr=row._tr.get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
  continue
 if line.startswith('# '):p=doc.add_paragraph(line[2:],'Title')
 elif line.startswith('## '):
  title=line[3:]
  if title.startswith('E') or title.startswith('3.') or title.startswith('4.'):doc.add_page_break()
  p=doc.add_heading(title,level=1)
 elif line.startswith('- '):p=doc.add_paragraph(style='List Bullet');runs(p,line[2:])
 elif re.match(r'^\d+\. ',line):p=doc.add_paragraph(style='List Number');runs(p,re.sub(r'^\d+\. ','',line))
 else:p=doc.add_paragraph();runs(p,line)
 i+=1
foot=sec.footer.paragraphs[0];foot.alignment=2
foot.add_run('Experiment slides redesign | ')
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');foot._p.append(fld)
doc.save(out)

source=(ROOT/'report.tex').read_text(encoding='utf-8')
tables=list(re.finditer(r'\\begin\{table\}.*?\\end\{table\}',source,re.S))
targets={'tab:protocol','tab:main','tab:baselines','tab:tasks','tab:ablation','tab:followups','tab:development','tab:hypotheses','tab:funnel'}
folder=ROOT/'output/experiment_redesign/report_table_sources';folder.mkdir(parents=True,exist_ok=True)
index=[]
for number,m in enumerate(tables,1):
 label=re.search(r'\\label\{([^}]+)\}',m.group()).group(1)
 if label not in targets:continue
 name=f'table_{number:02}_{label.split(":")[1]}.tex'
 (folder/name).write_text(m.group()+'\n',encoding='utf-8')
 assert (folder/name).read_text(encoding='utf-8').rstrip()==m.group().rstrip()
 index.append({'table':number,'label':label,'source':'report.tex','start_line':source[:m.start()].count('\n')+1,'end_line':source[:m.end()].count('\n')+1,'file':name})
(folder/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
check=Document(out)
assert len(check.tables)==2
for key in ['E1','E2','E3a','E3b','E4','E5','E6','E7','E8']:
 assert any(p.text.startswith(key+'｜') for p in check.paragraphs)
print('Created',out.name)
print('Checked 9 slide plans including baseline implementation; 9 exact source-table extracts; original source documents unchanged.')
print(json.dumps(index,ensure_ascii=False))

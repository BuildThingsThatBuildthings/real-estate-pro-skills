#!/usr/bin/env python3
"""Render a source-led flyer plus readable branded Markdown handoff PDFs."""
import argparse,json,re
from production_inputs import Inputs
from pathlib import Path
import qrcode
from PIL import Image,ImageOps
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

def main():
 inputs=Inputs()
 def source(path):
  path=Path(path).resolve();inputs.read(path);return path
 def read(path):return inputs.read(path).decode('utf-8')
 p=argparse.ArgumentParser();p.add_argument('run');p.add_argument('--context-dir',default='context');p.add_argument('--output-prefix',default='');a=p.parse_args();r=Path(a.run);ctx=r/a.context_dir;b=json.loads(read(ctx/'brand.json'));facts=json.loads(read(ctx/'flyer.json'))
 for weight in [400,700]:pdfmetrics.registerFont(TTFont('Brand'+str(weight),str(source(r/b.get('fonts',{}).get(str(weight),'working/inter-'+str(weight)+'.ttf')))))
 out=r/a.output_prefix/facts['output_folder'];out.mkdir(exist_ok=True,parents=True);qrpath=r/a.output_prefix/facts.get('qr_output',str(Path(facts['output_folder'])/'listing-qr.png'));qrpath.parent.mkdir(parents=True,exist_ok=True);qr=qrcode.make(facts['url']);qr.save(qrpath)
 c=canvas.Canvas(str(out/(facts['id']+'.pdf')),pagesize=(612,792));c.setTitle(facts['address']+' | '+b['name']);c.setFillColor(HexColor(b['paper']));c.rect(0,0,612,792,fill=1,stroke=0);c.setFillColor(HexColor(b['red']));c.rect(0,782,612,10,fill=1,stroke=0)
 def txt(x,y,s,size=12,bold=False):c.setFillColor(HexColor(b['dark']));c.setFont('Brand700' if bold else 'Brand400',size);c.drawString(x,y,s)
 txt(36,747,b['name'].upper(),11,True);txt(36,714,facts['address'],25,True);txt(36,691,facts['location'],12)
 def photo(name,xy,size,focal=(.5,.5)):
  image=Image.open(source(r/facts.get('photos_folder','assets/photos')/name)).convert('RGB');image=ImageOps.fit(image,(int(size[0]*2),int(size[1]*2)),Image.Resampling.LANCZOS,centering=focal)
  c.drawImage(ImageReader(image),*xy,width=size[0],height=size[1])
 photo(facts['hero'],(36,365),(540,306),tuple(facts.get('hero_focal',[.5,.2])))
 txt(36,342,facts['price'],26,True);txt(205,347,facts['summary'],13,True)
 photo(facts['detail_photos'][0],(36,205),(260,118));photo(facts['detail_photos'][1],(316,205),(260,118))
 txt(36,183,facts['hook'],15,True)
 for i,line in enumerate(facts['features']):txt(36,160-i*18,line,10)
 c.drawImage(ImageReader(qrpath),472,105,width=100,height=100);txt(456,91,facts.get('qr_label','View listing'),8,True)
 c.setStrokeColor(HexColor(b['red']));c.line(36,78,576,78);txt(36,58,b['agent']+', REALTOR®',12,True);txt(36,41,'C '+b['phone']+('  |  O '+b['officePhone'] if b.get('officePhone') else ''),10);txt(36,25,b['website']+'  ·  '+b.get('licenseLabel','License #')+b['license'],9)
 c.drawImage(ImageReader(source(r/b.get('assets_folder','assets')/b['logo_source'])),410,40,width=160,height=35,mask='auto',preserveAspectRatio=True);txt(416,25,b['brokerage'],9);c.save()
 pdfmetrics.registerFontFamily('Brand400',normal='Brand400',bold='Brand700',italic='Brand400',boldItalic='Brand700')
 styles=getSampleStyleSheet();styles.add(ParagraphStyle('BrandBody',fontName='Brand400',fontSize=10,leading=15,spaceAfter=9));styles.add(ParagraphStyle('BrandH1',fontName='Brand700',fontSize=23,leading=28,spaceBefore=16,spaceAfter=18,textColor=HexColor(b['dark'])));styles.add(ParagraphStyle('BrandH3',fontName='Brand700',fontSize=10,leading=15,spaceBefore=10,spaceAfter=5,keepWithNext=True));styles.add(ParagraphStyle('BrandH2',fontName='Brand700',fontSize=15,leading=20,spaceBefore=15,spaceAfter=10,textColor=HexColor(b['red'])))
 def footer(can,doc):
  can.setFont('Brand400',8);can.setFillColor(HexColor(b['dark']));can.drawString(40,25,b['name']+' · '+b['brokerage']);can.drawRightString(572,25,str(doc.page))
 targets=json.loads(read(ctx/'documents.json'))
 for target in targets:
  item={'source':target} if isinstance(target,str) else target
  file=r/item['source'];pdfout=r/a.output_prefix/item.get('output',str(Path(item['source']).with_suffix('.pdf')))
  pdfout.parent.mkdir(parents=True,exist_ok=True)
  flow=[]
  options_path=r/'context/document-options.json'
  options=json.loads(read(options_path)).get(str(file.relative_to(r)),{}) if options_path.exists() else {}
  content=read(file).translate(str.maketrans({"'":'’','"':'”'}))
  if item.get('sections'):
   parts=re.split(r'(?m)(?=^## )',content)
   content='# '+item.get('title',file.stem)+'\n\n'+'\n\n'.join(section for section in parts if section.splitlines() and section.splitlines()[0].removeprefix('## ') in item['sections'])
  contact=b['name']+' · '+b['brokerage']+'<br/>C '+b['phone']+(' / O '+b['officePhone'] if b.get('officePhone') else '')
  flow.append(Paragraph(contact,styles['BrandBody']))
  if item.get('contact_instruction'):flow.append(Paragraph('Include the contact block above with every public post.',styles['BrandBody']))
  for block in re.sub(r'(?m)^(#{1,3} )',r'\n\n\1',content).split('\n\n'):
   block=block.strip()
   if not block:continue
   kind='BrandBody'
   if block.startswith('### '):kind='BrandH3';block=block[4:]
   elif block.startswith('# '):kind='BrandH1';block=block[2:]
   elif block.startswith('## '):
    kind='BrandH2';block=block[3:]
    if options.get('one_page_per_numbered_section') and re.match(r'^\d+\.',block):flow.append(PageBreak())
   if block.startswith('|'):
    for line in block.splitlines():
     if not re.match(r'^\|[-| :]+\|$',line):flow.append(Paragraph(line.replace('|',' · '),styles['BrandBody']))
    continue
   block=block.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;');block=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',block);block=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'<link href="\2" color="#D71920">\1</link>',block);block=block.replace('\n','<br/>')
   flow.append(Paragraph(block,styles[kind]))
  SimpleDocTemplate(str(pdfout),pagesize=(612,792),leftMargin=40,rightMargin=40,topMargin=35,bottomMargin=50).build(flow,onFirstPage=footer,onLaterPages=footer)
 inputs.finish()
 print(f'Flyer, QR and {len(targets)} handoff PDFs rendered')
if __name__=='__main__':main()

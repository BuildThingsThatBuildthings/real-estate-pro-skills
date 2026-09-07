#!/usr/bin/env python3
"""Render a source-led flyer plus readable branded Markdown handoff PDFs."""
import argparse,json,re
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
 p=argparse.ArgumentParser();p.add_argument('run');a=p.parse_args();r=Path(a.run);b=json.loads((r/'context/brand.json').read_text());facts=json.loads((r/'context/flyer.json').read_text())
 for weight in [400,700]:pdfmetrics.registerFont(TTFont('Brand'+str(weight),str(r/'working'/f'inter-{weight}.ttf')))
 out=r/facts['output_folder'];out.mkdir(exist_ok=True,parents=True);qr=qrcode.make(facts['url']);qr.save(out/'listing-qr.png')
 c=canvas.Canvas(str(out/(facts['id']+'.pdf')),pagesize=(612,792));c.setTitle(facts['address']+' | '+b['name']);c.setFillColor(HexColor(b['paper']));c.rect(0,0,612,792,fill=1,stroke=0);c.setFillColor(HexColor(b['red']));c.rect(0,782,612,10,fill=1,stroke=0)
 def txt(x,y,s,size=12,bold=False):c.setFillColor(HexColor(b['dark']));c.setFont('Brand700' if bold else 'Brand400',size);c.drawString(x,y,s)
 txt(36,747,b['name'].upper(),11,True);txt(36,714,facts['address'],25,True);txt(36,691,facts['location'],12)
 def photo(name,xy,size,focal=(.5,.5)):
  image=Image.open(r/'assets/photos'/name).convert('RGB');image=ImageOps.fit(image,(int(size[0]*2),int(size[1]*2)),Image.Resampling.LANCZOS,centering=focal)
  c.drawImage(ImageReader(image),*xy,width=size[0],height=size[1])
 photo(facts['hero'],(36,365),(540,306),tuple(facts.get('hero_focal',[.5,.2])))
 txt(36,342,facts['price'],26,True);txt(205,347,facts['summary'],13,True)
 photo(facts['detail_photos'][0],(36,205),(260,118));photo(facts['detail_photos'][1],(316,205),(260,118))
 txt(36,183,facts['hook'],15,True)
 for i,line in enumerate(facts['features']):txt(36,160-i*18,line,10)
 c.drawImage(ImageReader(out/'listing-qr.png'),472,105,width=100,height=100);txt(479,91,'Full listing',10,True)
 c.setStrokeColor(HexColor(b['red']));c.line(36,78,576,78);txt(36,58,b['agent']+', REALTOR®',12,True);txt(36,41,'C '+b['phone']+'  |  O '+b['officePhone'],10);txt(36,25,b['website']+'  ·  '+b.get('licenseLabel','License #')+b['license'],9)
 c.drawImage(ImageReader(r/'assets'/b['logo_source']),410,40,width=160,height=35,mask='auto',preserveAspectRatio=True);txt(416,25,b['brokerage'],9);c.save()
 styles=getSampleStyleSheet();styles.add(ParagraphStyle('BrandBody',fontName='Brand400',fontSize=10,leading=15,spaceAfter=9));styles.add(ParagraphStyle('BrandH1',fontName='Brand700',fontSize=23,leading=28,spaceBefore=16,spaceAfter=18,textColor=HexColor(b['dark'])));styles.add(ParagraphStyle('BrandH2',fontName='Brand700',fontSize=15,leading=20,spaceBefore=15,spaceAfter=10,textColor=HexColor(b['red'])))
 def footer(can,doc):
  can.setFont('Brand400',8);can.setFillColor(HexColor(b['dark']));can.drawString(40,25,b['name']+' · '+b['brokerage']);can.drawRightString(572,25,str(doc.page))
 targets=[r/path for path in json.loads((r/'context/documents.json').read_text())]
 for file in targets:
  flow=[]
  options_path=r/'context/document-options.json'
  options=json.loads(options_path.read_text()).get(str(file.relative_to(r)),{}) if options_path.exists() else {}
  for block in re.sub(r'(?m)^(#{1,3} )',r'\n\n\1',file.read_text()).split('\n\n'):
   if not block.strip():continue
   kind='BrandBody'
   if block.startswith('# '):kind='BrandH1';block=block[2:]
   elif block.startswith('## '):
    kind='BrandH2';block=block[3:]
    if options.get('one_page_per_numbered_section') and re.match(r'^\d+\.',block):flow.append(PageBreak())
   if block.startswith('|'):
    for line in block.splitlines():
     if not re.match(r'^\|[-| :]+\|$',line):flow.append(Paragraph(line.replace('|',' · '),styles['BrandBody']))
    continue
   block=block.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;');block=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',block);block=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'<link href="\2" color="#D71920">\1</link>',block);block=block.replace('\n','<br/>')
   flow.append(Paragraph(block,styles[kind]))
  SimpleDocTemplate(str(file.with_suffix('.pdf')),pagesize=(612,792),leftMargin=40,rightMargin=40,topMargin=35,bottomMargin=50).build(flow,onFirstPage=footer,onLaterPages=footer)
 print(f'Flyer, QR and {len(targets)} handoff PDFs rendered')
if __name__=='__main__':main()

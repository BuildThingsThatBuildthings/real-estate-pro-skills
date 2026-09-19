import sys,tempfile,hashlib,unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from qa_documents import check,private
class QA(unittest.TestCase):
 def test_private_image_contact_and_drift(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=r/'source.png';Image.new('RGB',(200,300),'red').save(p);s={'images':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]};a=check(s,r/'working/qa');self.assertEqual(a[0]['images'],1)
   with self.assertRaises(ValueError):private(r/'output/qa')
   p.write_bytes(b'changed')
   with self.assertRaises(ValueError):check(s,r/'working/qa2')
 def test_pdf_page_render(self):
  from reportlab.pdfgen.canvas import Canvas
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=r/'script.pdf';c=Canvas(str(p));c.drawString(50,700,'Actual recording script');c.save();s={'documents':[{'id':'script','path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]};a=check(s,r/'working/qa');self.assertEqual(a[0]['pages'],1);self.assertTrue(a[0]['nonempty_text']);self.assertFalse(a[0]['perceptual_review'])
 def test_embedded_pdf_qr_destination(self):
  import qrcode
  from reportlab.pdfgen.canvas import Canvas
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);png=r/'qr.png';url='https://example.com/listing';qrcode.make(url).save(png)
   pdf=r/'flyer.pdf';c=Canvas(str(pdf));c.drawImage(str(png),400,100,width=90,height=90);c.save()
   result=check({'qr':{'path':str(pdf),'destination':url}},r/'working/qr')
   self.assertEqual(result[0]['qr_destination'],url)
   with self.assertRaises(ValueError):check({'qr':{'path':str(pdf),'destination':'https://example.com/wrong'}},r/'working/wrong')
if __name__=='__main__':unittest.main()

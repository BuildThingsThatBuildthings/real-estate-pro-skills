"""Real fictional document render through the runner and public delivery gate."""
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parents[1]/'content-foundry/scripts'))
import run_workflow
from delivery_gate import validate_delivery

DEPS = all(importlib.util.find_spec(name) for name in ('qrcode','reportlab','pypdf'))
FONT = Path('/System/Library/Fonts/Supplemental/Arial.ttf')


@unittest.skipUnless(DEPS and FONT.exists(), 'Document runtime and local font required')
class DocumentDeliveryIntegration(unittest.TestCase):
    def test_useful_docs_render_and_deliver_with_private_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            for folder in ('context','working','assets/photos','output/Documents'):
                (root/folder).mkdir(parents=True,exist_ok=True)
            for weight in (400,700):shutil.copyfile(FONT,root/f'working/inter-{weight}.ttf')
            for name in ('front','kitchen','patio'):
                Image.new('RGB',(1200,800),'#244b50').save(root/f'assets/photos/{name}.png')
            Image.new('RGB',(400,100),'#ffffff').save(root/'assets/logo.png')
            brand={'name':'Harbor & Pine','paper':'#ffffff','red':'#24665a','dark':'#172e31','agent':'Test Agent','phone':'555-0100','officePhone':'555-0101','website':'example.com','license':'TEST','logo_source':'logo.png','brokerage':'Fictional Realty'}
            facts={'id':'listing-flyer','output_folder':'output/Documents','url':'https://example.com/listing','address':'100 Fictional Lane','location':'Fictional Harbor','hero':'front.png','detail_photos':['kitchen.png','patio.png'],'price':'$500,000','summary':'3 bedrooms','hook':'Room to unwind','features':['Private test fixture']}
            (root/'context/brand.json').write_text(json.dumps(brand))
            (root/'context/flyer.json').write_text(json.dumps(facts))
            (root/'context/documents.json').write_text(json.dumps(['output/Documents/Recording guide.md']))
            (root/'output/Documents/Recording guide.md').write_text('# Six room scripts\n\n\n### Start at the window\n\nA fictional recording guide for testing useful PDF delivery.\n')
            sources=[p for p in root.rglob('*') if p.is_file()]
            declared=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'origin':'original','source_id':f'fixture-{index}'} for index,p in enumerate(sources)]
            flow={'scope':'test','root':str(root),'run_id':'fictional-doc-run','tasks':[{'id':'documents','skill':'aia-listing-campaign','command':[sys.executable,str(SCRIPTS/'render_documents.py'),str(root)],'inputs':declared,'production_receipt':'working/document-production.json','outputs':['output/Documents/listing-flyer.pdf','output/Documents/listing-qr.png','output/Documents/Recording guide.pdf']}]}
            workflow=root/'workflow.json';workflow.write_text(json.dumps(flow))
            result=run_workflow.execute(workflow)
            task=result['tasks'][0]
            self.assertEqual(task['status'],'executed',(root/'working/workflow-logs/documents.log').read_text())
            self.assertEqual(task['freshness'],'verified')
            public=validate_delivery(root/'output',['Documents'],['Documents/listing-flyer.pdf','Documents/Recording guide.pdf','Documents/Recording guide.md'])
            self.assertEqual(len(public),4)
            from pypdf import PdfReader
            text=' '.join(page.extract_text() for page in PdfReader(root/'output/Documents/Recording guide.pdf').pages)
            self.assertIn('Start at the window',text)
            self.assertNotIn('###',text)
            self.assertTrue((root/'working/document-production.json').is_file())
            self.assertFalse(list((root/'output').rglob('*.json')))

if __name__=='__main__':unittest.main()

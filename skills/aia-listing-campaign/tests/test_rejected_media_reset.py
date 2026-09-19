import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('reset',Path(__file__).resolve().parents[1]/'scripts/reset_campaign.py');reset=importlib.util.module_from_spec(spec);spec.loader.exec_module(reset)
class RejectedMediaTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'run';(self.root/'working').mkdir(parents=True);(self.root/'source').mkdir();self.original=self.root/'source/photo.jpg';self.original.write_bytes(b'original')
  self.trash=self.base/'Trash/old';(self.trash/'delivery').mkdir(parents=True);self.video=self.trash/'delivery/rejected.mp4';self.video.write_bytes(b'rejected');self.pdf=self.trash/'delivery/approved.pdf';self.pdf.write_bytes(b'approved document')
  old={'complete':True,'preserved':[{'destination':str(self.original),'hashes':reset.tree_hashes(self.original)}],'removed':[{'trash_path':str(self.trash)}]};self.old=self.root/'working/old.json';self.old.write_text(json.dumps(old))
  self.plan={'authorization':'Delete exact rejected videos','permanent_delete_authorized':True,'run_root':str(self.root),'local_reset_receipt':str(self.old),'targets':[{'path':str(self.video),'sha256':reset.file_hash(self.video)}]}
 def tearDown(self):self.tmp.cleanup()
 def test_exact_media_removed_document_and_original_survive(self):
  result=reset.purge_rejected_exports(self.plan,self.root/'working/result.json');self.assertTrue(result['complete']);self.assertFalse(self.video.exists());self.assertTrue(self.pdf.exists());self.assertTrue(self.original.exists())
 def test_documents_refused(self):
  self.plan['targets']=[{'path':str(self.pdf),'sha256':reset.file_hash(self.pdf)}]
  with self.assertRaises(ValueError):reset.purge_rejected_exports(self.plan,self.root/'working/result.json')
  self.assertTrue(self.pdf.exists())
 def test_changed_preserved_original_blocks_deletion(self):
  self.original.write_bytes(b'changed')
  with self.assertRaises(ValueError):reset.purge_rejected_exports(self.plan,self.root/'working/result.json')
  self.assertTrue(self.video.exists())
if __name__=='__main__':unittest.main()

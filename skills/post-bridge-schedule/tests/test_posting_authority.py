"""OFFLINE ONLY: every transport and credential is mocked or a temporary fixture."""
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
CONFIG=SimpleNamespace(TOOLS={},NAME={99:'personal'},GBP=99,MIN_GAP=90,CTA={},RUNGS=[3,5,7,8],FORBIDDEN_HOURS=[],BLOCK_DAYS=30,VIEW_RELIABLE=[],MIN_RECORDS_PER_HOUR=3)
with patch.dict(sys.modules,{'config':CONFIG}):
    import pb
    import posting_authority as authority


class PostingAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.data={'content_owner':'client-a','credential':{'type':'env','name':'TEST_CLIENT_KEY'},'destination':{'owner':'client-a','kind':'client','credential_sha256':hashlib.sha256(b'fixture-key').hexdigest(),'account_ids':[11,12],'ownership_verified_by':'user','ownership_reference':'User supplied client workspace'},'authorization':{'source':'user','explicit':True,'reference':'User explicitly requested this client batch','scope':'client-posting','operations':['upload','draft','schedule','patch','delete']}}
        self.context=self.root/'posting.json';self.context.write_text(json.dumps(self.data))
        self.env=patch.dict(os.environ,{'AIA_POSTING_CONTEXT':str(self.context),'TEST_CLIENT_KEY':'fixture-key','POST_BRIDGE_API_KEY':'personal-fallback-must-never-write'})
        self.env.start()
        self.network=patch('urllib.request.urlopen',side_effect=AssertionError('LIVE NETWORK FORBIDDEN IN TESTS'));self.network.start()
    def tearDown(self):
        self.network.stop();self.env.stop();self.temp.cleanup()
    def save(self):self.context.write_text(json.dumps(self.data))
    def transport(self,path,method,body,key,base=pb.API):
        self.assertEqual(key,'fixture-key')
        if method=='GET' and path.startswith('/social-accounts'):
            return {'data':[{'id':11},{'id':12}],'meta':{}}
        if method=='GET' and path=='/posts/existing':return {'social_accounts':[11]}
        return {'id':'fixture-result'}
    def test_missing_context_blocks_before_any_network_or_global_credential(self):
        with patch.dict(os.environ,{'AIA_POSTING_CONTEXT':''}),patch.object(pb,'_request') as transport:
            with self.assertRaises(authority.PostingAuthorityError):pb.req('/posts','POST',{'is_draft':True,'social_accounts':[99]})
            transport.assert_not_called()
    def test_no_posting_authorization_blocks_upload_and_draft(self):
        self.data['authorization']['operations']=[];self.save()
        with patch.object(pb,'_request') as transport:
            for path,body in [('/posts',{'is_draft':True,'social_accounts':[11]}),('/media/create-upload-url',{})]:
                with self.assertRaises(authority.PostingAuthorityError):pb.req(path,'POST',body)
            transport.assert_not_called()
    def test_fingerprint_mismatch_never_falls_back(self):
        self.data['destination']['credential_sha256']='wrong';self.save()
        with patch.object(pb,'_request') as transport:
            with self.assertRaises(authority.PostingAuthorityError):pb.req('/posts','POST',{'is_draft':True,'social_accounts':[11]})
            transport.assert_not_called()
    def test_client_content_cannot_enter_personal_workspace(self):
        self.data['destination'].update(owner='ryan',kind='personal');self.save()
        with patch.object(pb,'_request') as transport:
            with self.assertRaisesRegex(authority.PostingAuthorityError,'another owner'):pb.req('/posts','POST',{'is_draft':True,'social_accounts':[11]})
            transport.assert_not_called()
    def test_explicit_personal_sample_is_narrow_exception(self):
        self.data['destination'].update(owner='ryan',kind='personal')
        self.data['authorization'].update(scope='personal-sample',sample_content_owner='client-a',sample_destination_owner='ryan')
        self.save()
        with patch.object(pb,'_request',side_effect=self.transport) as transport:
            self.assertEqual(pb.req('/posts','POST',{'is_draft':True,'social_accounts':[11]})['id'],'fixture-result')
            self.assertEqual([call.args[1] for call in transport.call_args_list],['GET','POST'])
    def test_roster_mismatch_blocks_all_writes(self):
        with patch.object(pb,'_request',return_value={'data':[{'id':99}],'meta':{}}) as transport:
            with self.assertRaisesRegex(authority.PostingAuthorityError,'roster differs'):pb.req('/posts','POST',{'scheduled_at':'future','social_accounts':[11]})
            self.assertTrue(all(call.args[1]=='GET' for call in transport.call_args_list))
    def test_verified_client_and_exact_requested_accounts(self):
        with patch.object(pb,'_request',side_effect=self.transport) as transport:
            pb.req('/posts','POST',{'scheduled_at':'future','social_accounts':[11,12]})
            self.assertEqual(transport.call_args_list[-1].args[1],'POST')
            with self.assertRaisesRegex(authority.PostingAuthorityError,'outside authorized'):pb.req('/posts','POST',{'is_draft':True,'social_accounts':[99]})
    def test_patch_checks_existing_post_before_writing(self):
        with patch.object(pb,'_request',side_effect=self.transport) as transport:
            pb.req('/posts/existing','PATCH',{'caption':'Updated'})
            self.assertEqual([call.args[1] for call in transport.call_args_list],['GET','GET','PATCH'])
        def wrongpost(path,method,body,key,base=pb.API):
            if path=='/posts/existing':return {'social_accounts':[99]}
            return self.transport(path,method,body,key,base)
        with patch.object(pb,'_request',side_effect=wrongpost) as transport:
            with self.assertRaises(authority.PostingAuthorityError):pb.req('/posts/existing','PATCH',{'caption':'bad'})
            self.assertTrue(all(call.args[1]=='GET' for call in transport.call_args_list))
    def test_read_only_audit_needs_no_posting_authorization(self):
        self.data['authorization']={};self.save()
        with patch.object(pb,'_request',side_effect=self.transport) as transport:
            pb.req('/posts/existing')
            self.assertEqual(len(transport.call_args_list),1)
            self.assertEqual(transport.call_args.args[1],'GET')
    def test_import_batch_is_offline_and_build_uses_only_scoped_accounts(self):
        with patch.dict(sys.modules,{'config':CONFIG}),patch('subprocess.run',side_effect=AssertionError('NO IMPORT-TIME COMMANDS')):
            batch=importlib.import_module('create_batch');importlib.reload(batch)
            self.assertIsNone(batch.ALLOWED_CT)
            engine=importlib.import_module('schedule_engine');importlib.reload(engine)
            self.assertEqual(engine.SLOTS,{})
            windows=importlib.import_module('windows');importlib.reload(windows)
            post={'captions':{'11':'One','12':'Two'},'video_media_id':'vid','gmb_media_id':'image','youtube_title':'Test','scheduled_at':'future'}
            self.assertEqual(batch.build(post)['social_accounts'],[11,12])
    def test_unsupported_write_path_refused(self):
        with patch.object(pb,'_request') as transport:
            with self.assertRaises(authority.PostingAuthorityError):pb.req('/anything','POST',{})
            transport.assert_not_called()

    def test_upload_without_authority_never_reserves_or_puts_bytes(self):
        media=self.root/'fixture.png';media.write_bytes(b'local fixture only')
        self.data['authorization']['operations']=[];self.save()
        with patch.object(pb,'_request') as transport:
            with self.assertRaises(authority.PostingAuthorityError):pb.upload(str(media))
            transport.assert_not_called()

if __name__=='__main__':unittest.main()

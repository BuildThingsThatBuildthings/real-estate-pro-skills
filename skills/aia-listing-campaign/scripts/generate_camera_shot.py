#!/usr/bin/env python3
"""Generate one source-image camera shot; inspect before chaining or batching.
Requires GEMINI_API_KEY. Private shot config owns all client facts and file paths.
"""
import argparse,base64,json,mimetypes,os,pathlib,urllib.request,urllib.error
p=argparse.ArgumentParser();p.add_argument('config');a=p.parse_args()
c=json.loads(pathlib.Path(a.config).read_text());image=pathlib.Path(c['image'])
if not c.get('rights_authorized'): raise SystemExit('Source-image rights authorization is required')
key=os.environ.get('GEMINI_API_KEY')
if not key: raise SystemExit('GEMINI_API_KEY is required')
body={'model':c['model'],'input':[{'type':'image','data':base64.b64encode(image.read_bytes()).decode(),'mime_type':mimetypes.guess_type(image)[0]},{'type':'text','text':c['prompt']}],'generation_config':{'video_config':{'task':'image_to_video'}},'response_format':{'type':'video','delivery':'uri','aspect_ratio':c.get('aspect_ratio','16:9')}}
out=pathlib.Path(c['output']);out.parent.mkdir(parents=True,exist_ok=True)
r=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/interactions',data=json.dumps(body).encode(),headers={'x-goog-api-key':key,'Content-Type':'application/json'})
try:
 with urllib.request.urlopen(r,timeout=240) as f: data=json.load(f)
except urllib.error.HTTPError as e:
 error={'status':'provider_rejected','http_status':e.code,'message':e.read().decode()[:1600]}
 out.with_suffix('.receipt.json').write_text(json.dumps(error,indent=2));print(json.dumps(error));raise SystemExit(2)
vids=[x for s in data.get('steps',[]) for x in s.get('content',[]) if x.get('type')=='video']
if not vids:
 out.with_suffix('.receipt.json').write_text(json.dumps({'status':'no_video','provider_status':data.get('status'),'interaction_id':data.get('id')},indent=2));raise SystemExit('Provider returned no finished video; inspect receipt before retrying')
v=vids[0]
if v.get('data'): raw=base64.b64decode(v['data'])
else:
 from urllib.parse import urlparse
 url=v['uri'];host=urlparse(url).hostname or ''
 if host!='generativelanguage.googleapis.com': raise SystemExit('Unexpected download host; inspect before sending credentials')
 with urllib.request.urlopen(urllib.request.Request(url,headers={'x-goog-api-key':key}),timeout=120) as f:raw=f.read()
out.write_bytes(raw)
out.with_suffix('.receipt.json').write_text(json.dumps({'status':'generated_unreviewed','model':c['model'],'interaction_id':data.get('id'),'source_image':str(image),'output_bytes':len(raw),'creative_review':'pending','fidelity_review':'pending'},indent=2));print(str(out))

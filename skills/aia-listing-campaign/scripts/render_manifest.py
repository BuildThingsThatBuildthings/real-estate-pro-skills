#!/usr/bin/env python3
"""Resume valid video exports; independent clean covers cannot invalidate a finished film."""
import argparse,json,subprocess
from pathlib import Path

def valid(path,seconds):
 if not path.exists():return False
 try:
  d=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)]))
  return abs(float(d['format']['duration'])-seconds)<.15
 except (subprocess.CalledProcessError,KeyError,ValueError):return False

def main():
 p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('engine');p.add_argument('--covers-only',action='store_true');a=p.parse_args();e=Path(a.engine).resolve()
 failures=[]
 for job in json.loads(Path(a.manifest).read_text()):
  out=Path(job['output']);out.parent.mkdir(parents=True,exist_ok=True);log=out.with_suffix('.render.log')
  with log.open('a') as f:
   if not a.covers_only and not valid(out,float(job['duration'])):
    temp=out.with_suffix('.partial.mp4')
    cmd=[str(e/'node_modules/.bin/remotion'),'render','src/index.ts','CampaignFilm',str(temp),'--props='+job['props'],'--codec=h264','--crf=19','--concurrency=2','--timeout=60000','--log=error']
    subprocess.run(cmd,cwd=e,stdout=f,stderr=subprocess.STDOUT,check=True)
    if not valid(temp,float(job['duration'])):raise RuntimeError('Incomplete video: '+job['id'])
    temp.replace(out)
   props=json.loads(Path(job['props']).read_text());props.update(captions=[],audio=None,music=None)
   coverprops=Path(job['props']).with_suffix('.cover-props.json');coverprops.write_text(json.dumps(props))
   try:subprocess.run([str(e/'node_modules/.bin/remotion'),'still','src/index.ts','CampaignFilm',str(out.with_suffix('.cover.png')),'--props='+str(coverprops),'--frame=40','--timeout=60000','--log=error'],cwd=e,stdout=f,stderr=subprocess.STDOUT,check=True)
   except subprocess.CalledProcessError:failures.append(job['id']);print('Cover retry needed: '+job['id'],flush=True)
  print('Rendered '+job['id'],flush=True)
 if failures:print('Pending covers: '+', '.join(failures))
if __name__=='__main__':main()

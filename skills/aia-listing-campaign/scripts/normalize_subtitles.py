#!/usr/bin/env python3
"""Remove overlapping SRT cue tails without changing text or cue start times."""
import argparse,json,re
from pathlib import Path

def normalize(path):
    def millis(t):
        h,m,s,ms=map(int,re.split('[:,]',t));return ((h*60+m)*60+s)*1000+ms
    def stamp(ms):
        h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000);return f'{h:02}:{m:02}:{s:02},{ms:03}'
    cues=[]
    for block in path.read_text().strip().split('\n\n'):
        lines=block.splitlines();start,end=map(millis,lines[1].split(' --> '));cues.append([start,end,lines[2:]])
    fixed=0
    for i,c in enumerate(cues[:-1]):
        if c[1]>cues[i+1][0]:
            if cues[i+1][0]<=c[0]:raise ValueError(f'Non-increasing cue starts in {path}')
            c[1]=cues[i+1][0];fixed+=1
    path.write_text('\n\n'.join(f'{i+1}\n{stamp(c[0])} --> {stamp(c[1])}\n'+ '\n'.join(c[2]) for i,c in enumerate(cues))+'\n')
    return fixed

def main():
    ap=argparse.ArgumentParser();ap.add_argument('manifest');a=ap.parse_args();result=[]
    for job in json.loads(Path(a.manifest).read_text()):
        path=Path(job['output']).with_suffix('.srt')
        if path.exists():result.append({'id':job['id'],'overlap_tails_trimmed':normalize(path)})
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

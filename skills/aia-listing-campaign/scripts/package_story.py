#!/usr/bin/env python3
"""Package a run's actual edit as an evidence-linked, independently framed storyboard."""
import argparse, csv, json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('run'); a=ap.parse_args(); root=Path(a.run)
    spec=json.loads((root/'context/story-package.json').read_text())
    out=(root/spec['output']).resolve()
    if not out.is_relative_to((root/'working').resolve()):raise ValueError('Story production records belong only in private working storage')
    out.mkdir(parents=True,exist_ok=True)
    (out/'Narrative treatment.md').write_text(spec['treatment'])
    (out/'Sound plan.md').write_text(spec['sound_plan'])
    boards=[]
    for composition in spec['compositions']:
        props=json.loads((root/composition['props']).read_text()); start=0; scenes=[]
        for i,scene in enumerate(props['scenes']):
            evidence=spec['scene_evidence'][i]
            scenes.append({**scene,'start_seconds':round(start/30,3),'end_seconds':round((start+scene['frames'])/30,3),**evidence})
            start+=scene['frames']
        boards.append({'id':composition['id'],'width':props['width'],'height':props['height'],'scenes':scenes})
    (out/'Evidence-linked script and storyboard.json').write_text(json.dumps(boards,indent=2))
    lines=['# Neighborhood story: actual edit and sources','', 'Timing follows the rendered narration. The vertical and horizontal compositions use separate frames.','']
    for board in boards:
        lines += ['## '+board['id'],'']
        for i,s in enumerate(board['scenes']):
            lines += [f"### {i+1}. {s['start_seconds']:.1f}–{s['end_seconds']:.1f}s · {s['label']}",'',s.get('voice',''),'', '**On screen:** '+s['headline'].replace('\n',' / '),'', '**Evidence:** '+', '.join(s['claim_ids'])+'. **Visual:** '+s['visual_intent'],'']
    (out/'Read the neighborhood film.md').write_text('\n'.join(lines))
    with (out/'Media acquisition.csv').open('w',newline='') as f:
        rows=spec['acquisition']; writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print('Story treatment, actual script, storyboard, acquisition list and sound plan packaged')

if __name__=='__main__':main()

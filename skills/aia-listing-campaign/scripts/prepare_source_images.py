#!/usr/bin/env python3
"""Convert authorized source photos to provider-compatible PNG without creative edits."""
import argparse, hashlib, json
from pathlib import Path
from PIL import Image, ImageOps
from production_inputs import Inputs

def prepare(spec,inputs=None):
    receipts=[]
    for item in spec['images']:
        if not item.get('rights_basis'): raise ValueError('Source authorization required')
        src=Path(item['source']); dst=Path(item['output'])
        if src.resolve()==dst.resolve(): raise ValueError('Never overwrite original media')
        if dst.exists():raise ValueError('Fresh source conversion cannot overwrite an existing result')
        if inputs:inputs.read(src)
        dst.parent.mkdir(parents=True,exist_ok=True)
        image=ImageOps.exif_transpose(Image.open(src)).convert('RGB')
        image.save(dst,format='PNG')
        receipts.append({**item,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
                         'output_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),
                         'size':list(image.size),'transformation':'format and EXIF orientation only; no creative alteration'})
    return receipts

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('spec');p.add_argument('--receipt',required=True);a=p.parse_args()
    inputs=Inputs();spec=json.loads(inputs.read(a.spec))
    receipt=Path(a.receipt);receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps(prepare(spec,inputs),indent=2)+'\n');inputs.finish()

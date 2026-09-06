#!/usr/bin/env python3
"""Download explicitly inventoried, permitted assets; retain source URLs and hashes."""
import argparse, concurrent.futures, hashlib, json, urllib.request
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('destination');a=p.parse_args()
    items=json.loads(Path(a.manifest).read_text());out=Path(a.destination);out.mkdir(parents=True,exist_ok=True)
    def fetch(m):
        if m.get('rights') not in ('authorized','licensed','original') or not m.get('rights_basis'): raise ValueError('Rights missing: '+m['id'])
        dest=out/m['filename']
        if not dest.exists():
            with urllib.request.urlopen(m['url'],timeout=45) as response: data=response.read()
            dest.write_bytes(data)
        data=dest.read_bytes();m.update(path=str(dest),bytes=len(data),sha256=hashlib.sha256(data).hexdigest());return m
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool: results=list(pool.map(fetch,items))
    (out/'inventory.json').write_text(json.dumps(results,indent=2));print(f'Acquired {len(results)} source assets')
if __name__=='__main__':main()

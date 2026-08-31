#!/usr/bin/env python3
"""
Outbox lifecycle for finished content.

    awaiting-approval/   everything produced but not yet cleared by a human
    approved/            the human moved it here: that IS the trigger to schedule
    posted/              scheduling verified complete, all gates passed
    failed/              a gate failed; goes back to a human

  outbox_flow.py status                     classify every project against Post Bridge
  outbox_flow.py organize [--yes]           one-time reorg: fully-scheduled -> posted,
                                            unscheduled strays -> awaiting-approval
  outbox_flow.py pending                    list projects sitting in approved/ (the queue)
  outbox_flow.py promote <project> --ids id1,id2 [--yes]
                                            verify every record id (status scheduled/posted,
                                            >=9 destinations, distinct captions), write a
                                            receipt, then move approved/<p> -> posted/<p>

promote is the ONLY path into posted/. It refuses if any record fails verification.
The outbox root comes from pipeline.json tools.outbox_root.
"""
import json,os,sys,shutil,argparse,socket,urllib.request
from datetime import datetime,timezone
socket.setdefaulttimeout(30)
_HERE=os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0,_HERE)
import config as _cfg
import pb

OUTBOX=os.path.expanduser(_cfg.TOOLS.get("outbox_root","~/video-builds/outbox"))
STAGES=("awaiting-approval","approved","posted","failed","scheduled")
VIDEO=(".mp4",".mov",".m4v",".webm")

def projects(stage):
    d=os.path.join(OUTBOX,stage)
    if not os.path.isdir(d): return []
    return sorted(p for p in os.listdir(d) if os.path.isdir(os.path.join(d,p)))

def vids(path):
    out=[]
    for dp,_,fs in os.walk(path):
        for f in fs:
            if f.lower().endswith(VIDEO) and not f.startswith("."):
                out.append(os.path.join(dp,f))
    return out

def pb_sizes():
    return {(m.get("object") or {}).get("size_bytes") for m in pb.paged("/media")}

def classify():
    sizes=pb_sizes()
    rows=[]
    for stage in STAGES:
        for p in projects(stage):
            path=os.path.join(OUTBOX,stage,p)
            vv=vids(path)
            inpb=sum(1 for v in vv if os.path.getsize(v) in sizes)
            if not vv: verdict="no-video"
            elif inpb==len(vv): verdict="all-in-pb"
            elif inpb==0: verdict="none-in-pb"
            else: verdict=f"partial {inpb}/{len(vv)}"
            rows.append((stage,p,len(vv),inpb,verdict))
    return rows

def cmd_status(a):
    print(f"outbox: {OUTBOX}\n")
    print(f"{'STAGE':<19}{'PROJECT':<42}{'vids':>5}{'in-pb':>6}  VERDICT")
    for stage,p,n,i,v in classify():
        print(f"{stage:<19}{p:<42}{n:>5}{i:>6}  {v}")

def cmd_organize(a):
    rows=classify()
    moves=[]
    for stage,p,n,i,v in rows:
        src=os.path.join(OUTBOX,stage,p)
        if stage=="scheduled" and v in ("all-in-pb",):
            moves.append((src,os.path.join(OUTBOX,"posted",p),"scheduled+verified in PB"))
        elif stage=="awaiting-approval" and v=="all-in-pb":
            moves.append((src,os.path.join(OUTBOX,"posted",p),"already fully in PB"))
        elif stage=="scheduled" and v.startswith("partial"):
            print(f"HOLD scheduled/{p}: {v} — inspect before moving")
    if not moves:
        print("nothing to move"); return
    for src,dst,why in moves:
        print(f"{'MOVE' if a.yes else 'would move'} {os.path.relpath(src,OUTBOX)} -> {os.path.relpath(dst,OUTBOX)}   ({why})")
        if a.yes:
            if os.path.exists(dst):
                # merge: move children, keep both histories
                for item in os.listdir(src):
                    s2,d2=os.path.join(src,item),os.path.join(dst,item)
                    if not os.path.exists(d2): shutil.move(s2,d2)
                try: os.rmdir(src)
                except OSError: print(f"  note: {src} not empty after merge, left in place")
            else:
                shutil.move(src,dst)
    if not a.yes: print("\nre-run with --yes to apply")

def cmd_pending(a):
    q=projects("approved")
    if not q: print("approved/ is empty — nothing queued"); return
    print("QUEUED FOR SCHEDULING (run the skill on each, then promote):")
    for p in q:
        marker=os.path.join(OUTBOX,"approved",p,"INGESTED")
        note="  [stale INGESTED marker present]" if os.path.exists(marker) else ""
        print(f"  {p}  ({len(vids(os.path.join(OUTBOX,'approved',p)))} videos){note}")

def cmd_promote(a):
    # Prefer whichever stage directory actually holds the content. A husk
    # (marker files only) can shadow the real folder and get promoted in its
    # place, which strands the content. Learned the hard way.
    cands=[os.path.join(OUTBOX,st,a.project) for st in ("approved","awaiting-approval")]
    cands=[c for c in cands if os.path.isdir(c)]
    if not cands: raise SystemExit(f"not found in approved/ or awaiting-approval/: {a.project}")
    src=max(cands,key=lambda c:len(vids(c)))
    if len(vids(src))==0 and len(cands)>1:
        raise SystemExit(f"both candidates are content-free husks: {cands}")
    ids=[x.strip() for x in a.ids.split(",") if x.strip()]
    if not ids: raise SystemExit("--ids required: the record ids the skill created")
    results=[]; ok=True
    for pid in ids:
        try:
            q=pb.req(f"/posts/{pid}")
        except Exception as e:
            results.append((pid,"UNREADABLE",str(e)[:40])); ok=False; continue
        accs=q.get("social_accounts") or []
        ac=[c.get("caption") or "" for c in (q.get("account_configurations") or {}).get("account_configurations",[])]
        problems=[]
        if q.get("status") not in ("scheduled","posted","processing"): problems.append(f"status={q.get('status')}")
        if len(set(accs))<9: problems.append(f"dests={len(set(accs))}")
        if len(set(x.strip() for x in ac))<len(ac): problems.append("duplicate captions")
        if problems: ok=False
        results.append((pid,q.get("status"),"; ".join(problems) or "verified"))
    for pid,st,note in results:
        print(f"  {pid[:8]}  {st:<10} {note}")
    if not ok:
        print("\nPROMOTE REFUSED: fix the records above first"); sys.exit(1)
    receipt=dict(project=a.project,promoted_at=datetime.now(timezone.utc).isoformat(),
                 record_ids=ids,verification=[dict(id=i,status=s,note=n) for i,s,n in results])
    dst=os.path.join(OUTBOX,"posted",a.project)
    if not a.yes:
        print(f"\nall {len(ids)} records verified. re-run with --yes to move {os.path.relpath(src,OUTBOX)} -> posted/")
        return
    os.makedirs(os.path.dirname(dst),exist_ok=True)
    if os.path.exists(dst):
        for item in os.listdir(src):
            d2=os.path.join(dst,item)
            if not os.path.exists(d2): shutil.move(os.path.join(src,item),d2)
        try: os.rmdir(src)
        except OSError: pass
    else:
        shutil.move(src,dst)
    json.dump(receipt,open(os.path.join(dst,"SCHEDULE-RECEIPT.json"),"w"),indent=1)
    print(f"\npromoted {a.project} -> posted/  (receipt written)")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd",required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    o=sub.add_parser("organize"); o.add_argument("--yes",action="store_true"); o.set_defaults(fn=cmd_organize)
    sub.add_parser("pending").set_defaults(fn=cmd_pending)
    pr=sub.add_parser("promote"); pr.add_argument("project"); pr.add_argument("--ids",required=True)
    pr.add_argument("--yes",action="store_true"); pr.set_defaults(fn=cmd_promote)
    a=ap.parse_args(); a.fn(a)

#!/usr/bin/env python3
"""
Create Post Bridge records from a batch JSON, enforcing the preflight lint.

  create_batch.py lint   batch.json      run all 9 checks, write nothing
  create_batch.py create batch.json      lint, then create (only if lint passes)

batch.json:
{
  "posts": [
    {
      "slug": "automations-01-...",
      "scheduled_at": "2026-08-29T20:00:00Z",
      "video_media_id": "...",
      "gmb_media_id": "...",
      "youtube_title": "...",
      "twitter_first_comment": "<optional link>",
      "gbp_cta_url": "<optional, defaults to brand.json cta.url>",
      "captions": { "<account_id>": "...", "...": "one entry per configured channel" }
    }
  ]
}
"""
import json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from collections import defaultdict

API = "https://api.post-bridge.com/v1"
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.realpath(__file__)))
import config as _cfg
CHANNELS = dict(_cfg.NAME)
GBP = _cfg.GBP
MIN_GAP_MIN = _cfg.MIN_GAP
def _allowed_ct():
    """Allowed slots come from the SAME derived ladder the planner uses.
    Hardcoding here lets lint and planner disagree, which rejects valid slots."""
    try:
        import subprocess
        out = subprocess.run(
            ["python3", os.path.join(os.path.dirname(os.path.abspath(__file__)), "windows.py"),
             "ladder", "--json"], capture_output=True, text=True, timeout=120)
        return set(json.loads(out.stdout)["8"])
    except Exception:
        return {"11:15", "15:15", "18:15", "20:15", "12:15", "13:20", "10:15", "09:15"}


ALLOWED_CT = _allowed_ct()


def key():
    return json.load(open(os.path.expanduser("~/.config/post-bridge/config.json")))["apiKey"]


def api(path, method="GET", body=None):
    req = urllib.request.Request(
        f"{API}{path}", method=method,
        headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body else None)
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def live_times():
    """channel -> [datetime UTC] for every scheduled post."""
    per, off = defaultdict(list), 0
    while True:
        page = api(f"/posts?status=scheduled&limit=100&offset={off}")
        for p in page["data"]:
            if p.get("is_draft") or not p.get("scheduled_at"):
                continue
            t = datetime.fromisoformat(p["scheduled_at"].replace("Z", "+00:00"))
            for a in set(p["social_accounts"]):
                if a in CHANNELS:
                    per[a].append(t)
        if not page["meta"].get("next"):
            break
        off += 100
    return per


def ct_hhmm(utc_iso):
    t = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    off = -5 if 3 <= t.month <= 11 else -6
    return (t + timedelta(hours=off)).strftime("%H:%M")


def lint(batch, per_ch):
    errs = []
    pending = defaultdict(list)
    for p in batch["posts"]:
        s = p["slug"]
        caps = {int(k): v for k, v in p["captions"].items()}

        # 1 nine destinations
        if set(caps) != set(CHANNELS):
            errs.append(f"{s}: destinations != 9 (missing {set(CHANNELS)-set(caps)})")
        # 2 no duplicate account ids  (dict keys are unique; guard the raw list)
        raw = list(p["captions"].keys())
        if len(raw) != len(set(raw)):
            errs.append(f"{s}: duplicate account_id in captions")
        # 3 nine distinct captions
        vals = [v.strip() for v in caps.values()]
        if len(set(vals)) != len(vals):
            errs.append(f"{s}: captions not all distinct ({len(vals)-len(set(vals))} dupes)")
        if any(not v for v in vals):
            errs.append(f"{s}: empty caption present")
        # 4 youtube title
        yt = p.get("youtube_title", "")
        if not yt or len(yt) > 100:
            errs.append(f"{s}: youtube_title missing or >100 chars ({len(yt)})")
        # 5 gbp uses an image
        if not p.get("gmb_media_id"):
            errs.append(f"{s}: gmb_media_id missing (GBP cannot take video)")
        # 6 slot allowed
        hhmm = ct_hhmm(p["scheduled_at"])
        if hhmm not in ALLOWED_CT:
            errs.append(f"{s}: slot {hhmm} CT not in allowed set")
        # 7 same-channel spacing vs live + pending
        t = datetime.fromisoformat(p["scheduled_at"].replace("Z", "+00:00"))
        for a in CHANNELS:
            for other in per_ch[a] + pending[a]:
                if abs((t - other).total_seconds()) / 60 < MIN_GAP_MIN:
                    errs.append(f"{s}: {CHANNELS[a]} within {MIN_GAP_MIN}min of {other:%Y-%m-%d %H:%M}Z")
                    break
        for a in CHANNELS:
            pending[a].append(t)
        # 8 media ids resolve
        for mid_key in ("video_media_id", "gmb_media_id"):
            mid = p.get(mid_key)
            if mid:
                try:
                    m = api(f"/media/{mid}")
                    # The media RECORD existing is not enough. Post Bridge purges the
                    # underlying FILE once any post using it publishes, leaving the id
                    # resolvable and the storage 404. A record scheduled against purged
                    # media publishes to nothing, silently. Check the signed URL.
                    url = (m.get("object") or {}).get("url")
                    if not url:
                        errs.append(f"{s}: {mid_key} {mid} has no signed url (file purged?)")
                    else:
                        import subprocess as _sp
                        code = _sp.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                                        "-r", "0-100", url], capture_output=True,
                                       text=True, timeout=25).stdout
                        if code not in ("200", "206"):
                            errs.append(f"{s}: {mid_key} {mid} storage returns {code} — "
                                        f"file purged, re-upload from source")
                except urllib.error.HTTPError as e:
                    errs.append(f"{s}: {mid_key} {mid} does not resolve ({e.code})")
    return errs



def check_do_not_schedule(batch):
    """Refuse to schedule media from a project flagged do_not_schedule.

    Production projects carry a job.json next to the render tree. A True flag
    means a human has not cleared that project for scheduling yet. Scheduling
    held content is worse than scheduling nothing.
    """
    import glob as _glob
    blocked = []
    for post in batch.get("posts", []):
        src = post.get("source_path") or post.get("slug", "")
        d = os.path.dirname(os.path.abspath(src)) if os.path.sep in str(src) else None
        while d and d != os.path.sep:
            j = os.path.join(d, "job.json")
            if os.path.isfile(j):
                try:
                    if json.load(open(j)).get("do_not_schedule") is True:
                        blocked.append((post.get("slug"), j))
                except Exception:
                    pass
                break
            d = os.path.dirname(d)
    return blocked

def build(p):
    caps = {int(k): v for k, v in p["captions"].items()}
    cfg = [{"account_id": a,
            "caption": caps[a],
            "media": [p["gmb_media_id"] if a == GBP else p["video_media_id"]]}
           for a in CHANNELS]
    pc = {
        "youtube": {"title": p["youtube_title"]},
        "google_business": {"cta_action_type": _cfg.CTA.get("action_type", "LEARN_MORE"),
                            "cta_url": p.get("gbp_cta_url") or _cfg.CTA.get("url", ""),
                            "media": [p["gmb_media_id"]]},
    }
    if p.get("twitter_first_comment"):
        pc["twitter"] = {"first_comment": p["twitter_first_comment"]}
    # Cover frame for the vertical video surfaces. cover_image needs a separate
    # uploaded asset; video_cover_timestamp_ms needs none, so it is the default.
    cover_ms = p.get("cover_timestamp_ms", 1500)
    if p.get("instagram_cover_media_id"):
        pc["instagram"] = {"cover_image": p["instagram_cover_media_id"]}
    else:
        pc["instagram"] = {"video_cover_timestamp_ms": cover_ms}
    pc["tiktok"] = {"video_cover_timestamp_ms": cover_ms}
    return {
        # top level caption is only a fallback; every channel has its own.
        "caption": caps[next(iter(CHANNELS))],
        "social_accounts": list(CHANNELS),
        "account_configurations": {"account_configurations": cfg},
        "platform_configurations": pc,
        "scheduled_at": p["scheduled_at"],
    }


if __name__ == "__main__":
    mode, path = sys.argv[1], sys.argv[2]
    batch = json.load(open(path))
    per_ch = live_times()
    held = check_do_not_schedule(batch)
    errs = [f"{slug}: project flagged do_not_schedule in {j}" for slug, j in held]
    errs += lint(batch, per_ch)
    if errs:
        print(f"LINT FAILED ({len(errs)} error(s)):")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    print(f"LINT PASSED: {len(batch['posts'])} posts, 9 destinations each, "
          f"{len(batch['posts'])*9} content units")
    if mode == "lint":
        sys.exit(0)
    created = []
    for p in batch["posts"]:
        r = api("/posts", "POST", build(p))
        pid = r.get("id")
        created.append((pid, p))
        print(f"created {pid}  {p['slug']}  {p['scheduled_at']}")

    # ---- POST-CREATE VERIFICATION ----
    # This API returns a created id without reliably persisting
    # social_accounts. Re-read every record and repair empties. Observed
    # rate on a 25 post batch: 4 records silently created with 0 destinations.
    print("\nverifying...")
    import time as _t
    bad = []
    for pid, p in created:
        try:
            q = api(f"/posts/{pid}")
        except Exception as e:
            print(f"  {pid[:8]} {p['slug']}: READ FAILED {e}")
            bad.append((pid, p)); continue
        if len(q["social_accounts"]) != 9 or len(set(q["social_accounts"])) != 9:
            print(f"  {pid[:8]} {p['slug']}: dest={len(q['social_accounts'])} REPAIRING")
            bad.append((pid, p))
    for pid, p in list(bad):
        payload = build(p)
        fixed = False
        for attempt in range(1, 6):
            try:
                api(f"/posts/{pid}", "PATCH",
                    {"social_accounts": payload["social_accounts"],
                     "account_configurations": payload["account_configurations"]})
            except urllib.error.HTTPError:
                pass
            _t.sleep(2)
            q = api(f"/posts/{pid}")
            if len(q["social_accounts"]) == 9 == len(set(q["social_accounts"])):
                print(f"  {pid[:8]} repaired on attempt {attempt}")
                bad.remove((pid, p)); fixed = True; break
        if not fixed:
            print(f"  {pid[:8]} {p['slug']}: STILL BROKEN, delete and recreate manually")
    ok = len(created) - len(bad)
    print(f"\nVERIFIED {ok}/{len(created)} records with 9 unique destinations")
    if bad:
        sys.exit(2)

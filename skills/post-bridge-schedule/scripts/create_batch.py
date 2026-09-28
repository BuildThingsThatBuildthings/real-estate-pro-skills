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

THE ONLY WAY AIA/BT2 POSTS ARE CREATED (Ryan, 2026-09-27). Callers: the social
agent and the video agent. A global PreToolUse hook blocks direct connector
create_post for AIA/BT2; every other scheduler is retired.

AIA/BT2 roster law (check 1): whenever a post or the verified posting context
touches an AIA/BT2 account, the post must target ALL nine roster accounts
(AIA_BT2_ROSTER) with a non-empty caption per account, all nine captions
pairwise distinct, and a YouTube title. The only exception is a LinkedIn-only
post (accounts drawn only from LINKEDIN_ONLY), which needs a non-empty,
distinct caption per LinkedIn account and nothing else.
"""
import json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo

API = "https://api.post-bridge.com/v1"
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.realpath(__file__)))
import config as _cfg
import pb
import posting_authority
CHANNELS = {}  # populated only from explicit destination context

# AIA/BT2 nine-account roster (ops/social-engine/ACCOUNT-REGISTRY.md). Hardcoded on
# purpose: a posting context that drops an account must fail the lint, not shrink it.
AIA_BT2_ROSTER = frozenset({72366, 72367, 72370, 75843, 75846, 75850, 75841, 75844, 75848})
# li/AIA and li/RyanWanner: the only accounts a post may target on its own.
LINKEDIN_ONLY = frozenset({72370, 80927})
AIA_BT2_SCOPE = AIA_BT2_ROSTER | LINKEDIN_ONLY


def _norm_caption(value):
    """Caption text for the distinctness test: whitespace collapsed, case folded."""
    return " ".join(value.split()).casefold() if isinstance(value, str) else ""


def is_linkedin_only(caps):
    return bool(caps) and set(caps) <= LINKEDIN_ONLY


def roster_errors(slug, caps, channels, youtube_title):
    """AIA/BT2 roster law. Returns [] for posts outside AIA/BT2 scope.

    caps: {int account_id: caption}. channels: the verified posting context ids.
    """
    if not (set(caps) & AIA_BT2_SCOPE or set(channels) & AIA_BT2_SCOPE):
        return []
    errs = []
    if is_linkedin_only(caps):
        outside = set(caps) - set(channels)
        if outside:
            errs.append(f"{slug}: LinkedIn-only post targets {sorted(outside)} outside the verified posting context")
        return errs
    missing = AIA_BT2_ROSTER - set(caps)
    extra = set(caps) - AIA_BT2_ROSTER
    if missing:
        errs.append(f"{slug}: AIA/BT2 post must target all 9 roster accounts (missing {sorted(missing)})")
    if extra:
        errs.append(f"{slug}: AIA/BT2 post targets non-roster accounts {sorted(extra)}; "
                    f"only a LinkedIn-only post ({sorted(LINKEDIN_ONLY)}) may leave the roster")
    unverified = AIA_BT2_ROSTER - set(channels)
    if unverified:
        errs.append(f"{slug}: verified posting context is missing roster accounts {sorted(unverified)}")
    empty = sorted(a for a in AIA_BT2_ROSTER & set(caps) if not _norm_caption(caps[a]))
    if empty:
        errs.append(f"{slug}: empty caption for roster accounts {empty}")
    seen = {}
    for a in sorted(AIA_BT2_ROSTER & set(caps)):
        n = _norm_caption(caps[a])
        if n and n in seen:
            errs.append(f"{slug}: caption for {a} duplicates {seen[n]}; all 9 captions must be distinct")
        seen.setdefault(n, a)
    if not isinstance(youtube_title, str) or not youtube_title.strip():
        errs.append(f"{slug}: AIA/BT2 post needs a YouTube title")
    return errs
GBP = _cfg.GBP
MIN_GAP_MIN = _cfg.MIN_GAP          # between posts on the SAME account
MIN_STAGGER_MIN = int(getattr(_cfg, "MIN_GLOBAL_STAGGER", 10))  # across different accounts
def _allowed_ct(preferred_slots=()):
    """Every daypart ladder slot, plus explicit batch timing preferences.
    Rungs are count targets, not whitelists. Never substitute guessed slots
    when analytics loading fails.
    """
    import windows
    # The daypart ladder's full candidate set (schedule_engine.LADDER / repair use the same).
    allowed = {s for s in windows.ladder_order(windows.rows()) if windows.in_window(s)}
    for slot in preferred_slots:
        parsed = datetime.strptime(slot, "%H:%M")
        if (parsed.strftime("%H:%M") != slot or parsed.hour in _cfg.FORBIDDEN_HOURS
                or not windows.in_window(slot)):
            raise ValueError("Invalid or forbidden preferred slot: " + slot)
        allowed.add(slot)
    return allowed


ALLOWED_CT = None  # import is offline; derive only during an explicit lint/create run


def key():
    return pb.api_key()


def api(path, method="GET", body=None):
    return pb.req(path, method, body)


def scoped_channels():
    data = posting_authority.context(required=True)
    ids = data.get('destination', {}).get('account_ids', [])
    if not ids:
        raise posting_authority.PostingAuthorityError('Verified client account roster required')
    return {int(value): _cfg.NAME.get(int(value), str(value)) for value in ids}


def live_times():
    """channel -> [datetime UTC] for every scheduled post."""
    global CHANNELS
    CHANNELS = scoped_channels()
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
    if t.tzinfo is None:
        raise ValueError("scheduled_at must include a UTC offset")
    return t.astimezone(ZoneInfo("America/Chicago")).strftime("%H:%M")


def lint(batch, per_ch):
    global ALLOWED_CT, CHANNELS
    CHANNELS = scoped_channels()
    ALLOWED_CT = _allowed_ct(batch.get("preferred_slots", ()))
    errs = []
    pending = defaultdict(list)
    for p in batch["posts"]:
        s = p["slug"]
        caps = {int(k): v for k, v in (p.get("captions") or {}).items()}
        li_only = is_linkedin_only(caps)

        # 1 destinations: AIA/BT2 roster law (all 9, or LinkedIn-only), else the verified roster
        if set(caps) & AIA_BT2_SCOPE or set(CHANNELS) & AIA_BT2_SCOPE:
            errs.extend(roster_errors(s, caps, CHANNELS, p.get("youtube_title")))
        elif set(caps) != set(CHANNELS):
            errs.append(f"{s}: destinations differ from verified client roster (missing {set(CHANNELS)-set(caps)})")
        # 2 no duplicate account ids  (dict keys are unique; guard the raw list)
        raw = [str(k).strip() for k in (p.get("captions") or {}).keys()]
        if len(raw) != len(set(raw)):
            errs.append(f"{s}: duplicate account_id in captions")
        # 3 distinct, non-empty captions
        vals = [_norm_caption(v) for v in caps.values()]
        if len(set(vals)) != len(vals):
            errs.append(f"{s}: captions not all distinct ({len(vals)-len(set(vals))} dupes)")
        if any(not v for v in vals):
            errs.append(f"{s}: empty caption present")
        # 4 youtube title (a LinkedIn-only post has no YouTube destination)
        yt = p.get("youtube_title") or ""
        if not li_only and (not yt.strip() or len(yt) > 100):
            errs.append(f"{s}: youtube_title missing or >100 chars ({len(yt)})")
        # 5 gbp uses an image
        if not li_only and not p.get("gmb_media_id"):
            errs.append(f"{s}: gmb_media_id missing (GBP cannot take video)")
        # 6 slot allowed
        hhmm = ct_hhmm(p["scheduled_at"])
        import windows as _w
        if not _w.in_window(hhmm):
            errs.append(f"{s}: slot {hhmm} CT outside the posting window "
                        f"{_w.EARLIEST_START}-{_w.LATEST_START} CT (last start {_w.LATEST_START})")
        elif hhmm not in ALLOWED_CT:
            errs.append(f"{s}: slot {hhmm} CT not in allowed set")
        # 7 spacing vs live + pending: MIN_GAP_MIN on the accounts this post
        #   targets, MIN_STAGGER_MIN against every other post on any account
        t = datetime.fromisoformat(p["scheduled_at"].replace("Z", "+00:00"))
        targets = set(caps) or set(CHANNELS)
        for a in sorted(targets):
            for other in per_ch.get(a, []) + pending[a]:
                if abs((t - other).total_seconds()) / 60 < MIN_GAP_MIN:
                    errs.append(f"{s}: {CHANNELS.get(a, a)} within {MIN_GAP_MIN}min of {other:%Y-%m-%d %H:%M}Z")
                    break
        for other in sorted({x for ev in list(per_ch.values()) + list(pending.values()) for x in ev}):
            if abs((t - other).total_seconds()) / 60 < MIN_STAGGER_MIN:
                errs.append(f"{s}: within the {MIN_STAGGER_MIN}min cross-account stagger of "
                            f"{other:%Y-%m-%d %H:%M}Z")
                break
        for a in targets:
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
    global CHANNELS
    CHANNELS = scoped_channels()
    caps = {int(k): v for k, v in p["captions"].items()}
    if is_linkedin_only(caps):
        targets = [a for a in CHANNELS if a in caps]
        media = [m for m in (p.get("video_media_id") or p.get("image_media_id"),) if m]
        return {
            "caption": caps[targets[0]],
            "social_accounts": targets,
            "account_configurations": {"account_configurations": [
                {"account_id": a, "caption": caps[a], "media": media} for a in targets]},
            "scheduled_at": p["scheduled_at"],
        }
    targets = [a for a in CHANNELS if a in caps]
    cfg = [{"account_id": a,
            "caption": caps[a],
            "media": [p["gmb_media_id"] if a == GBP else p["video_media_id"]]}
           for a in targets]
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
        "caption": caps[targets[0]],
        "social_accounts": targets,
        "account_configurations": {"account_configurations": cfg},
        "platform_configurations": pc,
        "scheduled_at": p["scheduled_at"],
    }


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("lint", "create"):
        sys.exit("usage: create_batch.py lint|create batch.json")
    mode, path = sys.argv[1], sys.argv[2]
    CHANNELS = scoped_channels()
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
    units = sum(len(p.get("captions") or {}) for p in batch["posts"])
    print(f"LINT PASSED: {len(batch['posts'])} posts, {units} content units")
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
        want = len(build(p)["social_accounts"])
        if len(q["social_accounts"]) != want or len(set(q["social_accounts"])) != want:
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
            if len(q["social_accounts"]) == len(payload["social_accounts"]) == len(set(q["social_accounts"])):
                print(f"  {pid[:8]} repaired on attempt {attempt}")
                bad.remove((pid, p)); fixed = True; break
        if not fixed:
            print(f"  {pid[:8]} {p['slug']}: STILL BROKEN, delete and recreate manually")
    ok = len(created) - len(bad)
    print(f"\nVERIFIED {ok}/{len(created)} records with every targeted destination unique")
    if bad:
        sys.exit(2)

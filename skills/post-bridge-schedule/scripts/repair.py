#!/usr/bin/env python3
"""
Repair structural defects in the live Post Bridge calendar.

  repair.py scan                    report defects, change nothing
  repair.py fix --dedupe            collapse duplicate destinations in a record
  repair.py fix --collisions        reschedule to clear the 90-minute same-channel rule
  repair.py fix --all               both

Every write is verified by re-reading the record, and retried up to 4 times.
The Post Bridge write path returns success without persisting often enough
that a blind PATCH cannot be trusted.
"""
import json, os, sys, time, argparse, urllib.request, urllib.error
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone

API = "https://api.post-bridge.com/v1"
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.realpath(__file__)))
import config as _cfg
NAME = dict(_cfg.NAME)
MIN_GAP = _cfg.MIN_GAP
LADDER = ["11:15", "13:20", "15:00", "20:30", "12:00", "18:00", "10:00", "09:15"]


def ct(d):
    return timezone(timedelta(hours=-5 if 3 <= d.month <= 11 else -6))


def api(path, method="GET", body=None):
    k = json.load(open(os.path.expanduser("~/.config/post-bridge/config.json")))["apiKey"]
    r = urllib.request.Request(f"{API}{path}", method=method,
        headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body else None)
    with urllib.request.urlopen(r) as resp:
        return json.load(resp)


def live():
    out, off = [], 0
    while True:
        pg = api(f"/posts?status=scheduled&limit=100&offset={off}")
        out += pg["data"]
        if not pg["meta"].get("next"):
            break
        off += 100
    return [p for p in out if not p.get("is_draft") and p.get("scheduled_at")]


def when(p):
    t = datetime.fromisoformat(p["scheduled_at"].replace("Z", "+00:00"))
    return t.astimezone(ct(t))


def occupancy(posts, exclude=None):
    ev = defaultdict(list)
    for p in posts:
        if exclude and p["id"] == exclude:
            continue
        t = when(p)
        for a in set(p["social_accounts"]):
            if a in NAME:
                ev[a].append(t)
    return ev


def find_defects(posts):
    dupes = [p for p in posts if len(p["social_accounts"]) != len(set(p["social_accounts"]))]
    empties = [p for p in posts if len(p["social_accounts"]) == 0]
    byid = {p["id"]: p for p in posts}
    ev = defaultdict(list)
    for p in posts:
        for a in set(p["social_accounts"]):
            if a in NAME:
                ev[a].append((when(p), p["id"]))
    pairs = defaultdict(set)
    for a in NAME:
        s = sorted(ev[a])
        for i in range(1, len(s)):
            if (s[i][0] - s[i - 1][0]).total_seconds() / 60 < MIN_GAP:
                pairs[(s[i - 1][1], s[i][1])].add(NAME[a])
    # move the record with FEWER destinations; tie break on the later one
    moves = []
    for (a, b), chans in pairs.items():
        loser = a if len(byid[a]["social_accounts"]) < len(byid[b]["social_accounts"]) else b
        moves.append((loser, sorted(chans), byid[a], byid[b]))
    return dupes, empties, moves


def free_slot(post, posts, taken):
    """Earliest allowed slot from this post's own day forward that clears MIN_GAP."""
    ev = occupancy(posts, exclude=post["id"])
    for a, times in taken.items():
        ev[a].extend(times)
    chans = [a for a in set(post["social_accounts"]) if a in NAME]
    day0 = when(post).date()
    for dayoff in range(0, 14):
        day = day0 + timedelta(days=dayoff)
        for s in LADDER:
            hh, mm = map(int, s.split(":"))
            cand = datetime.combine(day, datetime.min.time()).replace(
                hour=hh, minute=mm, tzinfo=ct(day))
            if all(abs((cand - t).total_seconds()) / 60 >= MIN_GAP
                   for a in chans for t in ev[a]):
                return cand
    return None


def patch_verify(pid, body, check, attempts=4):
    for i in range(1, attempts + 1):
        try:
            api(f"/posts/{pid}", "PATCH", body)
        except urllib.error.HTTPError as e:
            if i == attempts:
                return False, f"HTTP {e.code}"
        time.sleep(1.5)
        try:
            if check(api(f"/posts/{pid}")):
                return True, f"attempt {i}"
        except Exception:
            pass
    return False, f"unverified after {attempts}"


def cmd_scan(a):
    posts = live()
    dupes, empties, moves = find_defects(posts)
    print(f"live scheduled records: {len(posts)}")
    print(f"duplicate-destination: {len(dupes)}   empty-destination: {len(empties)}   collision pairs: {len(moves)}")
    for p in dupes:
        c = Counter(p["social_accounts"])
        print(f"  DUPE {p['id']}  raw={len(p['social_accounts'])} unique={len(set(p['social_accounts']))}"
              f"  repeated={[NAME.get(k,k) for k,v in c.items() if v>1]}")
    for p in empties:
        print(f"  EMPTY {p['id']} {when(p):%Y-%m-%d %H:%M}")
    for loser, chans, A, B in moves:
        print(f"  COLLIDE {A['id'][:8]} {when(A):%Y-%m-%d %H:%M} vs {B['id'][:8]} {when(B):%H:%M}"
              f"  on {len(chans)} ch -> move {loser[:8]}")


def cmd_fix(a):
    posts = live()
    dupes, empties, moves = find_defects(posts)
    if a.dedupe or a.all:
        for p in dupes:
            # A bare social_accounts PATCH 500s on this API. Always resend
            # account_configurations alongside it, deduped by account_id.
            cur = api(f"/posts/{p['id']}")
            ac = cur.get("account_configurations") or {}
            ac = ac.get("account_configurations", []) if isinstance(ac, dict) else ac
            seen = {}
            for c in ac:
                seen.setdefault(c["account_id"], c)
            cfg, uniq = list(seen.values()), sorted(seen)
            n = len(uniq)
            ok, note = patch_verify(p["id"],
                {"social_accounts": uniq,
                 "account_configurations": {"account_configurations": cfg}},
                lambda q: len(q["social_accounts"]) == n == len(set(q["social_accounts"])))
            print(f"dedupe {p['id'][:8]}: {len(p['social_accounts'])} -> {n}  "
                  f"{'OK' if ok else 'FAILED'} ({note})")
    if a.collisions or a.all:
        posts = live()
        byid = {p["id"]: p for p in posts}
        _, _, moves = find_defects(posts)
        taken = defaultdict(list)
        done = set()
        for loser, chans, A, B in moves:
            if loser in done:
                continue
            done.add(loser)
            p = byid[loser]
            slot = free_slot(p, posts, taken)
            if not slot:
                print(f"move {loser[:8]}: NO FREE SLOT within 14 days")
                continue
            utc = slot.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            ok, note = patch_verify(loser, {"scheduled_at": utc},
                lambda q: q["scheduled_at"].replace("+00:00", "Z").startswith(utc[:16]))
            print(f"move {loser[:8]} {when(p):%Y-%m-%d %H:%M} -> {slot:%Y-%m-%d %H:%M} CT  "
                  f"{'OK' if ok else 'FAILED'} ({note})")
            if ok:
                for c in set(p["social_accounts"]):
                    if c in NAME:
                        taken[c].append(slot)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan").set_defaults(fn=cmd_scan)
    f = sub.add_parser("fix")
    f.add_argument("--dedupe", action="store_true")
    f.add_argument("--collisions", action="store_true")
    f.add_argument("--all", action="store_true")
    f.set_defaults(fn=cmd_fix)
    args = ap.parse_args()
    args.fn(args)

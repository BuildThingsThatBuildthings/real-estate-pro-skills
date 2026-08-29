#!/usr/bin/env python3
"""
Post Bridge scheduling engine. Channel set comes from config/channels.json.

  status                 current posts/day per 30-day block, next rung, gaps
  collisions             same-channel collisions in the live calendar
  plan  --count N        propose N placements honoring ramp + slots + 90-min rule

Reads the API key from ~/.config/post-bridge/config.json (same as the post-bridge CLI).
Times are Nashville CT; scheduled_at is written in UTC.
"""
import json, os, sys, argparse, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone, date

API = "https://api.post-bridge.com/v1"
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.realpath(__file__)))
import config as _cfg
CHANNELS = dict(_cfg.NAME)
N_CH = len(CHANNELS)
RUNGS = list(_cfg.RUNGS)
def _derived_slots():
    """Slot ladder derived from live analytics. Falls back to the last
    known-good ladder if analytics are unavailable."""
    try:
        import subprocess, os as _os
        out = subprocess.run(
            ["python3", _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "windows.py"),
             "ladder", "--json"], capture_output=True, text=True, timeout=120)
        lad = json.loads(out.stdout)
        return {int(k): v for k, v in lad.items()}
    except Exception:
        return {3: ["11:15", "15:15", "18:15"],
                5: ["11:15", "15:15", "18:15", "20:15", "12:15"],
                7: ["11:15", "15:15", "18:15", "20:15", "12:15", "13:20", "10:15"],
                8: ["11:15", "15:15", "18:15", "20:15", "12:15", "13:20", "10:15", "09:15"]}


SLOTS = _derived_slots()
FORBIDDEN_HOURS = set(_cfg.FORBIDDEN_HOURS)
MIN_GAP_MIN = _cfg.MIN_GAP
BLOCK = _cfg.BLOCK_DAYS


def ct_offset(d):
    """CDT (UTC-5) Mar-Nov, else CST (UTC-6). Good enough for scheduling."""
    return timezone(timedelta(hours=-5 if 3 <= d.month <= 11 else -6))


def api(path):
    key = json.load(open(os.path.expanduser("~/.config/post-bridge/config.json")))["apiKey"]
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def live_posts():
    out, off = [], 0
    while True:
        page = api(f"/posts?status=scheduled&limit=100&offset={off}")
        out += page["data"]
        if not page["meta"].get("next"):
            break
        off += 100
    return [p for p in out if not p.get("is_draft") and p.get("scheduled_at")]


def occupancy(posts):
    """channel -> sorted [datetime CT]; and date -> content units"""
    per_ch, per_day = defaultdict(list), defaultdict(int)
    for p in posts:
        t = datetime.fromisoformat(p["scheduled_at"].replace("Z", "+00:00"))
        d = t.astimezone(ct_offset(t)).replace(tzinfo=None)
        for a in set(p["social_accounts"]):
            if a in CHANNELS:
                per_ch[a].append(d)
                per_day[d.date()] += 1
    for a in per_ch:
        per_ch[a].sort()
    return per_ch, per_day


def blocks(today):
    return [[today + timedelta(days=i) for i in range(s, s + BLOCK)] for s in (0, BLOCK, 2 * BLOCK)]


def posts_per_day(per_day, days):
    return {d: per_day.get(d, 0) / N_CH for d in days}


def cmd_status(args):
    posts = live_posts()
    per_ch, per_day = occupancy(posts)
    today = date.today()
    bs = blocks(today)
    print(f"live scheduled records: {len(posts)}")
    tot_units = sum(per_day.values())
    print(f"content units on the 9 channels: {tot_units}  (~{tot_units/N_CH:.1f} posts)\n")
    cur = None
    for i, blk in enumerate(bs[:2], 1):
        ppd = posts_per_day(per_day, blk)
        avg = sum(ppd.values()) / len(blk)
        print(f"Block {i}  {blk[0]} -> {blk[-1]}   avg {avg:.2f} posts/day")
        for r in RUNGS:
            need = sum(max(0, r - round(ppd[d])) for d in blk)
            print(f"    to {r}/day: {need:4d} posts short")
    for r in RUNGS:
        if any(round(posts_per_day(per_day, b)[d]) < r for b in bs[:2] for d in b):
            cur = r
            break
    cur = cur or 8
    print(f"\ncurrent rung: {cur}/day   slots: {', '.join(SLOTS[cur])} CT")


def cmd_collisions(args):
    posts = live_posts()
    per_ch, _ = occupancy(posts)
    # intra-record duplicate destinations
    dupes = [p["id"] for p in posts
             if len(p["social_accounts"]) != len(set(p["social_accounts"]))]
    total = 0
    for a, name in CHANNELS.items():
        ev = per_ch[a]
        bad = [(ev[i - 1], ev[i], (ev[i] - ev[i - 1]).total_seconds() / 60)
               for i in range(1, len(ev)) if (ev[i] - ev[i - 1]).total_seconds() / 60 < MIN_GAP_MIN]
        total += len(bad)
        if bad:
            print(f"{name}: {len(bad)} collision(s) under {MIN_GAP_MIN} min")
            for x, y, g in bad[:5]:
                print(f"    {x:%Y-%m-%d %H:%M} -> {y:%H:%M}  ({g:.0f} min)")
    print(f"\nTOTAL same-channel collisions: {total}")
    if dupes:
        print(f"records with duplicate destinations: {len(dupes)} -> {dupes[:5]}")


LADDER = SLOTS[8]


def free_slot(per_ch, day, slot_list, pending):
    """First slot on `day` clearing MIN_GAP_MIN on all 9 channels.

    A rung is a COUNT target, not a slot whitelist: prefer the rung's own slots,
    then fall back down the full analytics-ordered ladder so a day whose preferred
    slot is blocked by an existing post still reaches the rung.
    """
    ordered = list(slot_list) + [x for x in LADDER if x not in slot_list]
    for s in ordered:
        hh, mm = map(int, s.split(":"))
        if hh in FORBIDDEN_HOURS:
            continue
        cand = datetime.combine(day, datetime.min.time()).replace(hour=hh, minute=mm)
        ok = True
        for a in CHANNELS:
            times = per_ch[a] + [t for t, _ in pending]
            if any(abs((cand - t).total_seconds()) / 60 < MIN_GAP_MIN for t in times):
                ok = False
                break
        if ok:
            return cand
    return None


def cmd_plan(args):
    posts = live_posts()
    per_ch, per_day = occupancy(posts)
    today = date.today()
    bs = blocks(today)
    placements, pending = [], []
    remaining = args.count
    for rung in RUNGS:
        for bi, blk in enumerate(bs[:2], 1):
            for d in blk:
                if remaining <= 0:
                    break
                have = round(posts_per_day(per_day, blk)[d] + sum(1 for t, _ in pending if t.date() == d))
                while have < rung and remaining > 0:
                    slot = free_slot(per_ch, d, SLOTS[rung], pending)
                    if slot is None:
                        break
                    pending.append((slot, f"block{bi}"))
                    placements.append((slot, rung, bi))
                    have += 1
                    remaining -= 1
            if remaining <= 0:
                break
        if remaining <= 0:
            break
    placements.sort()
    print(f"{'#':>3}  {'DATE':<12} {'CT':<6} {'UTC':<20} {'RUNG':<5} BLOCK  COLLISION")
    for i, (t, rung, bi) in enumerate(placements, 1):
        utc = t.replace(tzinfo=ct_offset(t.date())).astimezone(timezone.utc)
        print(f"{i:>3}  {t:%Y-%m-%d} {t:%a}  {t:%H:%M}  {utc:%Y-%m-%dT%H:%M:%SZ}  {rung}/day  b{bi}    clear")
    print(f"\nplaced {len(placements)} of {args.count} requested")
    if len(placements) < args.count:
        print(f"{args.count - len(placements)} could not be placed without violating the {MIN_GAP_MIN}-min rule")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("collisions").set_defaults(fn=cmd_collisions)
    pp = sub.add_parser("plan"); pp.add_argument("--count", type=int, required=True); pp.set_defaults(fn=cmd_plan)
    a = ap.parse_args()
    a.fn(a)

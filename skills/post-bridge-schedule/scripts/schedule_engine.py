#!/usr/bin/env python3
"""
Post Bridge scheduling engine. Channel set comes from config/channels.json.

  status                 current posts/day per 30-day block, next rung, gaps
  collisions             same-channel collisions in the live calendar
  plan  --count N        propose N placements honoring ramp + slots + spacing rules
                         (read only: prints placements, writes nothing)

Placement spreads each day across dayparts (windows.DAYPARTS, CT): morning
06-11, afternoon 12-16, evening 17:00-22:00. The posting window is 06:00 to
22:00 inclusive (config windows.earliest_start / latest_start): a post may start
exactly at 22:00, never after, never before 06:00. The next post on a day goes to that
day's emptiest daypart, counting posts already scheduled there.

Spacing: min_gap_minutes (45) between posts on the SAME account; across
different accounts only min_global_stagger_minutes (10). A planned post targets
every configured channel, so for it "same account" is every channel.

Reads the API key from ~/.config/post-bridge/config.json (same as the post-bridge CLI).
Times are Nashville CT; scheduled_at is written in UTC.
"""
import json, os, sys, argparse, urllib.request
from collections import defaultdict
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone, date

API = "https://api.post-bridge.com/v1"
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.realpath(__file__)))
import config as _cfg
import pb
import windows
import math
CHANNELS = dict(_cfg.NAME)
N_CH = len(CHANNELS)
RUNGS = list(_cfg.RUNGS)
def _derived_slots():
    """Use the same daypart ladder as create_batch and repair, never guessed slots."""
    rows = windows.rows()
    # Full daypart round-robin order: the lint's allowed set and the fallback ladder.
    global LADDER
    LADDER = windows.ladder_order(rows)
    slots = {r: LADDER[:r] for r in RUNGS}
    if any(not slots.get(r) for r in RUNGS):
        raise RuntimeError("No analytics-supported slot ladder; planning is blocked")
    return slots


SLOTS = {}  # derive only in an explicit CLI run, never while importing
FORBIDDEN_HOURS = set(_cfg.FORBIDDEN_HOURS)
MIN_GAP_MIN = _cfg.MIN_GAP
MIN_STAGGER_MIN = int(getattr(_cfg, "MIN_GLOBAL_STAGGER", 10))
BLOCK = _cfg.BLOCK_DAYS
TZ = ZoneInfo("America/Chicago")
LEAD_HOURS = float(getattr(_cfg, "LEAD_HOURS", 1))  # pipeline.json approval.lead_hours


def ct_offset(d):
    """The real Nashville offset for that date, from the tz database.

    This used to approximate DST as "March through November is UTC-5", which is
    wrong for the ~5 weeks a year that fall inside those months but outside DST:
    Nov 2-30 and Mar 1 through the second Sunday. Every slot planned in that
    window was written an hour off, and create_batch.py -- which reads the real
    zone -- then rejected it as "not in allowed set". The planner and the linter
    have to agree about what time it is.
    """
    if isinstance(d, datetime):
        d = d.date()
    noon = datetime(d.year, d.month, d.day, 12, tzinfo=ZoneInfo("America/Chicago"))
    return timezone(noon.utcoffset())


def api(path):
    return pb.req(path)


def live_posts():
    return [p for p in pb.paged('/posts')
            if p.get('status') in {'scheduled', 'posted', 'processing'}
            and not p.get('is_draft') and p.get('scheduled_at')]


def occupancy(posts):
    """channel -> sorted [datetime CT]; and date -> content units"""
    per_ch, per_day = defaultdict(list), defaultdict(int)
    seen = set()
    for p in posts:
        if p.get('id') and p['id'] in seen:
            continue
        if p.get('id'):
            seen.add(p['id'])
        t = datetime.fromisoformat(p["scheduled_at"].replace("Z", "+00:00"))
        if t.tzinfo is None:
            raise ValueError('scheduled_at must have an offset')
        d = t.astimezone(TZ).replace(tzinfo=None)
        for a in {int(x) for x in p.get("social_accounts", [])}:
            if a in CHANNELS:
                per_ch[a].append(d)
                per_day[d.date()] += 1
    for a in per_ch:
        per_ch[a].sort()
    return per_ch, per_day


def blocks(today, count=None):
    count = count if count is not None else _cfg.HORIZON_BLOCKS
    return [[today + timedelta(days=i) for i in range(b * BLOCK, (b + 1) * BLOCK)]
            for b in range(count)]


def first_day(now=None):
    now = now or datetime.now(TZ)
    return (now.astimezone(TZ) + timedelta(hours=LEAD_HOURS)).date()


def gap(units, rung):
    # Never round 8/9 deliveries up to a completed post. A new post adds N_CH units.
    return max(0, math.ceil((rung * N_CH - units) / N_CH))


def posts_per_day(per_day, days):
    return {d: per_day.get(d, 0) / N_CH for d in days}


def cmd_status(args):
    posts = live_posts()
    per_ch, per_day = occupancy(posts)
    today = first_day()
    bs = blocks(today)
    print(f"live dated scheduled/posted/processing records: {len(posts)}")
    tot_units = sum(per_day.values())
    print(f"content units on the {N_CH} channels: {tot_units}  (~{tot_units/N_CH:.1f} posts)\n")
    cur = None
    for i, blk in enumerate(bs, 1):
        ppd = posts_per_day(per_day, blk)
        avg = sum(ppd.values()) / len(blk)
        print(f"Block {i}  {blk[0]} -> {blk[-1]}   avg {avg:.2f} posts/day")
        for r in RUNGS:
            need = sum(gap(per_day.get(d, 0), r) for d in blk)
            print(f"    to {r}/day: {need:4d} posts short")
    for r in RUNGS:
        if any(gap(per_day.get(d, 0), r) for b in bs for d in b):
            cur = r
            break
    if cur is None:
        print(f"\ninitial blocks complete; open block {_cfg.HORIZON_BLOCKS + 1} at {RUNGS[0]}/day")
    else:
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
    # Cross-account stagger: informational, the 45-minute rule is per account.
    allt = sorted({t for ev in per_ch.values() for t in ev})
    close = sum(1 for i in range(1, len(allt))
                if (allt[i] - allt[i - 1]).total_seconds() / 60 < MIN_STAGGER_MIN)
    print(f"distinct times closer than the {MIN_STAGGER_MIN}-min cross-account stagger: {close}")
    if dupes:
        print(f"records with duplicate destinations: {len(dupes)} -> {dupes[:5]}")


LADDER = []  # populated with SLOTS during an explicit CLI run
DAYPART_NAMES = windows.DAYPART_NAMES


def daypart_slots(extra=()):
    """{daypart: [slots best first]} from LADDER (plus any `extra` rung slots).

    LADDER is a daypart round-robin, so filtering it by daypart keeps each
    daypart's own score order. Slots outside every daypart go last under None.
    """
    out = {n: [] for n in DAYPART_NAMES}
    out[None] = []
    for s in list(LADDER) + [x for x in extra if x not in LADDER]:
        out[windows.daypart_of(s)].append(s)
    return out


def day_load(per_ch, pending, day):
    """{daypart: posts already on `day`}, in full-post equivalents (a record on
    k of the N_CH channels counts k/N_CH, the same units the rung gap uses)."""
    load = {n: 0.0 for n in DAYPART_NAMES}
    for a, times in per_ch.items():
        if a not in CHANNELS:
            continue
        for t in times:
            dp = windows.daypart_of(t.hour)
            if t.date() == day and dp:
                load[dp] += 1 / N_CH
    for e in pending:
        dp = windows.daypart_of(e[0].hour)
        if e[0].date() == day and dp:
            load[dp] += len(_pending_accounts(e) & set(CHANNELS)) / N_CH
    return load


def day_candidates(per_ch, pending, day, rung_slots=()):
    """Slots for the next post on `day`: emptiest daypart first (ties go
    morning, afternoon, evening), each daypart's slots best first. On an empty
    day that is best morning, best afternoon, best evening, next morning, next
    afternoon. A day that already holds posts fills its emptiest dayparts."""
    load = day_load(per_ch, pending, day)
    parts = daypart_slots(rung_slots)
    order = sorted(DAYPART_NAMES, key=lambda n: (round(load[n], 6), DAYPART_NAMES.index(n)))
    return [s for n in order for s in parts[n]] + parts[None]


def _pending_accounts(entry):
    """pending entries are (time, label) for a full-roster post, or (time, label, accounts)."""
    return set(entry[2]) if len(entry) > 2 else set(CHANNELS)


def slot_conflict(cand, accounts, per_ch, pending):
    """Why `cand` (naive CT) cannot hold a post on `accounts`, or None if it can.

    MIN_GAP_MIN applies only to posts sharing an account with the candidate.
    Every other post, on any configured account, only needs MIN_STAGGER_MIN.
    """
    for a in accounts:
        times = list(per_ch.get(a, [])) + [e[0] for e in pending if a in _pending_accounts(e)]
        for t in times:
            if abs((cand - t).total_seconds()) / 60 < MIN_GAP_MIN:
                return f"{CHANNELS.get(a, a)} within {MIN_GAP_MIN} min of {t:%H:%M}"
    others = [t for ev in per_ch.values() for t in ev] + [e[0] for e in pending]
    for t in others:
        if abs((cand - t).total_seconds()) / 60 < MIN_STAGGER_MIN:
            return f"within the {MIN_STAGGER_MIN}-min cross-account stagger of {t:%H:%M}"
    return None


def free_slot(per_ch, day, slot_list, pending, earliest=None, accounts=None):
    """First slot on `day` that clears the spacing rules for `accounts`.

    `accounts` defaults to every configured channel, because a planned post fans
    out to all of them as ONE record. The 45-minute gap is checked on those
    accounts only; posts on other accounts need just the global stagger.

    A rung is a COUNT target, not a slot whitelist: prefer the listed slots. A
    blocked slot falls back to the rest of its own daypart first (best first),
    then to the rest of the ladder, so a day whose preferred slot is blocked by
    an existing post still reaches the rung without drifting to another part of
    the day.
    """
    accounts = set(CHANNELS) if accounts is None else set(accounts)
    ordered = []
    for s in slot_list:
        dp = windows.daypart_of(s)
        for x in [s] + [x for x in LADDER if dp and windows.daypart_of(x) == dp]:
            if x not in ordered:
                ordered.append(x)
    ordered += [x for x in LADDER if x not in ordered]
    for s in ordered:
        hh, mm = map(int, s.split(":"))
        if hh in FORBIDDEN_HOURS or not windows.in_window(s):
            continue
        cand = datetime.combine(day, datetime.min.time()).replace(hour=hh, minute=mm)
        if earliest is not None and cand.replace(tzinfo=TZ) < earliest:
            continue
        if slot_conflict(cand, accounts, per_ch, pending) is None:
            return cand
    return None


def plan_placements(posts, count, *, now=None):
    """Fill each block in order at each rung; any unfillable gap stops advancement.

    Initial horizon uses the configured blocks. Once all reach the top rung,
    open one further block and restart at the first rung, as the skill specifies.
    This function is pure: callers supply live records and analytics slots.
    """
    if count < 0 or not RUNGS or N_CH < 1 or BLOCK < 1 or _cfg.HORIZON_BLOCKS < 1:
        raise ValueError('Invalid count, channels, or ramp configuration')
    now = now or datetime.now(TZ)
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    earliest = now.astimezone(TZ) + timedelta(hours=LEAD_HOURS)
    per_ch, per_day = occupancy(posts)
    placements, pending = [], []
    remaining = count
    first = 0
    width = _cfg.HORIZON_BLOCKS
    while remaining:
        for rung in RUNGS:
            for bi in range(first, first + width):
                days = [earliest.date() + timedelta(days=bi * BLOCK + i) for i in range(BLOCK)]
                blocked = []
                for d in days:
                    have = per_day.get(d, 0) + N_CH * sum(t.date() == d for t, _ in pending)
                    while gap(have, rung) and remaining:
                        slot = free_slot(per_ch, d, day_candidates(per_ch, pending, d, SLOTS[rung]),
                                         pending, earliest)
                        if slot is None:
                            blocked.append({'date': d.isoformat(), 'block': bi + 1,
                                            'rung': rung, 'missing_posts': gap(have, rung)})
                            break
                        pending.append((slot, f'block{bi + 1}'))
                        placements.append((slot, rung, bi + 1))
                        have += N_CH
                        remaining -= 1
                    if not remaining:
                        return placements, []
                if blocked:
                    return placements, blocked
        first += width
        width = 1
    return placements, []


def cmd_plan(args):
    placements, blocked = plan_placements(live_posts(), args.count)
    placements.sort()
    print(f"{'#':>3}  {'DATE':<12} {'CT':<6} {'UTC':<20} {'RUNG':<5} BLOCK  COLLISION")
    for i, (t, rung, bi) in enumerate(placements, 1):
        utc = t.replace(tzinfo=ct_offset(t.date())).astimezone(timezone.utc)
        print(f"{i:>3}  {t:%Y-%m-%d} {t:%a}  {t:%H:%M}  {utc:%Y-%m-%dT%H:%M:%SZ}  {rung}/day  b{bi}    clear")
    print(f"\nplaced {len(placements)} of {args.count} requested")
    if len(placements) < args.count:
        print(f"{args.count - len(placements)} could not be placed without violating the "
              f"{MIN_GAP_MIN}-min same-account gap or the {MIN_STAGGER_MIN}-min stagger")
    if blocked:
        print('Ramp advancement blocked by unfilled earlier dates:')
        print(json.dumps(blocked, indent=2))


if __name__ == "__main__":
    SLOTS = _derived_slots()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("collisions").set_defaults(fn=cmd_collisions)
    pp = sub.add_parser("plan"); pp.add_argument("--count", type=int, required=True); pp.set_defaults(fn=cmd_plan)
    a = ap.parse_args()
    a.fn(a)

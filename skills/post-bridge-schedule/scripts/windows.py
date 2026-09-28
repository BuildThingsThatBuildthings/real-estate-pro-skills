#!/usr/bin/env python3
"""
Derive posting windows from your own analytics. No hardcoded slots.

  windows.py report              hour + weekday performance, ranked
  windows.py ladder              emit the slot ladder for the configured rungs
  windows.py ladder --json       machine readable, for the planner

Source, in order:
  1. The War Room warehouse verb `social.windows` (pipeline.json
     windows.warehouse_url), when it answers, has computed windows, and they are
     no older than windows.warehouse_max_age_hours (48).
  2. Otherwise the live Post Bridge analytics, with a loud notice on stderr.
Both paths feed the same scoring, so the ladder does not depend on the source.

Scoring uses the MEDIAN, never the mean: one viral post must not move an hour.
  - views for the view-reliable platforms (tiktok, youtube, facebook),
  - likes for instagram (feed photos report 0 views).
Each platform's per-hour median is normalized by that platform's best allowed
hour. An hour's score is
  view_weight * mean(normalized view medians of the platforms with enough posts)
              * sqrt(those platforms / view platforms with enough posts at any hour)
  + like_weight * normalized instagram median likes.
The square-root coverage factor keeps an hour backed by one platform from
outranking an hour backed by three purely through averaging.
Hours with fewer than min_records_per_hour posts on a platform do not count for
that platform. Forbidden hours are never scored.

Slots spread by daypart (CT): morning 06-11, afternoon 12-16, evening 17:00-22:00.
The ladder is best morning, best afternoon, best evening, then round-robin the
next-best remaining hour of each daypart. A daypart with no scored hour still
gets one slot (its hour with the most posts on record, else 09/13/19). Slots are
HH:15, except hour 22, whose slot is exactly 22:00: the posting window is
06:00 to 22:00 inclusive (windows.earliest_start / latest_start), so the last
post may start at 22:00 and nothing starts after it.

Post Bridge syncs analytics for TikTok, YouTube, Instagram and Facebook only.
X, LinkedIn and Google Business return nothing, so they cannot inform timing.
"""
import json, os, sys, argparse, subprocess, statistics as st, urllib.request, urllib.error
from collections import defaultdict
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

API = "https://api.post-bridge.com/v1"
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.realpath(__file__)))
import config as _cfg
import pb
VIEW_RELIABLE = set(_cfg.VIEW_RELIABLE)
LIKE_SIGNAL = set(getattr(_cfg, "LIKE_SIGNAL", {"instagram"}))
MIN_N = _cfg.MIN_RECORDS_PER_HOUR   # ignore hours with too little evidence
RUNG_SIZES = {r: r for r in _cfg.RUNGS}
FORBIDDEN = set(_cfg.FORBIDDEN_HOURS)   # never schedule overnight
# Posting window, CT, inclusive at both ends: 22:00 is a legal start, 22:15 is not.
EARLIEST_START = getattr(_cfg, "EARLIEST_START", "06:00")
LATEST_START = getattr(_cfg, "LATEST_START", "22:00")


def _minutes(hhmm):
    h, m = map(int, str(hhmm).split(":")[:2])
    return h * 60 + m


def in_window(hhmm):
    """True when an "HH:MM" CT start is inside EARLIEST_START..LATEST_START, inclusive.
    The one window check that free_slot, the create_batch lint and repair all use."""
    return _minutes(EARLIEST_START) <= _minutes(hhmm) <= _minutes(LATEST_START)
WAREHOUSE_URL = getattr(_cfg, "WAREHOUSE_URL", "")
WAREHOUSE_MAX_AGE_HOURS = float(getattr(_cfg, "WAREHOUSE_MAX_AGE_HOURS", 48))
KEY_ENV = "WARROOM_OPS_KEY"
KEYCHAIN_SERVICE = "warroom-ops-key"
TZ = ZoneInfo("America/Chicago")


def ct(d):
    return TZ


def api(p):
    return pb.req(p)


class WarehouseUnavailable(RuntimeError):
    pass


class Rows(list):
    """Per-post analytics rows plus the per-platform, per-hour table scoring uses.

    A plain list keeps every caller working (`rows()` used to return one). When
    the warehouse answers there are no per-post rows, only `stats`.
      stats:  {platform: {hour: (n, median_of_that_platform's_metric)}}
      source: "warehouse" | "live"
    """
    def __init__(self, items=(), stats=None, source="live", meta=None, weekdays=None):
        super().__init__(items)
        self.stats = stats if stats is not None else {}
        self.source = source
        self.meta = meta or {}
        self.weekdays = weekdays or {}


def metric_for(platform):
    if platform in VIEW_RELIABLE:
        return "views"
    if platform in LIKE_SIGNAL:
        return "likes"
    return None


# ---------------------------------------------------------------- live source

def live_rows():
    out = pb.paged("/analytics")
    res = []
    for r in out:
        if not r.get("platform_created_at"):
            continue
        t = datetime.fromisoformat(r["platform_created_at"].replace("Z", "+00:00"))
        t = t.astimezone(ct(t))
        res.append(dict(p=r["platform"], t=t, v=r.get("view_count") or 0,
                        l=r.get("like_count") or 0))
    return res


def stats_from_rows(rs):
    """{platform: {hour: (n, median)}} on each platform's own metric."""
    g = defaultdict(lambda: defaultdict(list))
    for r in rs:
        m = metric_for(r["p"])
        if m is None:
            continue
        g[r["p"]][r["t"].hour].append(r["v"] if m == "views" else r["l"])
    return {p: {h: (len(v), st.median(v)) for h, v in hours.items()} for p, hours in g.items()}


def weekdays_from_rows(rs):
    g = defaultdict(list)
    for r in rs:
        if r["p"] in VIEW_RELIABLE:
            g[r["t"].strftime("%w %a")].append(r["v"])
    return {k: (len(v), st.median(v)) for k, v in sorted(g.items())}


# ---------------------------------------------------------------- warehouse

def ops_key():
    k = os.environ.get(KEY_ENV)
    if k:
        return k.strip()
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
                             capture_output=True, text=True, timeout=10)
    except Exception as e:
        raise WarehouseUnavailable(f"no ops key ({type(e).__name__})")
    if out.returncode != 0 or not out.stdout.strip():
        raise WarehouseUnavailable(f"no ops key (env {KEY_ENV} unset, keychain {KEYCHAIN_SERVICE} missing)")
    return out.stdout.strip()


def fetch_warehouse(url=None, timeout=20):
    url = url or WAREHOUSE_URL
    if not url:
        raise WarehouseUnavailable("windows.warehouse_url not configured")
    req = urllib.request.Request(url, method="POST", data=b"{}",
                                 headers={"x-ops-key": ops_key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except WarehouseUnavailable:
        raise
    except urllib.error.HTTPError as e:
        raise WarehouseUnavailable(f"HTTP {e.code}")
    except Exception as e:
        raise WarehouseUnavailable(f"{type(e).__name__}: {e}")


def parse_warehouse(resp, now=None, max_age_hours=None):
    """Validate a social.windows response and turn it into a Rows(stats=...).

    Raises WarehouseUnavailable with the reason when the answer cannot be used.
    """
    max_age_hours = WAREHOUSE_MAX_AGE_HOURS if max_age_hours is None else max_age_hours
    if not isinstance(resp, dict):
        raise WarehouseUnavailable("response is not an object")
    if not resp.get("ok", False):
        raise WarehouseUnavailable(f"ok=false ({resp.get('error') or resp.get('message') or 'no detail'})")
    if not resp.get("found", False):
        raise WarehouseUnavailable("found=false (no windows computed yet)")
    computed = resp.get("computedAt")
    age = resp.get("ageHours")
    if age is None and computed is not None:
        now = now or datetime.now(timezone.utc)
        age = (now.timestamp() * 1000 - float(computed)) / 3_600_000
    if age is None:
        raise WarehouseUnavailable("no computedAt/ageHours")
    if float(age) > max_age_hours:
        raise WarehouseUnavailable(f"stale: {float(age):.1f}h old > {max_age_hours:g}h")
    stats, facts = {}, 0
    for plat in resp.get("platforms") or []:
        p = plat.get("platform")
        m = metric_for(p)
        if m is None:
            continue
        want = plat.get("metric") or m
        hours = {}
        for h in plat.get("hours") or []:
            n = int(h.get("n") or 0)
            facts += n
            med = h.get("score")
            if med is None:
                med = h.get("medianViews") if want == "views" else h.get("medianLikes")
            hours[int(h["hour"])] = (n, float(med or 0))
        stats[p] = hours
    if not stats:
        raise WarehouseUnavailable("no usable platforms in response")
    weekdays = {}
    for plat in resp.get("platforms") or []:
        if plat.get("platform") not in VIEW_RELIABLE:
            continue
        for w in plat.get("weekdays") or []:
            k = w.get("weekday", w.get("day"))
            if k is None:
                continue
            weekdays.setdefault(f"{plat['platform']} {k}", (int(w.get("n") or 0),
                                                          w.get("medianViews", w.get("score"))))
    iso = (datetime.fromtimestamp(float(computed) / 1000, timezone.utc).isoformat()
           if computed is not None else "unknown")
    meta = dict(computedAt=iso, ageHours=float(age), facts=int(resp.get("facts") or facts),
                tz=resp.get("tz"), allowedHours=resp.get("allowedHours"),
                minSample=resp.get("minSample"))
    return Rows([], stats=stats, source="warehouse", meta=meta, weekdays=weekdays)


def rows():
    """Warehouse first; live Post Bridge analytics when it is unavailable or stale."""
    try:
        rs = parse_warehouse(fetch_warehouse())
        print(f"WINDOWS SOURCE: warehouse (computed {rs.meta['computedAt']}, "
              f"{rs.meta['facts']} facts)", file=sys.stderr)
        return rs
    except WarehouseUnavailable as e:
        reason = str(e)
    print("!" * 78 + f"\nWINDOWS SOURCE: live Post Bridge fallback (warehouse unavailable: {reason})\n"
          + "!" * 78, file=sys.stderr)
    live = live_rows()
    return Rows(live, stats=stats_from_rows(live), source="live",
                meta=dict(reason=reason, facts=len(live)), weekdays=weekdays_from_rows(live))


# ---------------------------------------------------------------- scoring

def _stats(rs):
    s = getattr(rs, "stats", None)
    return s if s else stats_from_rows(rs)


def score(rs):
    """{hour: detail} ordered best first. See the module docstring for the formula."""
    stats = _stats(rs)
    best = {}
    for p, hours in stats.items():
        best[p] = max((m for h, (n, m) in hours.items() if n >= MIN_N and h not in FORBIDDEN),
                      default=0)
    # Coverage: view platforms with enough posts at ANY allowed hour. An hour backed by
    # fewer of them has its view component scaled by sqrt(covered / this), so one
    # platform alone cannot outrank a well-covered hour purely by averaging.
    view_any = sum(1 for p, hours in stats.items() if metric_for(p) == "views"
                   and any(n >= MIN_N and h not in FORBIDDEN for h, (n, _) in hours.items()))
    out = {}
    for h in range(24):
        if h in FORBIDDEN:
            continue
        vparts, lparts, detail = [], [], {}
        for p, hours in stats.items():
            n, m = hours.get(h, (0, 0))
            if n:
                detail[p] = dict(n=n, median=m, enough=n >= MIN_N)
            if n < MIN_N:
                continue
            norm = (m / best[p]) if best[p] else 0.0
            (vparts if metric_for(p) == "views" else lparts).append(norm)
        if not vparts and not lparts:
            continue
        coverage = (len(vparts) / view_any) ** 0.5 if view_any else 0.0
        s = (_cfg.VIEW_WEIGHT * (sum(vparts) / len(vparts) if vparts else 0.0) * coverage
             + _cfg.LIKE_WEIGHT * (sum(lparts) / len(lparts) if lparts else 0.0))
        out[h] = dict(score=round(s, 3),
                      n_views=sum(d["n"] for p, d in detail.items() if metric_for(p) == "views"),
                      n_likes=sum(d["n"] for p, d in detail.items() if metric_for(p) == "likes"),
                      view_coverage=f"{len(vparts)}/{view_any}", platforms=detail)
    return dict(sorted(out.items(), key=lambda x: (-x[1]["score"], x[0])))


# ---------------------------------------------------------------- dayparts
#
# Posts spread across the whole day instead of clustering in the top-scored
# hours. Each daypart ranks its own hours by score; the ladder takes the best
# of each daypart first (rung 3 = one per daypart), then round-robins the
# next-best remaining hour of each daypart.
#   (name, first hour, last hour, default hour when the daypart has no evidence)
DAYPARTS = (("morning", 6, 11, 9), ("afternoon", 12, 16, 13), ("evening", 17, 22, 19))
DAYPART_NAMES = tuple(d[0] for d in DAYPARTS)
LADDER_SIZE = 8


def slot_for(h):
    """HH:15, clamped into the posting window: an hour whose :15 falls past
    latest_start but whose :00 does not (22 with a 22:00 latest start) gets
    exactly latest_start; likewise earliest_start for the opening hour."""
    s = f"{h:02d}:15"
    if in_window(s):
        return s
    if _minutes(s) > _minutes(LATEST_START) and in_window(f"{h:02d}:00"):
        return LATEST_START
    if _minutes(s) < _minutes(EARLIEST_START) and EARLIEST_START.startswith(f"{h:02d}:"):
        return EARLIEST_START
    return s


def hour_open(h):
    """True when hour `h` has a legal slot: not forbidden and inside the window."""
    return h not in FORBIDDEN and in_window(slot_for(h))


def daypart_of(h):
    """Daypart name for an hour (int) or an "HH:MM" slot; None outside 06-22."""
    if isinstance(h, str):
        h = int(h.split(":")[0])
    for name, lo, hi, _ in DAYPARTS:
        if lo <= h <= hi:
            return name
    return None


def hour_evidence(rs):
    """{hour: posts on record at that hour, any platform, any sample size}."""
    ev = defaultdict(int)
    for hours in _stats(rs).values():
        for h, (n, _) in hours.items():
            ev[int(h)] += n
    return dict(ev)


def daypart_hours(rs, sc=None):
    """{daypart: [hours best first]}. Never leaves a daypart empty.

    Scored hours rank by score. A daypart with no scored hour gets its hour with
    the most posts on record (even below min_records_per_hour), else its default.
    Forbidden hours are never used.
    """
    sc = score(rs) if sc is None else sc
    ev = None
    out = {}
    for name, lo, hi, default in DAYPARTS:
        allowed = [h for h in range(lo, hi + 1) if hour_open(h)]
        ranked = [h for h in sc if h in allowed]
        if not ranked and allowed:
            ev = hour_evidence(rs) if ev is None else ev
            seen = [h for h in allowed if ev.get(h)]
            if seen:
                ranked = [max(seen, key=lambda h: (ev[h], -abs(h - default)))]
            else:
                ranked = [min(allowed, key=lambda h: abs(h - default))]
        out[name] = ranked
    return out


def ladder_order(rs, limit=None):
    """Every candidate slot, daypart round-robin: best morning, best afternoon,
    best evening, then the next-best remaining hour of each daypart in turn."""
    parts = daypart_hours(rs)
    queues = [list(parts[n]) for n in DAYPART_NAMES]
    order = []
    while any(queues):
        for q in queues:
            if q:
                order.append(slot_for(q.pop(0)))
    return order[:limit] if limit else order


def ladder(rs):
    slots = ladder_order(rs, max([LADDER_SIZE] + list(RUNG_SIZES.values())))
    return {r: slots[:n] for r, n in RUNG_SIZES.items()}


# ---------------------------------------------------------------- CLI

PLAT_COLS = ("tiktok", "youtube", "facebook", "instagram")


def _cell(d):
    if not d:
        return "-"
    return f"{d['median']:g}({d['n']}){'' if d['enough'] else '*'}"


def cmd_report(a):
    rs = rows()
    stats = _stats(rs)
    total = sum(n for hours in stats.values() for n, _ in hours.values())
    print(f"source: {rs.source if isinstance(rs, Rows) else 'live'}   scored records: {total}   "
          f"min per hour per platform: {MIN_N}")
    print("cells are median(n); views for tiktok/youtube/facebook, likes for instagram; "
          "* = too few posts, not counted\n")
    print(f"{'HOUR':<6}{'score':>7}  " + "".join(f"{c:>16}" for c in PLAT_COLS))
    for h, d in score(rs).items():
        print(f"{h:02d}:00{d['score']:>7}  "
              + "".join(f"{_cell(d['platforms'].get(c)):>16}" for c in PLAT_COLS))
    wk = getattr(rs, "weekdays", None) or {}
    if wk:
        print("\nWEEKDAY (median views, view-reliable set)")
        for k, (n, med) in wk.items():
            print(f"  {k}  n={n:<4} median={med if med is not None else '-'}")
    print(f"\nposting window: {EARLIEST_START}-{LATEST_START} CT inclusive   excluded hours:",
          ", ".join(f"{h:02d}" for h in sorted(FORBIDDEN)))


def cmd_ladder(a):
    rs = rows()
    lad = ladder(rs)
    if a.json:
        print(json.dumps(lad, indent=1))
        return
    sc = score(rs)
    print("Derived slot ladder (CT): daypart spread, each daypart ranked by median-based score\n")
    for r in sorted(lad):
        print(f"  {r}/day: {', '.join(lad[r])}")
    print(f"\nfull order ({LADDER_SIZE}): {', '.join(ladder_order(rs, LADDER_SIZE))}")
    for name, hours in daypart_hours(rs, sc).items():
        tag = "" if any(h in sc for h in hours) else "   (no scored hour: fallback)"
        print(f"  {name:<9} {', '.join(slot_for(h) for h in hours)}{tag}")
    print("\nranking basis:")
    for h, d in list(sc.items())[:10]:
        per = "  ".join(f"{p}={_cell(v)}" for p, v in sorted(d["platforms"].items()))
        print(f"  {h:02d}:00  score={d['score']:<6} {per}")
    print(f"\nposting window: {EARLIEST_START}-{LATEST_START} CT inclusive   excluded hours:",
          ", ".join(f"{h:02d}" for h in sorted(FORBIDDEN)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    l = sub.add_parser("ladder"); l.add_argument("--json", action="store_true"); l.set_defaults(fn=cmd_ladder)
    args = ap.parse_args()
    args.fn(args)

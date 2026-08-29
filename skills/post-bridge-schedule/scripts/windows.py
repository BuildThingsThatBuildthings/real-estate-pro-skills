#!/usr/bin/env python3
"""
Derive posting windows from live Post Bridge analytics. No hardcoded slots.

  windows.py report              hour + weekday performance, ranked
  windows.py ladder              emit the slot ladder for rungs 3/5/7/8
  windows.py ladder --json       machine readable, for the planner

Post Bridge syncs analytics for TikTok, YouTube, Instagram and Facebook only.
X, LinkedIn and Google Business return nothing, so they cannot inform timing.
Instagram feed photos report 0 views, so views are computed on the
view-reliable set (yt/tt/fb) and Instagram contributes via likes.
"""
import json, os, sys, argparse, statistics as st, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

API = "https://api.post-bridge.com/v1"
VIEW_RELIABLE = {"youtube", "tiktok", "facebook"}
MIN_N = 8           # ignore hours with too little evidence
RUNG_SIZES = {3: 3, 5: 5, 7: 7, 8: 8}
FORBIDDEN = {0, 1, 2, 3, 4, 5, 6, 7, 22, 23}   # never schedule overnight


def ct(d):
    return timezone(timedelta(hours=-5 if 3 <= d.month <= 11 else -6))


def api(p):
    k = json.load(open(os.path.expanduser("~/.config/post-bridge/config.json")))["apiKey"]
    r = urllib.request.Request(f"{API}{p}", headers={"Authorization": f"Bearer {k}"})
    with urllib.request.urlopen(r) as resp:
        return json.load(resp)


def rows():
    out, off = [], 0
    while True:
        pg = api(f"/analytics?limit=100&offset={off}")
        out += pg["data"]
        if not pg["meta"].get("next"):
            break
        off += 100
    res = []
    for r in out:
        if not r.get("platform_created_at"):
            continue
        t = datetime.fromisoformat(r["platform_created_at"].replace("Z", "+00:00"))
        t = t.astimezone(ct(t))
        res.append(dict(p=r["platform"], t=t, v=r.get("view_count") or 0,
                        l=r.get("like_count") or 0))
    return res


def by_hour(rs, metric, subset=None):
    g = defaultdict(list)
    for r in rs:
        if subset and r["p"] not in subset:
            continue
        g[r["t"].hour].append(r[metric])
    return {h: (len(v), sum(v), sum(v) / len(v), st.median(v)) for h, v in g.items()}


def score(rs):
    """Blend: mean views on view-reliable platforms + mean IG likes, normalized."""
    vh = by_hour(rs, "v", VIEW_RELIABLE)
    lh = by_hour(rs, "l", {"instagram"})
    vmax = max((m for n, _, m, _ in vh.values() if n >= MIN_N), default=1) or 1
    lmax = max((m for n, _, m, _ in lh.values() if n >= MIN_N), default=1) or 1
    out = {}
    for h in range(24):
        if h in FORBIDDEN:
            continue
        vn, _, vm, _ = vh.get(h, (0, 0, 0, 0))
        ln, _, lm, _ = lh.get(h, (0, 0, 0, 0))
        if vn < MIN_N and ln < MIN_N:
            continue
        s = 0.75 * (vm / vmax) + 0.25 * (lm / lmax)
        out[h] = dict(score=round(s, 3), n_views=vn, mean_views=round(vm, 1),
                      n_likes=ln, mean_likes=round(lm, 2))
    return dict(sorted(out.items(), key=lambda x: -x[1]["score"]))


def cmd_report(a):
    rs = rows()
    print(f"analytics records: {len(rs)}   "
          f"view-reliable (yt/tt/fb): {sum(1 for r in rs if r['p'] in VIEW_RELIABLE)}")
    print(f"\n{'HOUR':<6}{'n(v)':>6}{'mean views':>12}{'median':>9}{'n(ig)':>7}{'mean likes':>12}{'score':>8}")
    for h, d in score(rs).items():
        print(f"{h:02d}:00{d['n_views']:>7}{d['mean_views']:>12}"
              f"{by_hour(rs,'v',VIEW_RELIABLE).get(h,(0,0,0,0))[3]:>9.0f}"
              f"{d['n_likes']:>7}{d['mean_likes']:>12}{d['score']:>8}")
    print("\nWEEKDAY (views, view-reliable set)")
    g = defaultdict(list)
    for r in rs:
        if r["p"] in VIEW_RELIABLE:
            g[r["t"].strftime("%w %a")].append(r["v"])
    for k in sorted(g):
        v = g[k]
        print(f"  {k}  n={len(v):<4} mean={sum(v)/len(v):6.1f}  median={st.median(v):5.0f}")


def ladder(rs):
    ranked = list(score(rs))
    slots, used = [], set()
    for h in ranked:
        if h in used:
            continue
        used.add(h)
        slots.append(f"{h:02d}:15" if h != 13 else "13:20")
        if len(slots) >= 8:
            break
    return {r: slots[:n] for r, n in RUNG_SIZES.items()}


def cmd_ladder(a):
    rs = rows()
    lad = ladder(rs)
    if a.json:
        print(json.dumps(lad, indent=1))
        return
    sc = score(rs)
    print("Derived slot ladder (CT), ranked by blended score\n")
    for r in (3, 5, 7, 8):
        print(f"  {r}/day: {', '.join(lad[r])}")
    print("\nranking basis:")
    for h, d in list(sc.items())[:10]:
        print(f"  {h:02d}:00  score={d['score']:<6} mean_views={d['mean_views']:<7} (n={d['n_views']})")
    print("\nexcluded overnight hours:", ", ".join(f"{h:02d}" for h in sorted(FORBIDDEN)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    l = sub.add_parser("ladder"); l.add_argument("--json", action="store_true"); l.set_defaults(fn=cmd_ladder)
    args = ap.parse_args()
    args.fn(args)

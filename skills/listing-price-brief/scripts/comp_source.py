#!/usr/bin/env python3
"""
Acquire comparable sales. Three tiers, one normalized output.

  comp_source.py tiers                                  what is available, and what each requires
  comp_source.py load --tier export --in comps.csv --out comps.json
  comp_source.py load --tier export --in rpr-export.csv --out comps.json --map mls_field_map.json
  comp_source.py browser-plan --market {slug}           the supervised session checklist

Tiers, in the order you should reach for them
---------------------------------------------
  export   the agent exports comps from their own MLS or from RPR and drops the file.
           Always works, no agreement required, zero risk. This tier must never stop
           working, because it is the fallback in every market where the others are
           unavailable.

  browser  a browser agent drives the agent's OWN logged-in session, agent-initiated,
           with the agent present, running the search they would have run themselves.
           Constraints are not optional -- see `browser-plan`.

  reso     RESO Web API 2.0 under the broker's IDX/VOW agreement. The correct
           long-term path, and the only one that is fully unattended. Requires a
           signed agreement per MLS, so it is configured per market or not at all.

Why the tiers exist rather than one scraper
-------------------------------------------
MLS rules of use are per-MLS and real. Credential sharing and unattended automated
retrieval are violations at nearly every board, and the suspension and fines land on
the sponsoring agent, not on the software. So the acquisition path is a configured
choice with the constraints written into it, and `export` is always there.

This module never invents a comp. It reads what it is given and normalizes it.
"""
import argparse, csv, datetime as dt, json, os, re, sys

_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.realpath(os.path.join(_HERE, "..", "..", "post-bridge-schedule", "scripts")))
try:
    import config as _cfg
except Exception:  # noqa: BLE001 — config is optional; export tier works without it
    _cfg = None

# Field names seen across MLS and RPR exports, normalized to one vocabulary.
# Extend this rather than hand-editing exports: a hand-edited export is a comp
# set nobody can reproduce.
ALIASES = {
    "address": ["address", "full address", "street address", "property address", "location", "addr"],
    "close_price": ["close price", "closed price", "sold price", "sale price", "sp", "closeprice", "price"],
    "close_date": ["close date", "closed date", "sold date", "sale date", "cd", "closedate"],
    "sqft": ["sqft", "sq ft", "square feet", "living area", "gla", "above grade finished area", "total sqft"],
    "beds": ["beds", "bedrooms", "br", "bedroomstotal", "total bedrooms"],
    "baths": ["baths", "bathrooms", "ba", "bathroomstotalinteger", "total baths"],
    "garage": ["garage", "garage spaces", "gar", "garagespaces"],
    "lot_sqft": ["lot sqft", "lot size", "lot size sqft", "lotsizesquarefeet", "lot"],
    "year_built": ["year built", "yr built", "yearbuilt", "yb"],
    "condition": ["condition", "property condition", "cond"],
    "distance_mi": ["distance", "distance mi", "miles", "proximity"],
    "dom": ["dom", "days on market", "cdom", "daysonmarket"],
    "notes": ["notes", "remarks", "public remarks", "comment", "comments"],
    "exclude": ["exclude", "excluded", "omit"],
    "exclude_reason": ["exclude reason", "exclusion reason", "why excluded", "omit reason"],
}
NUMERIC = {"close_price", "sqft", "beds", "baths", "garage", "lot_sqft", "year_built", "distance_mi", "dom"}
REQUIRED = ["address", "close_price", "close_date", "sqft"]


def build_map(headers, extra_map=None):
    """Map this file's headers onto the normalized vocabulary."""
    lookup = {}
    for h in headers:
        key = (h or "").strip().lower()
        for canon, names in ALIASES.items():
            if key in names or key.replace("_", " ") in names:
                lookup[h] = canon
                break
    if extra_map:
        for src, canon in extra_map.items():
            lookup[src] = canon
    return lookup


def to_number(v):
    if v is None:
        return None
    s = re.sub(r"[^\d.\-]", "", str(v))
    if s in ("", "-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def to_date(v):
    s = (v or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%d-%b-%Y", "%b %d, %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def load_export(path, extra_map=None):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"{path} has no rows")
    lookup = build_map(rows[0].keys(), extra_map)
    missing = [r for r in REQUIRED if r not in lookup.values()]
    if missing:
        raise SystemExit(
            f"{path} is missing required field(s): {missing}\n"
            f"  recognized: {sorted(set(lookup.values()))}\n"
            f"  headers seen: {list(rows[0].keys())}\n"
            f"  Map them with --map '{{\"Your Header\": \"close_price\"}}' rather than editing the export;\n"
            f"  a hand-edited export is a comp set nobody can reproduce.")
    out = []
    for i, r in enumerate(rows, start=1):
        c = {"comp_id": f"K{i:02d}"}
        for src, canon in lookup.items():
            v = r.get(src)
            if canon in NUMERIC:
                c[canon] = to_number(v)
            elif canon == "close_date":
                c[canon] = to_date(v)
            else:
                c[canon] = (v or "").strip()
        c["exclude"] = str(c.get("exclude", "")).strip().lower() in ("y", "yes", "true", "1", "x")
        out.append(c)
    return out


def cmd_load(a):
    if a.tier != "export":
        raise SystemExit(
            f"tier {a.tier!r} is not wired in this build.\n"
            f"  'browser' needs a supervised session — run: comp_source.py browser-plan --market {{slug}}\n"
            f"  'reso'    needs a signed IDX/VOW agreement for that MLS and a per-market config entry.\n"
            f"  Use --tier export today; it is the fallback that always works.")
    extra = json.load(open(a.map)) if a.map else None
    comps = load_export(a.inp, extra)
    doc = {
        "schema": "listing-price-brief/comps/v1",
        "tier": a.tier,
        "acquired_from": os.path.basename(a.inp),
        "acquired_at": a.as_of or dt.date.today().isoformat(),
        "comp_count": len(comps),
        "included": sum(1 for c in comps if not c["exclude"]),
        "comps": comps,
    }
    incomplete = [c["comp_id"] for c in comps
                  if not c["exclude"] and any(c.get(k) in (None, "") for k in REQUIRED)]
    if incomplete:
        doc["incomplete"] = incomplete
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"tier={a.tier}  {len(comps)} comp(s), {doc['included']} included -> {a.out}")
    if incomplete:
        print(f"  incomplete (missing a required field): {', '.join(incomplete)}")
    print("nothing was invented; every field came from the file.")
    return 0


def cmd_tiers(_a):
    cfg = {}
    if _cfg:
        try:
            cfg = _cfg.load("mls", required=False)
        except Exception:  # noqa: BLE001
            cfg = {}
    print("comp acquisition tiers\n")
    print("  export   READY — always. Agent exports from their own MLS or RPR.")
    print("           RPR is included with NAR membership at no extra cost.")
    print(f"  browser  {'CONFIGURED' if cfg.get('browser') else 'not configured'} — supervised session only.")
    print("           agent-initiated, agent present, their own login, never headless,")
    print("           never scheduled, credentials never stored or replayed.")
    print(f"  reso     {'CONFIGURED' if cfg.get('reso') else 'not configured'} — RESO Web API 2.0.")
    print("           needs the broker's signed IDX/VOW agreement with that MLS.")
    if cfg:
        print(f"\n  config: {cfg.get('_source')}")
    else:
        print("\n  no config/mls.json — export tier only, which is a fine place to operate.")
    return 0


def cmd_browser_plan(a):
    print(f"supervised comp pull — {a.market or 'unspecified market'}\n")
    print("These are constraints, not preferences. Credential sharing and unattended")
    print("automated retrieval violate the rules of use at nearly every board, and the")
    print("suspension and the fine land on the sponsoring agent.\n")
    for i, step in enumerate([
        "The AGENT opens their MLS and logs in themselves. Never ask for credentials, "
        "never store them, never replay a saved session.",
        "The agent stays present for the whole pull. If they step away, it stops.",
        "Run the search the agent would have run: their subject property, their radius, "
        "their date window, their property type.",
        "Export or capture the result set once. No pagination loops beyond what a person "
        "would click, no background refresh, no schedule.",
        "Hand the result straight to `comp_source.py load --tier export`. The normalizer "
        "is the same either way, so the audit trail is the same either way.",
        "Record in the run directory: who pulled it, when, and which MLS. That line is "
        "what makes the comp set reproducible six months from now.",
    ], start=1):
        print(f"  {i}. {step}")
    print("\nIf any step cannot be satisfied, use the export tier. It is not a downgrade.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("load")
    l.add_argument("--tier", default="export", choices=["export", "browser", "reso"])
    l.add_argument("--in", dest="inp", required=True)
    l.add_argument("--out", required=True)
    l.add_argument("--map", help="JSON object mapping your headers to the normalized names")
    l.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    l.set_defaults(fn=cmd_load)
    t = sub.add_parser("tiers"); t.set_defaults(fn=cmd_tiers)
    b = sub.add_parser("browser-plan"); b.add_argument("--market"); b.set_defaults(fn=cmd_browser_plan)
    args = ap.parse_args()
    sys.exit(args.fn(args))

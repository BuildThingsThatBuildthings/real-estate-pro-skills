#!/usr/bin/env python3
"""
Adjust the comps and compute the supported range. All arithmetic, no narrative.

  comps.py adjust --comps comps.json --subject subject.json --out adjusted.json
  comps.py adjust ... --rates rates.json --as-of 2026-08-29
  comps.py rates                                  the default adjustment rates, and where they come from

The model never does this math and never produces a number. It writes narrative
over what this script computed, and `brief_gate.py` refuses any figure in the
brief that does not appear here.

Every adjustment is recorded as a ledger line -- feature, subject value, comp
value, delta, rate, dollars -- so a seller can follow it on paper and an agent
can defend it out loud. An adjustment nobody can explain is worse than none.
"""
import argparse, datetime as dt, json, statistics, sys

# Defaults are a starting point, not a market. Local rates belong in rates.json:
# paired-sales analysis in the agent's own market beats any national figure, and
# the brief says which set was used.
DEFAULT_RATES = {
    "sqft": 85.0,               # $ per square foot of finished living area difference
    "beds": 5000.0,             # $ per bedroom
    "baths": 7500.0,            # $ per full bath equivalent
    "garage": 6000.0,           # $ per garage space
    "lot_sqft": 2.0,            # $ per square foot of lot difference
    "year_built": 600.0,        # $ per year of effective age difference
    "condition": 15000.0,       # $ per condition grade step
    "market_trend_pct_per_month": 0.0,   # time adjustment; 0 until measured locally
    "max_net_adjustment_pct": 25.0,      # a comp adjusted past this is not comparable
    "min_comps": 3,
    "present_round_to": 1000.0,   # a brief quotes round numbers; they get COMPUTED, not rounded in prose
}
CONDITION_SCALE = {"poor": 0, "fair": 1, "average": 2, "good": 3, "excellent": 4}


def cond_grade(v):
    return CONDITION_SCALE.get((v or "").strip().lower())


def months_between(a, b):
    return (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 30.44


def line(feature, subj, comp, rate, dollars, how):
    return {"feature": feature, "subject": subj, "comp": comp,
            "rate": rate, "dollars": round(dollars, 2), "how": how}


def adjust_one(c, s, rates, as_of):
    """Adjust the comp TOWARD the subject. Positive dollars mean the comp was
    inferior and its price is adjusted up to stand in for the subject."""
    ledger = []
    price = c.get("close_price")
    if price is None:
        return None, ["no close_price"]
    problems = []

    for feat in ("sqft", "beds", "baths", "garage", "lot_sqft"):
        sv, cv = s.get(feat), c.get(feat)
        if sv is None or cv is None:
            if feat == "sqft":
                problems.append("missing sqft")
            continue
        diff = sv - cv
        if diff:
            d = diff * rates[feat]
            ledger.append(line(feat, sv, cv, rates[feat], d, f"({sv} - {cv}) x {rates[feat]}"))

    sy, cy = s.get("year_built"), c.get("year_built")
    if sy and cy and sy != cy:
        d = (sy - cy) * rates["year_built"]
        ledger.append(line("year_built", sy, cy, rates["year_built"], d,
                           f"({sy} - {cy}) x {rates['year_built']}"))

    sg, cg = cond_grade(s.get("condition")), cond_grade(c.get("condition"))
    if sg is not None and cg is not None and sg != cg:
        d = (sg - cg) * rates["condition"]
        ledger.append(line("condition", s.get("condition"), c.get("condition"),
                           rates["condition"], d, f"({sg} - {cg} grade steps) x {rates['condition']}"))

    trend = rates.get("market_trend_pct_per_month", 0.0)
    cd = c.get("close_date")
    if trend and cd:
        try:
            months = months_between(dt.date.fromisoformat(cd), as_of)
        except ValueError:
            months = 0
        if months:
            d = price * (trend / 100.0) * months
            ledger.append(line("time", as_of.isoformat(), cd, trend, d,
                               f"{price} x {trend}%/mo x {round(months, 2)} mo"))

    gross = sum(abs(l["dollars"]) for l in ledger)
    net = sum(l["dollars"] for l in ledger)
    adjusted = price + net
    net_pct = (abs(net) / price * 100.0) if price else 0.0
    if net_pct > rates["max_net_adjustment_pct"]:
        problems.append(f"net adjustment {net_pct:.1f}% exceeds the {rates['max_net_adjustment_pct']}% ceiling")

    return {
        "comp_id": c["comp_id"],
        "address": c.get("address"),
        "close_price": price,
        "close_date": cd,
        "ledger": ledger,
        "gross_adjustment": round(gross, 2),
        "net_adjustment": round(net, 2),
        "net_adjustment_pct": round(net_pct, 2),
        "adjusted_value": round(adjusted, 2),
        "problems": problems,
    }, problems


def cmd_adjust(a):
    comps_doc = json.load(open(a.comps, encoding="utf-8"))
    subject = json.load(open(a.subject, encoding="utf-8"))
    rates = dict(DEFAULT_RATES)
    rates_source = "built-in defaults"
    if a.rates:
        rates.update(json.load(open(a.rates, encoding="utf-8")))
        rates_source = a.rates
    as_of = dt.date.fromisoformat(a.as_of) if a.as_of else dt.date.today()

    included, excluded = [], []
    for c in comps_doc["comps"]:
        if c.get("exclude"):
            excluded.append({"comp_id": c["comp_id"], "address": c.get("address"),
                             "close_price": c.get("close_price"),
                             "close_date": c.get("close_date"),
                             "reason": (c.get("exclude_reason") or "").strip()})
            continue
        row, problems = adjust_one(c, subject, rates, as_of)
        if row is None:
            excluded.append({"comp_id": c["comp_id"], "address": c.get("address"),
                             "reason": "; ".join(problems)})
            continue
        if problems:
            # Over-adjusted comps are reported, not silently dropped. An agent who
            # sees why a comp fell out can defend the ones that stayed.
            excluded.append({"comp_id": c["comp_id"], "address": c.get("address"),
                             "reason": "; ".join(problems), "computed": row})
            continue
        included.append(row)

    vals = sorted(r["adjusted_value"] for r in included)
    doc = {
        "schema": "listing-price-brief/adjusted/v1",
        "as_of": as_of.isoformat(),
        "rates_source": rates_source,
        "rates": rates,
        "subject": subject,
        "included": included,
        "excluded": excluded,
        "min_comps": rates["min_comps"],
        "enough_comps": len(included) >= rates["min_comps"],
    }
    if vals:
        doc["range"] = {
            "low": round(vals[0], 2),
            "high": round(vals[-1], 2),
            "median": round(statistics.median(vals), 2),
            # The supported range is the middle of the adjusted values, not the
            # extremes. Quoting min-to-max hands the seller the top number and
            # then argues with it later.
            "supported_low": round(vals[0] if len(vals) < 4 else statistics.quantiles(vals, n=4)[0], 2),
            "supported_high": round(vals[-1] if len(vals) < 4 else statistics.quantiles(vals, n=4)[2], 2),
            "n": len(vals),
        }
        # A seller-facing brief quotes round numbers. If prose rounds them, the
        # rounded figure is a number the model produced and the gate cannot
        # trace. So round here, in Python, and let the brief cite these.
        inc = float(rates.get("present_round_to", 1000.0)) or 1.0
        doc["range"]["supported_low_rounded"] = round(doc["range"]["supported_low"] / inc) * inc
        doc["range"]["supported_high_rounded"] = round(doc["range"]["supported_high"] / inc) * inc
        doc["range"]["median_rounded"] = round(doc["range"]["median"] / inc) * inc
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"rates: {rates_source}")
    print(f"included {len(included)}, excluded {len(excluded)}, minimum {rates['min_comps']}")
    for r in included:
        print(f"  {r['comp_id']}  close {r['close_price']:>12,.0f}  net {r['net_adjustment']:>+11,.0f}"
              f"  ({r['net_adjustment_pct']:>4.1f}%)  adjusted {r['adjusted_value']:>12,.0f}")
    for e in excluded:
        print(f"  {e['comp_id']}  EXCLUDED — {e['reason'] or 'NO REASON GIVEN'}")
    if doc.get("range"):
        rg = doc["range"]
        print(f"\n  supported range  {rg['supported_low']:,.0f} to {rg['supported_high']:,.0f}"
              f"   (median {rg['median']:,.0f}, n={rg['n']})")
    if not doc["enough_comps"]:
        print(f"\n  NOT ENOUGH COMPS: {len(included)} < {rates['min_comps']}. No range may be published.")
    print(f"-> {a.out}")
    return 0


def cmd_rates(_a):
    print("default adjustment rates\n")
    for k, v in DEFAULT_RATES.items():
        print(f"  {k:<32} {v}")
    print("\nThese are a starting point, not a market. Replace them with paired-sales")
    print("analysis from the agent's own market via --rates rates.json. The brief")
    print("records which set was used, because the range is only as defensible as the rates.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("adjust")
    j.add_argument("--comps", required=True); j.add_argument("--subject", required=True)
    j.add_argument("--out", required=True); j.add_argument("--rates"); j.add_argument("--as-of")
    j.set_defaults(fn=cmd_adjust)
    r = sub.add_parser("rates"); r.set_defaults(fn=cmd_rates)
    args = ap.parse_args()
    sys.exit(args.fn(args))

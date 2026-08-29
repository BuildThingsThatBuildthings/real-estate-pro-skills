#!/usr/bin/env python3
"""
Seller net proceeds at three prices. Arithmetic only.

  net_sheet.py build --adjusted adjusted.json --costs costs.json --out net_sheet.json
  net_sheet.py build ... --prices 505000,515000,525000
  net_sheet.py example-costs > costs.json

Most sellers interview one agent, so the appointment is a contest against waiting
rather than against a competitor. What moves it is a supported range, a written
net-proceeds number, and a dated plan. The middle one is the one most agents skip,
because it takes arithmetic nobody wants to do by hand at a kitchen table.

The model never computes any of this. Every line is a rate or a dollar amount from
costs.json applied to a price, and every line shows its own formula.
"""
import argparse, json, sys

EXAMPLE_COSTS = {
    "_comment": "Rates and amounts for one market and one brokerage. Nothing here is a default "
                "anywhere else. Confirm every line with the agent and their title company.",
    "listing_side_commission_pct": 3.0,
    "buyer_side_commission_pct": 3.0,
    "_commission_note": "Post-settlement, buyer-side compensation is negotiated and disclosed "
                        "separately and is not advertised on the MLS. Set it to what THIS seller "
                        "has agreed to offer, or 0 if nothing is offered.",
    "title_and_settlement": 1200.0,
    "owners_title_policy_pct": 0.55,
    "transfer_tax_pct": 0.37,
    "recording_and_misc": 150.0,
    "home_warranty": 0.0,
    "seller_concessions_pct": 0.0,
    "repairs_allowance": 0.0,
    "prorated_taxes": 0.0,
    "hoa_transfer": 0.0,
    "mortgage_payoff": 0.0,
}
PCT_LINES = [
    ("listing_side_commission_pct", "listing side commission"),
    ("buyer_side_commission_pct", "buyer side compensation offered"),
    ("owners_title_policy_pct", "owner's title policy"),
    ("transfer_tax_pct", "transfer tax"),
    ("seller_concessions_pct", "seller concessions"),
]
FLAT_LINES = [
    ("title_and_settlement", "title and settlement fees"),
    ("recording_and_misc", "recording and misc"),
    ("home_warranty", "home warranty"),
    ("repairs_allowance", "repairs allowance"),
    ("prorated_taxes", "prorated taxes"),
    ("hoa_transfer", "HOA transfer"),
]


def scenario(price, costs, round_to=1000.0):
    lines, total = [], 0.0
    for key, label in PCT_LINES:
        pct = float(costs.get(key, 0) or 0)
        if not pct:
            continue
        amt = price * pct / 100.0
        lines.append({"label": label, "basis": f"{pct}% of {price:,.0f}", "amount": round(amt, 2)})
        total += amt
    for key, label in FLAT_LINES:
        amt = float(costs.get(key, 0) or 0)
        if not amt:
            continue
        lines.append({"label": label, "basis": "flat", "amount": round(amt, 2)})
        total += amt
    payoff = float(costs.get("mortgage_payoff", 0) or 0)
    net_before = price - total
    return {
        "price": round(price, 2),
        "lines": lines,
        "total_costs": round(total, 2),
        "net_before_payoff": round(net_before, 2),
        "mortgage_payoff": round(payoff, 2),
        "estimated_net_to_seller": round(net_before - payoff, 2),
        # Computed, not rounded in prose -- see comps.py for why.
        "price_rounded": round(price / round_to) * round_to,
        "total_costs_rounded": round(total / round_to) * round_to,
        "estimated_net_to_seller_rounded": round((net_before - payoff) / round_to) * round_to,
    }


def cmd_build(a):
    adj = json.load(open(a.adjusted, encoding="utf-8"))
    costs = json.load(open(a.costs, encoding="utf-8"))
    if not adj.get("enough_comps"):
        raise SystemExit(
            f"refusing to build a net sheet: only {len(adj.get('included', []))} usable comp(s), "
            f"minimum {adj.get('min_comps')}.\n"
            f"  A net sheet on an unsupported price is a number the seller will hold you to.")
    rg = adj.get("range") or {}
    if a.prices:
        prices = [float(p.strip().replace(",", "").replace("$", "")) for p in a.prices.split(",")]
    else:
        prices = [rg["supported_low"], rg["median"], rg["supported_high"]]
    doc = {
        "schema": "listing-price-brief/net-sheet/v1",
        "as_of": adj.get("as_of"),
        "costs_source": a.costs,
        "supported_range": {"low": rg.get("supported_low"), "high": rg.get("supported_high")},
        "scenarios": [scenario(p, costs, float(costs.get("present_round_to", 1000.0)) or 1.0)
                      for p in prices],
    }
    outside = [p for p in prices if rg and not (rg["low"] <= p <= rg["high"])]
    if outside:
        doc["outside_comp_range"] = outside
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    for s in doc["scenarios"]:
        print(f"  {s['price']:>12,.0f}   costs {s['total_costs']:>11,.0f}   "
              f"net to seller {s['estimated_net_to_seller']:>12,.0f}")
    if outside:
        print(f"\n  NOTE: {[f'{p:,.0f}' for p in outside]} fall outside the adjusted comp range "
              f"{rg.get('low'):,.0f}-{rg.get('high'):,.0f}. The brief must say so plainly.")
    print(f"-> {a.out}")
    print("estimates only. the title company's figures govern at closing.")
    return 0


def cmd_example(_a):
    print(json.dumps(EXAMPLE_COSTS, indent=2))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--adjusted", required=True); b.add_argument("--costs", required=True)
    b.add_argument("--out", required=True); b.add_argument("--prices")
    b.set_defaults(fn=cmd_build)
    e = sub.add_parser("example-costs"); e.set_defaults(fn=cmd_example)
    args = ap.parse_args()
    sys.exit(args.fn(args))

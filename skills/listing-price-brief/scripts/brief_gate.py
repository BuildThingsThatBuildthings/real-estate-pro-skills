#!/usr/bin/env python3
"""
The gate. No pricing brief reaches a seller until this passes.

  brief_gate.py check --adjusted adjusted.json --net-sheet net_sheet.json --brief brief.md
  brief_gate.py check ... --client acme-realty
  brief_gate.py gates

Exit code 1 if anything fails.

The failure being defended against
----------------------------------
Pricing is the task agents most want help with and trust AI with least, and the
reason is specific: a model that writes a confident price narrative with numbers
it produced itself is worse than no help at all. The seller keeps the number, the
agent owns it, and nothing behind it can be re-derived.

So GROUNDED is the whole point. Every money figure in the brief must appear in
the computed JSON, or be explicitly marked. The model writes prose. Python owns
arithmetic.
"""
import argparse, json, os, re, sys

_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.realpath(os.path.join(_HERE, "..", "..", "compliance-gate", "scripts")))
try:
    import fair_housing as _compliance
except Exception:  # noqa: BLE001
    _compliance = None

MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\s?(?:k|m|million|thousand)?\b", re.I)
MARK = re.compile(r"\[(?:comp:[A-Za-z0-9]+|computed|verified|estimate)\]", re.I)

# A pricing brief is a marketing document. Calling it a valuation invites a
# regulator to read it as one, in a field where "appraisal" is a licensed act.
APPRAISAL = [
    (r"\bappraised? (?:value|at)\b", "'appraised value' is a licensed act, not this document"),
    (r"\bthis appraisal\b|\bour appraisal\b", "never call this an appraisal"),
    (r"\bcertified (?:value|valuation)\b", "implies a licensed valuation"),
    (r"\bmarket value is\b", "states a valuation as fact; give a supported range instead"),
    (r"\bthe (?:home|property|house) is worth\b", "states a valuation as fact"),
    (r"\bguarantee(d|s)?\b", "no guarantees of any kind"),
    (r"\bwill sell for\b|\bwill appraise\b", "no outcome promises"),
]
DISCLOSURE = re.compile(
    r"not an appraisal|not a valuation|marketing (?:pricing )?(?:brief|estimate)", re.I)


def norm(raw):
    n = re.sub(r"[^\d.]", "", raw)
    if not n:
        return None
    v = float(n)
    t = raw.lower()
    if "m" in t or "million" in t:
        v *= 1_000_000
    elif "k" in t or "thousand" in t:
        v *= 1_000
    return v


class Result:
    def __init__(self):
        self.failures, self.notes = [], []

    def fail(self, g, d):
        self.failures.append((g, d))

    def note(self, t):
        self.notes.append(t)


def computed_values(adj, net):
    """Every number Python produced. Nothing else may appear in the brief."""
    vals = set()

    def add(x):
        # Both the exact value and its whole-dollar form. A seller-facing brief
        # writes "$522,981" for 522981.18; that is the same number to the dollar,
        # not a figure the model produced.
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            vals.add(round(float(x), 2))
            vals.add(float(int(round(float(x)))))
    for r in adj.get("included", []):
        for k in ("close_price", "adjusted_value", "net_adjustment", "gross_adjustment"):
            add(r.get(k))
        for l in r.get("ledger", []):
            add(l.get("dollars")); add(l.get("rate"))
    for e in adj.get("excluded", []):
        # The exclusions section names these sales on purpose, so their prices
        # have to be traceable.
        add(e.get("close_price"))
        c = e.get("computed") or {}
        for k in ("close_price", "adjusted_value", "net_adjustment"):
            add(c.get(k))
    for v in (adj.get("range") or {}).values():
        add(v)
    for k, v in (adj.get("rates") or {}).items():
        add(v)
    for s in (net or {}).get("scenarios", []):
        for k in ("price", "total_costs", "net_before_payoff", "mortgage_payoff",
                  "estimated_net_to_seller", "price_rounded", "total_costs_rounded",
                  "estimated_net_to_seller_rounded"):
            add(s.get(k))
        for l in s.get("lines", []):
            add(l.get("amount"))
    return vals


def gate_comp_floor(adj, r):
    if not adj.get("enough_comps"):
        r.fail("COMP_FLOOR", f"{len(adj.get('included', []))} usable comp(s), minimum "
                             f"{adj.get('min_comps')} — no range may be published")


def gate_adjusted(adj, r):
    for row in adj.get("included", []):
        if not row.get("ledger"):
            r.note(f"{row['comp_id']} needed no adjustment; that is legitimate but rare — confirm it")
        for l in row.get("ledger", []):
            if l.get("dollars") is None or not l.get("how"):
                r.fail("ADJUSTED", f"{row['comp_id']} has a ledger line with no arithmetic: {l}")
        # Re-derive the total. A ledger that does not sum to its own net is the
        # one defect a reader will never catch and a seller's accountant will.
        s = round(sum(l["dollars"] for l in row.get("ledger", [])), 2)
        if abs(s - float(row.get("net_adjustment", 0))) > 0.01:
            r.fail("ADJUSTED", f"{row['comp_id']} ledger sums to {s} but net_adjustment is "
                               f"{row.get('net_adjustment')}")
        if abs(round(float(row["close_price"]) + s, 2) - float(row["adjusted_value"])) > 0.01:
            r.fail("ADJUSTED", f"{row['comp_id']} close_price + net does not equal adjusted_value")


def gate_exclusions(adj, r):
    for e in adj.get("excluded", []):
        if not (e.get("reason") or "").strip():
            r.fail("EXCLUSIONS", f"{e['comp_id']} was excluded with no reason — an unexplained "
                                 f"exclusion is indistinguishable from cherry-picking")


def gate_net_sheet(net, r):
    if not net:
        return
    for s in net.get("scenarios", []):
        total = round(sum(l["amount"] for l in s.get("lines", [])), 2)
        if abs(total - float(s.get("total_costs", 0))) > 0.01:
            r.fail("NET_SHEET", f"scenario {s['price']}: lines sum to {total}, total_costs says "
                                f"{s.get('total_costs')}")
        expect = round(float(s["price"]) - float(s["total_costs"]) - float(s.get("mortgage_payoff", 0)), 2)
        if abs(expect - float(s["estimated_net_to_seller"])) > 0.01:
            r.fail("NET_SHEET", f"scenario {s['price']}: net to seller does not re-derive")
    if net.get("outside_comp_range"):
        r.note(f"scenario price(s) {net['outside_comp_range']} sit outside the adjusted comp range — "
               f"the brief must say so plainly")


def gate_grounded(adj, net, text, r):
    vals = computed_values(adj, net)
    for i, block in enumerate(re.split(r"\n\s*\n", text), start=1):
        figs = MONEY.findall(block)
        if not figs:
            continue
        marked = bool(MARK.search(block))
        for raw in figs:
            v = norm(raw)
            if v is None:
                continue
            if round(v, 2) in vals or float(int(round(v))) in vals:
                continue
            if marked:
                r.note(f"para {i}: {raw!r} is marked but not computed — a human confirms it")
            else:
                r.fail("GROUNDED", f"para {i}: {raw!r} appears in no computed output — "
                                   f"compute it, or mark the paragraph [computed]/[verified]/[estimate]")


def gate_not_appraisal(text, r):
    low = text.lower()
    for pat, why in APPRAISAL:
        m = re.search(pat, low)
        if m:
            r.fail("NOT_APPRAISAL", f"{m.group(0)!r} — {why}")
    if not DISCLOSURE.search(text):
        r.fail("NOT_APPRAISAL", "no line stating this is not an appraisal or valuation")


def gate_compliance(text, client, r, lenient):
    if _compliance is None:
        r.fail("COMPLIANCE", "compliance-gate/scripts/fair_housing.py could not be imported")
        return
    try:
        _card, extra = _compliance.load_card(client)
    except Exception:  # noqa: BLE001
        extra = []
    for kind, hit, why in _compliance.check(text, extra, strict_source=not lenient):
        r.fail("COMPLIANCE", f"[{kind}] {hit!r} — {why}")


def cmd_check(a):
    adj = json.load(open(a.adjusted, encoding="utf-8"))
    net = json.load(open(a.net_sheet, encoding="utf-8")) if a.net_sheet else None
    text = open(a.brief, encoding="utf-8", errors="ignore").read()
    r = Result()

    gate_comp_floor(adj, r)
    gate_adjusted(adj, r)
    gate_exclusions(adj, r)
    gate_net_sheet(net, r)
    gate_grounded(adj, net, text, r)
    gate_not_appraisal(text, r)
    gate_compliance(text, a.client, r, a.lenient)

    rg = adj.get("range") or {}
    print(f"comps:  {len(adj.get('included', []))} included, {len(adj.get('excluded', []))} excluded")
    if rg:
        print(f"range:  {rg.get('supported_low'):,.0f} to {rg.get('supported_high'):,.0f} "
              f"(median {rg.get('median'):,.0f})")
    print(f"rates:  {adj.get('rates_source')}")
    for n in r.notes:
        print(f"  note   {n}")
    if not r.failures:
        print("\n  PASS  all gates")
        return 0
    by = {}
    for g, d in r.failures:
        by.setdefault(g, []).append(d)
    print()
    for g in sorted(by):
        print(f"  FAIL  {g}")
        for d in by[g]:
            print(f"          {d}")
    print(f"\n{len(r.failures)} failure(s) across {len(by)} gate(s). Nothing goes to the seller.")
    return 1


def cmd_gates(_a):
    for g, why in [
        ("COMP_FLOOR", "a range built on fewer usable comps than the configured minimum"),
        ("ADJUSTED", "a ledger line with no arithmetic, or a ledger that does not sum to its own net"),
        ("EXCLUSIONS", "a comp dropped with no reason — indistinguishable from cherry-picking"),
        ("NET_SHEET", "a net sheet whose lines do not re-derive its totals"),
        ("GROUNDED", "any money figure in the brief that appears in no computed output"),
        ("NOT_APPRAISAL", "appraisal or valuation language, and a brief with no disclosure line"),
        ("COMPLIANCE", "the Fair Housing baseline, imported from content-foundry"),
    ]:
        print(f"  {g:<14} refuses {why}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--adjusted", required=True); c.add_argument("--net-sheet")
    c.add_argument("--brief", required=True); c.add_argument("--client")
    c.add_argument("--lenient", action="store_true")
    c.set_defaults(fn=cmd_check)
    g = sub.add_parser("gates"); g.set_defaults(fn=cmd_gates)
    args = ap.parse_args()
    sys.exit(args.fn(args))

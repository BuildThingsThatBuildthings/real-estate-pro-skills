#!/usr/bin/env python3
"""
The gate. No drafted touch leaves this skill until it passes.

  touch_gate.py check --drafts drafts.json --reasons reasons.json --contacts contacts.csv
  touch_gate.py check ... --client acme-realty
  touch_gate.py gates                        # what each gate refuses, and why

Exit code 1 if anything fails.

What it is defending against
----------------------------
A follow-up system fails in two directions and only one of them is obvious.

The obvious one is spam: touches with no reason behind them, sent because the
calendar said Tuesday. That is what REASON refuses.

The one that ends a career is inference. A drafting model handed a contact
database will reach for "now that the kids are older" or "great neighborhood for
a family" because that is how marketing copy sounds. Written by a licensee, to a
consumer, about housing, that is a Fair Housing problem. NO_INFERENCE and
COMPLIANCE refuse it, and notice.py refuses to even read the columns that would
make it easy.
"""
import argparse, csv, json, os, re, sys

_HERE = os.path.dirname(os.path.realpath(__file__))
# Reuse, don't rebuild: one copy of the Fair Housing baseline in the bundle.
sys.path.insert(0, os.path.realpath(os.path.join(_HERE, "..", "..", "content-foundry", "scripts")))
try:
    import compliance as _compliance
except Exception:  # noqa: BLE001 — surfaced as a check, not a crash
    _compliance = None

ASKS = {"none", "referral", "testimonial", "review"}
EARNED_REQUIRED = {"referral", "testimonial", "review"}

# Inference about who someone is, or what kind of person a place suits. Every one
# of these reads as ordinary warm copy, which is exactly why it needs a machine
# to catch it.
INFERENCE = [
    (r"\bnow that (?:the )?(?:kids|children|they)\b", "infers family status"),
    (r"\b(?:your|the) (?:kids|children|grandkids)\b", "infers familial status"),
    (r"\bempty[- ]nest(?:er|ing)?\b", "infers familial status"),
    (r"\bgrowing family\b|\bstarter family\b|\bfamily[- ]friendly\b", "familial status targeting"),
    (r"\bgreat (?:for|place for) (?:a )?famil(?:y|ies)\b", "familial status targeting"),
    (r"\bperfect (?:for|neighborhood for|area for)\b", "implies an ideal buyer"),
    (r"\bnow that you(?:'re| are) retir(?:ed|ing)\b", "infers age"),
    (r"\bat your age\b|\bfor someone your age\b", "infers age"),
    (r"\byour church\b|\byour congregation\b|\byour parish\b", "infers religion"),
    (r"\bsince you(?:'re| are) (?:married|divorced|single|expecting)\b", "infers marital or familial status"),
    (r"\b(?:safe|safer|safest) (?:neighborhood|area|part of town)\b", "safety claims are a Fair Housing proxy"),
    (r"\b(?:good|great|top[- ]rated|better) schools?\b", "school quality claims are a proxy"),
    (r"\bpeople like you\b|\bsomeone in your situation\b", "categorizes the recipient"),
    (r"\bup[- ]and[- ]coming\b|\btransitional neighborhood\b", "coded language about an area"),
    (r"\bthe right kind of\b", "categorizes people or areas"),
]

# Figures that need a source, unless the draft marks them.
FIGURE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\b|\b\d+(?:\.\d+)?\s?(?:%|percent\b)", re.I)
SOURCED = re.compile(r"\[(?:source:[^\]]+|verified|VERIFY)\]", re.I)


class Result:
    def __init__(self):
        self.failures, self.notes = [], []

    def fail(self, gate, detail):
        self.failures.append((gate, detail))

    def note(self, t):
        self.notes.append(t)


def load_contacts(path):
    out = {}
    if not path:
        return out
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cid = (r.get("id") or "").strip()
            if cid:
                out[cid] = r
    return out


def truthy(v):
    return (v or "").strip().lower() in ("y", "yes", "true", "1")


def gate_reason(drafts, reasons, r):
    ids = {x["id"] for x in reasons["reasons"]}
    for d in drafts["drafts"]:
        rid = (d.get("reason_id") or "").strip()
        if not rid:
            r.fail("REASON", f"{d['id']} has no reason_id — a touch with no computed reason is spam")
        elif rid not in ids:
            r.fail("REASON", f"{d['id']} cites {rid}, which notice.py did not produce")


def gate_consent(drafts, contacts, r):
    for d in drafts["drafts"]:
        cid = (d.get("contact_id") or "").strip()
        c = contacts.get(cid)
        if c is None:
            if contacts:
                r.fail("CONSENT", f"{d['id']} targets {cid}, who is not in contacts.csv")
            continue
        if truthy(c.get("opted_out")):
            r.fail("CONSENT", f"{d['id']} targets {cid}, who has opted out")
        ch = (d.get("channel") or "").strip().lower()
        allowed = [x.strip().lower() for x in (c.get("channels") or "").split("|") if x.strip()]
        if allowed and ch and ch not in allowed:
            r.fail("CONSENT", f"{d['id']} uses {ch!r}, not among {cid}'s permitted channels {allowed}")


def gate_earned(drafts, r):
    for d in drafts["drafts"]:
        ask = (d.get("asks") or "none").strip().lower()
        if ask not in ASKS:
            r.fail("EARNED", f"{d['id']} has asks={ask!r}; valid: {', '.join(sorted(ASKS))}")
            continue
        if ask in EARNED_REQUIRED and not (d.get("earned_moment") or "").strip():
            r.fail("EARNED", f"{d['id']} asks for a {ask} with no earned_moment — "
                             f"the calendar alone is not permission")


def gate_no_inference(drafts, r):
    for d in drafts["drafts"]:
        low = (d.get("body") or "").lower()
        for pat, why in INFERENCE:
            m = re.search(pat, low)
            if m:
                r.fail("NO_INFERENCE", f"{d['id']}: {m.group(0)!r} — {why}")


def gate_facts(drafts, r):
    for d in drafts["drafts"]:
        body = d.get("body") or ""
        figs = FIGURE.findall(body)
        if figs and not SOURCED.search(body):
            r.fail("FACTS", f"{d['id']}: figure(s) {figs} with no [source: ...], [verified] or [VERIFY] marker")


def gate_no_send(drafts, r):
    for d in drafts["drafts"]:
        st = (d.get("status") or "").strip().lower()
        if st != "draft":
            r.fail("NO_SEND", f"{d['id']} has status {st!r} — this skill only ever produces drafts")


def gate_compliance(drafts, client, r, lenient):
    if _compliance is None:
        r.fail("COMPLIANCE", "content-foundry/scripts/compliance.py could not be imported; "
                             "the Fair Housing baseline did not run")
        return
    try:
        _card, extra = _compliance.load_card(client)
    except Exception:  # noqa: BLE001
        extra = []
    for d in drafts["drafts"]:
        for kind, hit, why in _compliance.check(d.get("body") or "", extra, strict_source=not lenient):
            r.fail("COMPLIANCE", f"{d['id']}: [{kind}] {hit!r} — {why}")


def cmd_check(a):
    drafts = json.load(open(a.drafts, encoding="utf-8"))
    reasons = json.load(open(a.reasons, encoding="utf-8"))
    contacts = load_contacts(a.contacts)
    r = Result()

    gate_reason(drafts, reasons, r)
    gate_consent(drafts, contacts, r)
    gate_earned(drafts, r)
    gate_no_inference(drafts, r)
    gate_facts(drafts, r)
    gate_no_send(drafts, r)
    gate_compliance(drafts, a.client, r, a.lenient)

    print(f"drafts:  {len(drafts['drafts'])}")
    print(f"reasons: {reasons.get('reason_count', len(reasons['reasons']))} as of {reasons.get('as_of')}")
    covered = {d.get("reason_id") for d in drafts["drafts"]}
    unused = [x["id"] for x in reasons["reasons"] if x["id"] not in covered]
    if unused:
        r.note(f"{len(unused)} computed reason(s) have no draft — fine, but they stay on the board")
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
    print(f"\n{len(r.failures)} failure(s) across {len(by)} gate(s). Nothing is approved.")
    return 1


def cmd_gates(_a):
    for g, why in [
        ("REASON", "a draft with no computed reason, or one notice.py never produced"),
        ("CONSENT", "an opted-out contact, or a channel they did not permit"),
        ("EARNED", "a referral, review or testimonial ask with no earned moment behind it"),
        ("NO_INFERENCE", "language inferring family, age, religion, or what kind of person a place suits"),
        ("FACTS", "a price or percentage with no source marker"),
        ("NO_SEND", "any draft not in status 'draft'; this skill never sends"),
        ("COMPLIANCE", "the Fair Housing baseline, imported from content-foundry"),
    ]:
        print(f"  {g:<14} refuses {why}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--drafts", required=True)
    c.add_argument("--reasons", required=True)
    c.add_argument("--contacts")
    c.add_argument("--client")
    c.add_argument("--lenient", action="store_true")
    c.set_defaults(fn=cmd_check)
    g = sub.add_parser("gates"); g.set_defaults(fn=cmd_gates)
    args = ap.parse_args()
    sys.exit(args.fn(args))

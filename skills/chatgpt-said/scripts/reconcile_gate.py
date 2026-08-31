#!/usr/bin/env python3
"""
The gate. Nothing reaches a client until this passes.

  reconcile_gate.py check --claims claims.json --reconciliation reconciliation.md
  reconcile_gate.py check ... --client acme-realty      # adds their GUARDRAILS card
  reconcile_gate.py classes                             # the taxonomy, with why

Exit code 1 if anything fails. This is a gate, not advice.

What it is actually defending against
-------------------------------------
The failure this skill exists to prevent is an agent walking into a listing
appointment with a rebuttal that is itself unsourced. That loses harder than
saying nothing, because now there are two confident documents and only one of
them has the agent's name on it.

So the gate is not a style check. It refuses to pass a reconciliation that
drops a claim, asserts a number nobody can trace, or argues with the client.
"""
import argparse, json, os, re, sys

_HERE = os.path.dirname(os.path.realpath(__file__))
# Reuse, don't rebuild: the Fair Housing baseline lives in compliance-gate —
# the ONE copy of those rules in the bundle.
sys.path.insert(0, os.path.realpath(os.path.join(_HERE, "..", "..", "compliance-gate", "scripts")))
try:
    import fair_housing as _compliance
except Exception:  # noqa: BLE001 — reported as a check, not a crash
    _compliance = None

CLASSES = {
    "verified":     "checked against a record the agent holds; the model got it right",
    "contradicted": "checked, and the local record differs; needs a source and the correct value",
    "unknowable":   "the model could not have known this — condition, motivation, off-market context",
    "stale":        "true once, not now — training cutoff, portal lag, market movement",
    "out_of_scope": "legal, tax, appraisal or lending advice; refer, do not answer",
}
NEEDS_SOURCE = {"verified", "contradicted"}
NEEDS_CORRECTION = {"contradicted"}

CITATION = re.compile(r"\[(C-[0-9a-f]{6}[a-z]?|verified|computed)\]")
MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\s?(?:k|m|million|thousand)?\b", re.I)
PERCENT = re.compile(r"\b\d+(?:\.\d+)?\s?(?:%|percent\b)", re.I)

# Arguing with the client. Every one of these has lost somebody a listing.
ADVERSARIAL = [
    (r"\byou(?:'re| are) (?:wrong|mistaken|misinformed)\b", "never tell the client they are wrong"),
    (r"\bthat(?:'s| is) (?:wrong|incorrect|false)\b", "corrects the client head-on"),
    (r"\bactually,\s", "'actually' is the tell that a correction is coming"),
    (r"\b(?:chatgpt|claude|gemini|the ai|ai)\s+(?:is|was|got it)\s+wrong\b", "agent versus algorithm is a losing frame"),
    (r"\b(?:ai|chatgpt|these tools?)\s+(?:is|are)\s+(?:unreliable|inaccurate|not to be trusted)\b",
     "attacks the tool the client chose to use"),
    (r"\bdon'?t trust\b", "attacks the tool the client chose to use"),
    (r"\btrust me\b", "asks for belief instead of showing a source"),
    (r"\bi(?:'ve| have) been (?:doing this|in this business|selling)\b", "credentials are not evidence"),
    (r"\bwith all due respect\b", "reads as a prelude to an argument"),
    (r"\blet me correct\b", "framing the conversation as a correction"),
    (r"\bno offense\b", "reads as a prelude to an argument"),
    (r"\bunlike (?:ai|chatgpt|a chatbot)\b", "agent versus algorithm"),
]
REFERRAL_HEADING = re.compile(r"^#+\s*.*(not my lane|outside my lane|refer|another professional|other professionals)",
                              re.I | re.M)


def norm_money(raw):
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


def norm_percent(raw):
    n = re.sub(r"[^\d.]", "", raw)
    return float(n) if n else None


def claim_values(c):
    """Every number this claim can legitimately license in the reconciliation:
    what the chatbot said, plus what the agent corrected it to."""
    out = {(v["kind"], v["value"]) for v in c.get("values", [])}
    cv = c.get("correct_value")
    if cv not in (None, ""):
        for m in MONEY.finditer(str(cv)):
            v = norm_money(m.group(0))
            if v is not None:
                out.add(("price", v))
        for m in PERCENT.finditer(str(cv)):
            v = norm_percent(m.group(0))
            if v is not None:
                out.add(("percent", v))
        bare = re.fullmatch(r"\s*([\d,]+(?:\.\d+)?)\s*", str(cv))
        if bare:
            out.add(("price", float(bare.group(1).replace(",", ""))))
    return out


class Result:
    def __init__(self):
        self.failures = []
        self.notes = []

    def fail(self, gate, detail):
        self.failures.append((gate, detail))

    def note(self, text):
        self.notes.append(text)


def gate_classified(doc, r):
    for c in doc["claims"]:
        k = c.get("class")
        if k is None or k == "":
            r.fail("CLASSIFIED", f"{c['id']} has no class — {c['text'][:70]!r}")
        elif k not in CLASSES:
            r.fail("CLASSIFIED", f"{c['id']} has unknown class {k!r}; valid: {', '.join(sorted(CLASSES))}")


def gate_sourced(doc, r):
    for c in doc["claims"]:
        k = c.get("class")
        if k in NEEDS_SOURCE and not (c.get("source") or "").strip():
            r.fail("SOURCED", f"{c['id']} is {k} but carries no source")
        if k in NEEDS_CORRECTION and not str(c.get("correct_value") or "").strip():
            r.fail("SOURCED", f"{c['id']} is contradicted but gives no correct_value")


def gate_cited(doc, text, r):
    """Nothing may be silently dropped. The splitter found it; the agent has to
    have an answer for it, even if the answer is 'that one I can't speak to'."""
    cited = set(CITATION.findall(text))
    for c in doc["claims"]:
        if c["id"] not in cited:
            r.fail("CITED", f"{c['id']} never appears in the reconciliation — {c['text'][:70]!r}")


def paragraphs(text):
    """Blank-line separated blocks, with the line number each one starts on.

    The citation unit is the paragraph, not the line. Prose wraps, so a figure
    and the claim id that licenses it routinely land on different lines; a
    line-scoped rule would force citation-per-line and make the document
    unreadable, which is how gates end up disabled."""
    out, buf, start_line = [], [], 1
    for i, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            if not buf:
                start_line = i
            buf.append(line)
        elif buf:
            out.append((start_line, "\n".join(buf))); buf = []
    if buf:
        out.append((start_line, "\n".join(buf)))
    return out


def gate_grounded(doc, text, r, tol_pct):
    by_id = {c["id"]: c for c in doc["claims"]}
    loose = 0
    for lineno, block in paragraphs(text):
        figures = [("price", m.group(0)) for m in MONEY.finditer(block)]
        figures += [("percent", m.group(0)) for m in PERCENT.finditer(block)]
        if not figures:
            continue
        tokens = CITATION.findall(block)
        if not tokens:
            r.fail("GROUNDED", f"para at line {lineno}: figure(s) {[f[1] for f in figures]} with no citation — "
                               f"cite a claim id, or mark [verified] or [computed]")
            continue
        claim_tokens = [t for t in tokens if t.startswith("C-")]
        licensed = set()
        for t in claim_tokens:
            if t not in by_id:
                r.fail("GROUNDED", f"para at line {lineno}: cites {t}, which is not in claims.json")
                continue
            licensed |= claim_values(by_id[t])
        for kind, raw in figures:
            v = norm_money(raw) if kind == "price" else norm_percent(raw)
            if v is None:
                continue
            ok = any(k == kind and (a == v or (tol_pct and a and abs(a - v) <= abs(a) * tol_pct / 100.0))
                     for k, a in licensed)
            if not ok:
                # A figure the cited claims do not carry is only allowed when the
                # paragraph also says where it did come from.
                if any(t in ("verified", "computed") for t in tokens):
                    loose += 1
                else:
                    r.fail("GROUNDED", f"para at line {lineno}: {raw!r} is not carried by "
                                       f"{claim_tokens or 'any cited claim'} — cite the claim that has it, "
                                       f"or mark the paragraph [verified] or [computed]")
    if loose:
        r.note(f"{loose} figure(s) rest on [verified] or [computed] rather than a claim id — "
               f"a human confirms each against the record")


def gate_no_argument(text, r):
    low = text.lower()
    for pat, why in ADVERSARIAL:
        m = re.search(pat, low)
        if m:
            r.fail("NO_ARGUMENT", f"{m.group(0)!r} — {why}")


def gate_referrals(doc, text, r):
    oos = [c["id"] for c in doc["claims"] if c.get("class") == "out_of_scope"]
    if not oos:
        return
    if not REFERRAL_HEADING.search(text):
        r.fail("REFERRALS", f"{len(oos)} out_of_scope claim(s) ({', '.join(oos)}) but no referral section — "
                            f"add a heading such as '## Not my lane'")


def gate_compliance(text, client, r, lenient):
    if _compliance is None:
        r.fail("COMPLIANCE", "compliance-gate/scripts/fair_housing.py could not be imported; "
                             "the Fair Housing baseline did not run")
        return
    try:
        _card, extra = _compliance.load_card(client)
    except Exception:  # noqa: BLE001 — a missing client cache is not a gate failure
        extra = []
    for kind, hit, why in _compliance.check(text, extra, strict_source=not lenient):
        r.fail("COMPLIANCE", f"[{kind}] {hit!r} — {why}")


def cmd_check(a):
    doc = json.load(open(a.claims, encoding="utf-8"))
    text = open(a.reconciliation, encoding="utf-8", errors="ignore").read()
    r = Result()

    gate_classified(doc, r)
    gate_sourced(doc, r)
    gate_cited(doc, text, r)
    gate_grounded(doc, text, r, a.tolerance_pct)
    gate_no_argument(text, r)
    gate_referrals(doc, text, r)
    gate_compliance(text, a.client, r, a.lenient)

    print(f"claims:         {len(doc['claims'])}  (source: {doc.get('client_ai_source', 'unstated')})")
    print(f"reconciliation: {a.reconciliation}")
    for n in r.notes:
        print(f"  note   {n}")
    if not r.failures:
        print("\n  PASS  all gates")
        return 0
    by_gate = {}
    for g, d in r.failures:
        by_gate.setdefault(g, []).append(d)
    print()
    for g in sorted(by_gate):
        print(f"  FAIL  {g}")
        for d in by_gate[g]:
            print(f"          {d}")
    print(f"\n{len(r.failures)} failure(s) across {len(by_gate)} gate(s). Nothing goes to the client.")
    return 1


def cmd_classes(_a):
    print("claim classes\n")
    for k, why in CLASSES.items():
        need = []
        if k in NEEDS_SOURCE:
            need.append("source")
        if k in NEEDS_CORRECTION:
            need.append("correct_value")
        req = f"   requires: {', '.join(need)}" if need else ""
        print(f"  {k:<14} {why}{req}")
    print("\nciting numbers in the reconciliation")
    print("  [C-xxxxxx]    the figure comes from that claim, or from its correct_value")
    print("  [verified]    the agent's own record; a human confirms it")
    print("  [computed]    derived from figures already cited above it")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--claims", required=True)
    c.add_argument("--reconciliation", required=True)
    c.add_argument("--client", default=None, help="client slug, to merge their GUARDRAILS card")
    c.add_argument("--tolerance-pct", type=float, default=0.0,
                   help="allowed drift when matching a cited figure; default 0, meaning exact")
    c.add_argument("--lenient", action="store_true", help="skip the needs-a-source number check in compliance")
    c.set_defaults(fn=cmd_check)
    cl = sub.add_parser("classes"); cl.set_defaults(fn=cmd_classes)
    args = ap.parse_args()
    sys.exit(args.fn(args))

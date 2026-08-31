#!/usr/bin/env python3
"""
Decompose a client's chatbot output into individually checkable claims.

  claim_split.py split --in chatbot.txt --out claims.json
  claim_split.py split --in chatbot.txt --out claims.json --source "seller's ChatGPT, 2026-08-29"
  claim_split.py show --claims claims.json

This step is deliberately dumb. It does not decide what is true, it decides
what is *checkable*, and it does it the same way every time so two runs on the
same paste produce the same claim ids. Judgment happens after, when a human and
the model fill in `class` and `source` for each claim.

The reason this is a script and not a prompt: an agent who is about to sit
across from a seller needs the claim list to be complete. A model asked to
"find the claims" silently drops the inconvenient ones. A splitter cannot.
"""
import argparse, hashlib, json, re, sys

# Claim kinds, most specific first. A sentence gets every kind that matches;
# `kinds` is a list because "it's worth $540,000, about 12% over the last sale"
# is a price claim AND a percentage claim and both need checking.
KIND_PATTERNS = [
    ("price",        r"\$\s?\d[\d,]*(?:\.\d+)?\s?(?:k|m|million|thousand)?\b"),
    ("percent",      r"\b\d+(?:\.\d+)?\s?(?:%|percent\b)"),
    ("area",         r"\b\d[\d,]*\s?(?:sq\.?\s?ft|square feet|sqft|acres?)\b"),
    ("rooms",        r"\b\d+(?:\.\d+)?\s?(?:bed|bedroom|bath|bathroom|garage)s?\b"),
    ("date",         r"\b(?:19|20)\d{2}\b|\b\d+\s?(?:day|week|month|year)s?\b"),
    ("comparative",  r"\b(?:more|less|higher|lower|cheaper|faster|slower|better|worse|above|below|over|under)\s+than\b|\b(?:overpriced|underpriced|above market|below market)\b"),
    ("superlative",  r"\b(?:best|worst|highest|lowest|most|least|only|never|always|every|all)\b"),
    ("recommend",    r"\b(?:you should|I(?:'d| would) recommend|consider|offer|counter|walk away|ask for|negotiate|wait|list at|price it at)\b"),
    ("legal_tax",    r"\b(?:contract|contingenc|disclosure|liabilit|lawsuit|attorney|tax(?:es|able|ed)?|deduct|capital gains|1031|escrow|title|lien|zoning|permit)\w*\b"),
    ("lending",      r"\b(?:mortgage|interest rate|APR|pre-?approval|loan|underwrit|PMI|points|refinanc)\w*\b"),
]

# Hedges the model uses. Not a claim kind, but recorded, because a hedged
# sentence and a flat assertion need different handling in the conversation.
HEDGE = re.compile(
    r"\b(?:roughly|approximately|around|about|likely|probably|may|might|could|"
    r"generally|typically|often|estimate[sd]?|in the range of|somewhere)\b", re.I)

# Sentence boundaries that survive "$540,000." and "3.5 baths." and "Dr. Smith".
_ABBR = r"(?<!\bMr)(?<!\bMrs)(?<!\bMs)(?<!\bDr)(?<!\bSt)(?<!\bAve)(?<!\bapprox)"
BULLET = r"^(?:[-*\u2022\u2013\u2010]|\d+[.)])\s+(.*)$"
_SENT = re.compile(rf"{_ABBR}(?<=[.!?])\s+(?=[A-Z\"'(—-])")


def segment(text):
    """Sentences, plus list items promoted to their own claims.

    Two things chatbots do that break naive splitting, and both lose claims:

    They hard-wrap at ~80 columns, so one sentence arrives as two lines.
    Splitting on the newline yields a fragment starting mid-clause, which no
    human can check and no gate can cite. Prose lines are rejoined first.

    They answer in bullets. A bullet is a claim even with no terminal
    punctuation, so it flushes whatever came before it and stands alone."""
    units = []
    for block in re.split(r"\n\s*\n", text):
        buf = []
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            bullet = re.match(BULLET, line)
            if bullet:
                if buf:
                    units.append(" ".join(buf)); buf = []
                units.append(bullet.group(1).strip())
                continue
            buf.append(line)
        if buf:
            units.append(" ".join(buf))
    out = []
    for u in units:
        out.extend(p.strip() for p in _SENT.split(u) if p.strip())
    return [p for p in out if len(p) > 2]


def kinds_of(sentence):
    return [k for k, pat in KIND_PATTERNS if re.search(pat, sentence, re.I)]


def values_in(sentence):
    """Every money amount and percentage in the sentence, normalized.

    The gate downstream matches on these, so normalization has to be stable:
    '$540,000' and '$540000' are the same value and must not read as two."""
    vals = []
    for m in re.finditer(KIND_PATTERNS[0][1], sentence, re.I):
        raw = m.group(0)
        n = re.sub(r"[^\d.]", "", raw)
        if not n:
            continue
        v = float(n)
        tail = raw.lower()
        if "m" in tail or "million" in tail:
            v *= 1_000_000
        elif "k" in tail or "thousand" in tail:
            v *= 1_000
        vals.append({"raw": raw.strip(), "kind": "price", "value": v})
    for m in re.finditer(KIND_PATTERNS[1][1], sentence, re.I):
        raw = m.group(0)
        n = re.sub(r"[^\d.]", "", raw)
        if n:
            vals.append({"raw": raw.strip(), "kind": "percent", "value": float(n)})
    return vals


def claim_ids(sentences):
    """One id per sentence, derived from the sentence text alone.

    The id must survive an EDIT, not just a re-run. An earlier scheme prefixed
    the position (C-01-d91b); inserting one sentence above shifted every index
    below it and silently detached every citation the agent had already written.
    Hash-only ids don't move when their neighbours do.

    A repeated sentence gets a, b, c suffixes in order of appearance, so two
    identical claims stay distinct and both stay citable."""
    seen = {}
    out = []
    for s in sentences:
        h = hashlib.sha256(s.encode("utf-8")).hexdigest()[:6]
        n = seen.get(h, 0)
        seen[h] = n + 1
        out.append(f"C-{h}" if n == 0 else f"C-{h}{chr(ord('a') + n)}")
    return out


def split(text, source_label):
    claims = []
    sentences = segment(text)
    ids = claim_ids(sentences)
    for i, s in enumerate(sentences, start=1):
        k = kinds_of(s)
        if not k and not HEDGE.search(s):
            # An unclassifiable sentence is still a claim if it asserts anything.
            # Pure connective tissue ("Here's a breakdown:") is not.
            if not re.search(r"\b(?:is|are|was|were|has|have|will|would|can|should|means|suggests)\b", s, re.I):
                continue
            k = ["assertion"]
        claims.append({
            "id": ids[i - 1],
            "text": s,
            "kinds": k or ["assertion"],
            "hedged": bool(HEDGE.search(s)),
            "values": values_in(s),
            # Filled in by a human working with the model. Never pre-filled here.
            "class": None,
            "source": None,
            "correct_value": None,
            "note": None,
        })
    return {
        "schema": "chatgpt-said/claims/v1",
        "client_ai_source": source_label,
        "claim_count": len(claims),
        "claims": claims,
    }


def cmd_split(a):
    text = sys.stdin.read() if a.inp == "-" else open(a.inp, encoding="utf-8", errors="ignore").read()
    doc = split(text, a.source)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"{doc['claim_count']} claim(s) -> {a.out}")
    print("every one needs a class and, where checked, a source. none are pre-filled.")
    return 0


def cmd_show(a):
    doc = json.load(open(a.claims, encoding="utf-8"))
    for c in doc["claims"]:
        flag = c["class"] or "UNCLASSIFIED"
        hedge = " (hedged)" if c["hedged"] else ""
        print(f"{c['id']}  [{flag}]{hedge}  {', '.join(c['kinds'])}")
        print(f"        {c['text']}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split")
    s.add_argument("--in", dest="inp", required=True, help="chatbot output, or - for stdin")
    s.add_argument("--out", required=True)
    s.add_argument("--source", default="client's AI assistant", help="what the client used, and when")
    s.set_defaults(fn=cmd_split)
    sh = sub.add_parser("show"); sh.add_argument("--claims", required=True); sh.set_defaults(fn=cmd_show)
    args = ap.parse_args()
    sys.exit(args.fn(args))

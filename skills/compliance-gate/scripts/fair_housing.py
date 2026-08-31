#!/usr/bin/env python3
"""
Real estate copy compliance gate — the ONE copy of these rules in the bundle.

  fair_housing.py check --text "..."             check one string
  fair_housing.py check --file <path>            check a file
  fair_housing.py check --batch <batch.json>     check every caption in a batch
  fair_housing.py check ... --profile <mls>      merge a local MLS profile
  fair_housing.py rules [--client <slug>] [--profile <mls>]

Lived in content-foundry until four skills needed it; a second copy would drift,
and the copy that drifts is the one that reaches a client. content-foundry keeps
a shim at its old path so nothing that imported it breaks.

Rules come from the client's own GUARDRAILS card in their Drive brand context
when one is present, merged over the built-in Fair Housing baseline. The card
wins on conflicts, because it was written for that brokerage.

Exit code 1 if anything fails. This is a gate, not advice.
"""
import argparse, json, os, re, sys, glob

_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.realpath(os.path.join(_HERE, "..", "..", "post-bridge-schedule", "scripts")))
sys.path.insert(0, _HERE)
import config as _cfg  # noqa: E402

# Fair Housing baseline. Applies even with no client card present.
BANNED = {
    "dream home": "describe the property",
    "hidden gem": "say what is actually unusual about it",
    "must-see": "state the feature",
    "perfect for": "implies an ideal buyer, a Fair Housing problem",
    "nestled": "filler",
    "charming neighborhood": "subjective claim about an area",
    "safe neighborhood": "Fair Housing violation, never make safety claims",
    "safest neighborhood": "Fair Housing violation, never make safety claims",
    "safe area": "Fair Housing violation",
    "safest area": "Fair Housing violation",
    "safest part of": "Fair Housing violation",
    "family-friendly": "demographic targeting",
    "family friendly": "demographic targeting",
    "walking distance": "use objective distance or 'near'",
    "steps from": "use objective distance or 'near'",
    "top-rated schools": "never make school quality claims",
    "great schools": "never make school quality claims",
    "good schools": "never make school quality claims",
    "school district is excellent": "never make school quality claims",
    "up-and-coming": "coded demographic language",
    "up and coming": "coded demographic language",
    "young professionals": "demographic targeting",
    "empty nester": "demographic targeting",
    "bachelor pad": "demographic targeting",
    "starter family": "demographic targeting",
    "exclusive community": "exclusionary language",
    "traditional neighborhood": "coded language",
    "integrated community": "references protected class",
    "no kids": "familial status discrimination",
    "adult living": "familial status, unless a verified 55+ community",
    "christian": "religious reference in property copy",
    "church nearby": "religious reference in property copy",
}
# Promises the READ ME forbids outright.
PROMISE = [
    (r"\bguarantee(d|s)?\b", "no guarantees of any kind"),
    (r"\bwill (appreciate|increase in value|sell fast|sell quickly)\b", "no outcome promises"),
    (r"\bpromise[sd]?\b", "no promises"),
    (r"\breturn on investment\b", "no investment performance claims"),
    (r"\bcash flow(s|ing)? \$?\d", "no investment performance claims"),
    (r"\bwill rent for\b", "no rent promises"),
    (r"\bclos(e|ing) in \d+ days\b", "no timeline promises"),
    (r"\bworth \$?\d[\d,]*\b", "no valuation claims without a sourced appraisal"),
]
# Numbers that need a source.
NEEDS_SOURCE = [
    (r"\b\d[\d,]*\s*(sq\.?\s?ft|square feet|sqft)\b", "square footage"),
    (r"\b\d+\s*(bed|bedroom|bath|bathroom)s?\b", "room counts"),
    (r"\b\d+(\.\d+)?%\s", "percentage"),
    (r"\bHOA\b.*\$\d", "HOA fees"),
    (r"\btax(es)?\b.*\$\d", "tax figures"),
    (r"\bbuilt in \d{4}\b", "year built"),
]


def load_card(slug):
    """Find a GUARDRAILS card in the client's synced brand context."""
    if not slug:
        return None, []
    try:
        cc = _cfg.load("clients")
    except Exception:
        return None, []
    root = os.path.expanduser(cc.get("cache_root", "~/.cache/re-skills/clients"))
    hits = glob.glob(os.path.join(root, slug, "brand-context", "**", "*GUARDRAIL*"), recursive=True)
    hits += glob.glob(os.path.join(root, slug, "brand-context", "**", "*guardrail*"), recursive=True)
    if not hits:
        return None, []
    text = open(hits[0], errors="ignore").read()
    extra = []
    m = re.search(r"#+\s*Banned Default Phrases(.+?)(\n#+\s|\Z)", text, re.S | re.I)
    if m:
        for line in m.group(1).splitlines():
            line = line.strip(" -*\t")
            if not line or line.startswith("#"):
                continue
            phrase = re.split(r"\s+unless\s+|\s+\(", line)[0].strip().lower()
            if 2 < len(phrase) < 60:
                extra.append(phrase)
    return hits[0], extra


def load_profile(name):
    """Extra rules for one MLS/board, from config/compliance/<name>.json.

    A profile ADDS rules; it can never remove a baseline rule. Boards differ in
    what they additionally prohibit, not in whether Fair Housing applies."""
    if not name:
        return {}
    import json as _json
    here = os.path.dirname(os.path.realpath(__file__))
    for up in range(1, 5):
        p = os.path.realpath(os.path.join(here, *[".."] * up, "config", "compliance", f"{name}.json"))
        if os.path.isfile(p):
            with open(p) as fh:
                d = _json.load(fh)
            d["_source"] = p
            return d
    raise SystemExit(f"unknown compliance profile {name!r}: no config/compliance/{name}.json found")


def check(text, extra_banned=(), strict_source=True, profile=None):
    # Collapse whitespace before matching: a caption wraps "walking\ndistance"
    # across lines and a substring check on the raw text walks right past it.
    low = re.sub(r"\s+", " ", text.lower())
    out = []
    prof = load_profile(profile) if isinstance(profile, str) else (profile or {})
    for phrase, why in {**BANNED, **{k.lower(): v for k, v in prof.get("banned", {}).items()}}.items():
        if phrase in low:
            out.append(("BANNED", phrase, why))
    for phrase in extra_banned:
        if phrase in low and not any(phrase == b for b in BANNED):
            out.append(("BANNED", phrase, "from the client GUARDRAILS card"))
    for pat, why in PROMISE:
        m = re.search(pat, low)
        if m:
            out.append(("PROMISE", m.group(0), why))
    if strict_source:
        for pat, what in NEEDS_SOURCE:
            m = re.search(pat, low)
            if m and "verify" not in low and "source" not in low and "per " not in low:
                out.append(("NEEDS_SOURCE", m.group(0), f"{what} needs a source or a VERIFY marker"))
    return out


def report(label, findings):
    if not findings:
        print(f"  PASS  {label}")
        return 0
    print(f"  FAIL  {label}")
    for kind, hit, why in findings:
        print(f"          [{kind}] {hit!r} — {why}")
    return 1


def cmd_check(a):
    card, extra = load_card(a.client)
    prof = load_profile(getattr(a, "profile", None))
    print(f"guardrails card: {card or 'none found, using Fair Housing baseline only'}")
    if extra:
        print(f"  +{len(extra)} banned phrases from the client card")
    if prof:
        print(f"  +{len(prof.get('banned', {}))} banned phrases from profile {prof['_source']}")
    bad = 0
    if a.text:
        bad += report("--text", check(a.text, extra, not a.lenient, prof))
    if a.file:
        bad += report(a.file, check(open(a.file, errors="ignore").read(), extra, not a.lenient, prof))
    if a.batch:
        b = json.load(open(a.batch))
        for p in b.get("posts", []):
            for acct, cap in p.get("captions", {}).items():
                bad += report(f"{p.get('slug','?')} / {acct}", check(cap, extra, not a.lenient, prof))
    print(f"\n{'ALL CLEAR' if not bad else str(bad) + ' item(s) failed'}")
    return 1 if bad else 0


def cmd_rules(a):
    card, extra = load_card(a.client)
    print(f"guardrails card: {card or 'none'}")
    print(f"\nFair Housing baseline: {len(BANNED)} banned phrases")
    for p, w in sorted(BANNED.items()):
        print(f"  {p:<28} {w}")
    print(f"\npromise patterns: {len(PROMISE)}")
    print(f"source-required patterns: {len(NEEDS_SOURCE)}")
    if extra:
        print(f"\nfrom the client card: {len(extra)}")
        for p in extra:
            print(f"  {p}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--text"); c.add_argument("--file"); c.add_argument("--batch")
    c.add_argument("--client"); c.add_argument("--lenient", action="store_true")
    c.add_argument("--profile", help="MLS profile name from config/compliance/")
    c.set_defaults(fn=cmd_check)
    r = sub.add_parser("rules"); r.add_argument("--client"); r.set_defaults(fn=cmd_rules)
    args = ap.parse_args()
    sys.exit(args.fn(args))

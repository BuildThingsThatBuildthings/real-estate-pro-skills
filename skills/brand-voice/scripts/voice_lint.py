#!/usr/bin/env python3
"""
Deterministic half of the brand-voice audit.

  voice_lint.py check --pack <voice-pack.md> --draft <draft.json>
  voice_lint.py check ... --lenient        # skip the source-required check

The pack holds judgment calls a human wrote down; this script enforces the ones
a machine can settle: banned words, hashtag piles, duplicated captions across
channels, links in an X body, missing hooks, unsourced claims. The other half
of the audit — does this SOUND like the brand — stays with the model reading
the pack's on-brand and off-brand examples. A linter that claims to measure
voice is lying; one that catches the mechanical failures frees the reader to
judge only voice.

draft.json:
  { "captions": { "<channel>": "<text>", ... } }

Exit 1 on any finding. This is a gate, not advice.
"""
import argparse, json, os, re, sys

HASHTAG_PILE = 3          # >= this many hashtags in one caption is a pile
FIRST_LINE_MAX = 120      # a first line longer than this is not a hook
URL = re.compile(r"https?://\S+")
CLAIM_NUMBER = re.compile(r"\b\d[\d,]*(?:\.\d+)?\s?(?:%|percent\b|sq\.?\s?ft\b|sqft\b|\$)|\$\s?\d", re.I)
SOURCED = re.compile(r"\[(?:source:[^\]]+|verified|VERIFY)\]", re.I)


def parse_pack(path):
    """Pull the machine-checkable parts out of a voice pack: the banned-word
    list, and whether the pack exists at all. Everything else in the pack is
    for the model, not for this script."""
    text = open(path, encoding="utf-8").read()
    banned = []
    m = re.search(r"#+\s*Banned words(.*?)(\n#+\s|\Z)", text, re.S | re.I)
    if m:
        for line in m.group(1).splitlines():
            line = line.strip(" -*\t")
            if not line or line.startswith("#"):
                continue
            word = re.split(r"\s+—|\s+-\s+|\s*\(", line)[0].strip().lower()
            if 1 < len(word) < 40:
                banned.append(word)
    return {"banned": banned, "name": os.path.basename(path)}


def check(captions, pack, strict_source=True):
    out = []
    seen_texts = {}
    for ch, cap in captions.items():
        low = re.sub(r"\s+", " ", cap.lower())
        # banned words, from the pack. The pack wrote them down for a reason.
        for w in pack["banned"]:
            if re.search(rf"(?<![\w'-]){re.escape(w)}(?![\w'-])", low):
                out.append((ch, "BANNED_WORD", w, f"the pack bans it"))
        # hashtag piles read as spam on every surface
        tags = re.findall(r"#\w+", cap)
        if len(tags) >= HASHTAG_PILE:
            out.append((ch, "HASHTAG_PILE", f"{len(tags)} hashtags", "keywords belong in the prose"))
        # the first line is the whole hook; most surfaces truncate
        first = cap.strip().splitlines()[0] if cap.strip() else ""
        if len(first) > FIRST_LINE_MAX:
            out.append((ch, "NO_HOOK", f"first line is {len(first)} chars",
                        f"front-load it; surfaces truncate near {FIRST_LINE_MAX}"))
        # X strips URLs from the body — the link belongs in the first comment
        if ch.lower() in ("x", "twitter") and URL.search(cap):
            out.append((ch, "LINK_IN_X_BODY", URL.search(cap).group(0)[:40], "links go in the first comment on X"))
        # a number is a claim; a claim carries a source
        if strict_source and CLAIM_NUMBER.search(cap) and not SOURCED.search(cap):
            out.append((ch, "UNSOURCED_CLAIM", CLAIM_NUMBER.search(cap).group(0).strip(),
                        "a figure needs [source: ...] or [VERIFY]"))
        # one caption per channel, all genuinely different — copying one caption
        # across surfaces throws away the whole point of per-channel publishing
        key = re.sub(r"\W+", "", low)[:200]
        if key and key in seen_texts:
            out.append((ch, "DUPLICATE_CAPTION", f"same text as {seen_texts[key]}",
                        "one idea, written once per channel, never copied"))
        elif key:
            seen_texts[key] = ch
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--pack", required=True)
    c.add_argument("--draft", required=True)
    c.add_argument("--lenient", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(a.pack):
        print(f"no voice pack at {a.pack} — do not invent a voice; ask for the pack.")
        return 2
    pack = parse_pack(a.pack)
    draft = json.load(open(a.draft, encoding="utf-8"))
    findings = check(draft.get("captions", {}), pack, strict_source=not a.lenient)
    print(f"pack: {pack['name']}  ({len(pack['banned'])} banned words)")
    print(f"captions: {len(draft.get('captions', {}))}")
    if not findings:
        print("\n  PASS  mechanical checks — now judge VOICE against the pack's examples")
        return 0
    print()
    for ch, kind, hit, why in findings:
        print(f"  FAIL  {ch:<12} [{kind}] {hit!r} — {why}")
    print(f"\n{len(findings)} finding(s). Fix the draft, not the linter.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

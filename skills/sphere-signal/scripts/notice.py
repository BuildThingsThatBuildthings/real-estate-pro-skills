#!/usr/bin/env python3
"""
Find the people who have a real reason to hear from this agent this week.

  notice.py scan --contacts contacts.csv --touchpoints touchpoints.csv --today 2026-08-29 --out reasons.json
  notice.py scan ... --limit 20
  notice.py reasons                      # the reason types, and what each requires

Reasons are COMPUTED, never invented. Every one traces to a date or a field in
the agent's own records, and carries the arithmetic that produced it. A model
asked to "find who to reach out to" produces a plausible list; a plausible list
is how a database gets spammed and an agent gets muted.

What this deliberately does not do
----------------------------------
No scoring of people. No "likelihood to sell" ranking. No inference from name,
address, photo, or anything else about who someone is. The only thing that makes
a contact surface here is a dated fact they gave the agent, or a promise the
agent made and has not kept.
"""
import argparse, csv, datetime as dt, json, sys
from collections import defaultdict

ISO = "%Y-%m-%d"

# Every reason type states what it needs and what it licenses. `requires` fields
# missing from a contact means the reason cannot fire — it does not mean the
# reason fires weakly.
REASONS = {
    "promise_due": {
        "requires": ["touchpoint.promise", "touchpoint.promise_due"],
        "why": "the agent said they would do something by a date; that date has arrived or passed",
        "urgency": 0,  # sorts first, always
    },
    "question_unanswered": {
        "requires": ["touchpoint.open_question"],
        "why": "they asked something and no later touchpoint answered it",
        "urgency": 1,
    },
    "home_anniversary": {
        "requires": ["contact.closed_date"],
        "why": "a dated anniversary of a transaction the agent was part of",
        "urgency": 2,
    },
    "holding_period": {
        "requires": ["contact.closed_date"],
        "why": "they have owned long enough that a move is plausible to ASK about, never to assume",
        "urgency": 3,
    },
    "dormant": {
        "requires": ["touchpoint.date"],
        "why": "no contact in longer than the configured window",
        "urgency": 4,
    },
    "never_touched": {
        "requires": ["contact.id"],
        "why": "in the database and never contacted at all",
        "urgency": 4,
    },
}

# Fields that must never be read, even if an agent puts them in the CSV. Reading
# them is how a follow-up system starts targeting protected classes. The scan
# refuses to run rather than silently ignoring them, because a column named
# `kids` in the file means somebody intended to use it.
FORBIDDEN_FIELDS = {
    "race", "ethnicity", "national_origin", "nationality", "religion", "church",
    "kids", "children", "num_children", "family_status", "familial_status",
    "marital_status", "married", "divorce", "divorced", "pregnant", "age",
    "disability", "handicap", "sex", "gender", "orientation", "immigration",
    "citizenship", "language_spoken", "ancestry",
}


def parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in (ISO, "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fields = set()
    for r in rows:
        fields |= {(k or "").strip().lower() for k in r}
    bad = sorted(fields & FORBIDDEN_FIELDS)
    if bad:
        raise SystemExit(
            f"refusing to read {path}: column(s) {bad} name a protected class.\n"
            f"  Remove them from the export. A follow-up system must not be able to see them,\n"
            f"  and ignoring them silently would leave them one edit away from being used.")
    return rows


def years_between(a, b):
    """Whole years, calendar-correct. Feb 29 lands on Mar 1 in common years."""
    y = b.year - a.year
    try:
        anniv = a.replace(year=b.year)
    except ValueError:
        anniv = a.replace(year=b.year, month=3, day=1)
    if anniv > b:
        y -= 1
    return y


def next_anniversary(closed, today):
    try:
        anniv = closed.replace(year=today.year)
    except ValueError:
        anniv = closed.replace(year=today.year, month=3, day=1)
    if anniv < today:
        try:
            anniv = closed.replace(year=today.year + 1)
        except ValueError:
            anniv = closed.replace(year=today.year + 1, month=3, day=1)
    return anniv


def scan(contacts, touchpoints, today, cfg):
    by_contact = defaultdict(list)
    for t in touchpoints:
        by_contact[(t.get("contact_id") or "").strip()].append(t)
    for tps in by_contact.values():
        tps.sort(key=lambda t: parse_date(t.get("date")) or dt.date.min)

    found = []
    for c in contacts:
        cid = (c.get("id") or "").strip()
        if not cid:
            continue
        if (c.get("opted_out") or "").strip().lower() in ("y", "yes", "true", "1"):
            continue
        name = (c.get("name") or cid).strip()
        tps = by_contact.get(cid, [])
        dated = [t for t in tps if parse_date(t.get("date"))]
        last = parse_date(dated[-1]["date"]) if dated else None

        # --- promise_due: the agent's own unkept word. Always first.
        for t in tps:
            due = parse_date(t.get("promise_due"))
            promise = (t.get("promise") or "").strip()
            done = (t.get("promise_done") or "").strip().lower() in ("y", "yes", "true", "1")
            if promise and due and not done and due <= today:
                found.append(reason(cid, name, "promise_due", today,
                                    f"promised {promise!r}, due {due.isoformat()}",
                                    {"promise": promise, "due": due.isoformat(),
                                     "days_overdue": (today - due).days},
                                    f"touchpoint {t.get('date')}"))

        # --- question_unanswered: they asked, nobody answered.
        for i, t in enumerate(tps):
            q = (t.get("open_question") or "").strip()
            if not q:
                continue
            qd = parse_date(t.get("date"))
            answered = any((later.get("answers") or "").strip() == (t.get("id") or "").strip()
                           for later in tps[i + 1:] if (t.get("id") or "").strip())
            if not answered:
                found.append(reason(cid, name, "question_unanswered", today,
                                    f"asked {q!r} and it was never answered",
                                    {"question": q, "asked": qd.isoformat() if qd else None},
                                    f"touchpoint {t.get('date')}"))

        closed = parse_date(c.get("closed_date"))
        if closed:
            # --- home_anniversary: dated, factual, needs no pretext.
            anniv = next_anniversary(closed, today)
            lead = (anniv - today).days
            if 0 <= lead <= cfg["anniversary_lead_days"]:
                found.append(reason(cid, name, "home_anniversary", today,
                                    f"{years_between(closed, anniv)}-year anniversary of closing on {closed.isoformat()}",
                                    {"closed": closed.isoformat(), "anniversary": anniv.isoformat(),
                                     "years": years_between(closed, anniv), "days_out": lead},
                                    "contact.closed_date"))
            # --- holding_period: a reason to ASK, never a prediction.
            held = years_between(closed, today)
            if held >= cfg["holding_period_years"]:
                found.append(reason(cid, name, "holding_period", today,
                                    f"owned {held} years, past the {cfg['holding_period_years']}-year mark",
                                    {"closed": closed.isoformat(), "years_held": held},
                                    "contact.closed_date"))

        # --- dormant / never_touched
        if last is None:
            found.append(reason(cid, name, "never_touched", today,
                                "no touchpoint on record at all", {}, "touchpoints.csv"))
        else:
            gap = (today - last).days
            if gap >= cfg["dormant_days"]:
                found.append(reason(cid, name, "dormant", today,
                                    f"{gap} days since the last contact on {last.isoformat()}",
                                    {"last_contact": last.isoformat(), "days_since": gap},
                                    f"touchpoint {last.isoformat()}"))
    found.sort(key=lambda r: (REASONS[r["reason"]]["urgency"], r["contact_name"]))
    return found


def reason(cid, name, kind, today, human, computed, source):
    return {
        "id": f"R-{kind}-{cid}",
        "contact_id": cid,
        "contact_name": name,
        "reason": kind,
        "as_of": today.isoformat(),
        "human": human,
        "computed": computed,
        "source": source,
    }


def cmd_scan(a):
    today = parse_date(a.today) or dt.date.today()
    cfg = {
        "dormant_days": a.dormant_days,
        "holding_period_years": a.holding_period_years,
        "anniversary_lead_days": a.anniversary_lead_days,
    }
    contacts = read_csv(a.contacts)
    tps = read_csv(a.touchpoints) if a.touchpoints else []
    found = scan(contacts, tps, today, cfg)
    if a.limit:
        found = found[:a.limit]
    doc = {
        "schema": "sphere-signal/reasons/v1",
        "as_of": today.isoformat(),
        "config": cfg,
        "contacts_scanned": len(contacts),
        "reason_count": len(found),
        "reasons": found,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    counts = defaultdict(int)
    for r in found:
        counts[r["reason"]] += 1
    print(f"{len(contacts)} contact(s) scanned as of {today.isoformat()}")
    for k in sorted(counts, key=lambda x: REASONS[x]["urgency"]):
        print(f"  {counts[k]:>3}  {k}")
    print(f"-> {a.out}")
    print("no contact is scored or ranked by who they are. every reason above is a date.")
    return 0


def cmd_reasons(_a):
    print("reason types, most urgent first\n")
    for k, v in sorted(REASONS.items(), key=lambda kv: kv[1]["urgency"]):
        print(f"  {k}")
        print(f"      {v['why']}")
        print(f"      requires: {', '.join(v['requires'])}")
    print(f"\nrefused columns ({len(FORBIDDEN_FIELDS)}): reading any of these aborts the scan")
    print("  " + ", ".join(sorted(FORBIDDEN_FIELDS)))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--contacts", required=True)
    s.add_argument("--touchpoints")
    s.add_argument("--out", required=True)
    s.add_argument("--today", help="YYYY-MM-DD; defaults to today. Pass it to make runs reproducible.")
    s.add_argument("--dormant-days", type=int, default=180)
    s.add_argument("--holding-period-years", type=int, default=7)
    s.add_argument("--anniversary-lead-days", type=int, default=21)
    s.add_argument("--limit", type=int, default=0)
    s.set_defaults(fn=cmd_scan)
    r = sub.add_parser("reasons"); r.set_defaults(fn=cmd_reasons)
    args = ap.parse_args()
    sys.exit(args.fn(args))

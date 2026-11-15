"""Configuration loader for the posting pipeline.

Resolution for each file:
  1. $RE_SKILLS_CONFIG_DIR/<name>.json
  2. <repo>/config/<name>.json

There is deliberately NO built-in account fallback. A missing channels.json
raises rather than defaulting, because a silent default here would post one
person's content to another person's accounts.

realpath, not abspath: this file is normally reached through a symlink in
~/.claude/skills, and normpath would collapse ".." textually back out of the repo.
"""
import json, os

_HERE = os.path.dirname(os.path.realpath(__file__))


class ConfigError(RuntimeError):
    pass


def _candidates(name):
    """If RE_SKILLS_CONFIG_DIR is set it is AUTHORITATIVE and nothing else is
    consulted. Falling back to the repo config when an explicit profile
    directory is missing a file would silently post one person's content to
    another person's accounts."""
    env = os.environ.get("RE_SKILLS_CONFIG_DIR")
    if env:
        yield os.path.join(os.path.expanduser(env), f"{name}.json")
        return
    for up in range(1, 5):
        yield os.path.realpath(os.path.join(_HERE, *[".."] * up, "config", f"{name}.json"))


def load(name, required=True):
    tried = []
    for c in _candidates(name):
        tried.append(c)
        if os.path.isfile(c):
            with open(c) as f:
                d = json.load(f)
            d["_source"] = c
            return d
    if not required:
        return {}
    raise ConfigError(
        f"missing config '{name}.json'.\n"
        f"  copy config/{name}.example.json to config/{name}.json and fill it in,\n"
        f"  or set RE_SKILLS_CONFIG_DIR.\n  looked in:\n    " + "\n    ".join(tried))


def expand(p):
    return os.path.expanduser(p) if isinstance(p, str) else p


# ---- channels ----
_ch = load("channels")
NAME = {int(k): v["label"] for k, v in _ch["channels"].items()}
PLATFORM = {int(k): v["platform"] for k, v in _ch["channels"].items()}
BRAND = {int(k): v.get("brand", "") for k, v in _ch["channels"].items()}
MIN_GAP = int(_ch.get("min_gap_minutes", 45))  # ops/social-engine/ACCOUNT-REGISTRY.md rule 4
IMAGE_ONLY = set(_ch.get("image_only_platforms", ["google_business"]))
VIDEO_REQUIRED = set(_ch.get("video_required_platforms", ["youtube"]))
IMAGE_ONLY_IDS = [a for a, p in PLATFORM.items() if p in IMAGE_ONLY]
GBP = IMAGE_ONLY_IDS[0] if IMAGE_ONLY_IDS else None
CHANNELS_SOURCE = _ch["_source"]

# ---- brand (optional) ----
_br = load("brand", required=False)
BRAND_NAME = _br.get("name", "")
SITE_URL = _br.get("site_url", "")
CTA = _br.get("cta", {"action_type": "LEARN_MORE", "url": SITE_URL})
CARD = _br.get("card", {})

# ---- pipeline (optional, with neutral defaults) ----
_pl = load("pipeline", required=False)
RAMP = _pl.get("ramp", {"rungs": [5], "block_days": 30, "horizon_blocks": 2})
RUNGS = RAMP.get("rungs", [5])
BLOCK_DAYS = int(RAMP.get("block_days", 30))
HORIZON_BLOCKS = int(RAMP.get("horizon_blocks", 2))
W = _pl.get("windows", {})
MIN_RECORDS_PER_HOUR = int(W.get("min_records_per_hour", 8))
# Posting window 06:00 to 22:00 Central, INCLUSIVE: a post may start exactly at
# 22:00 (never 22:01 or later) and no earlier than 06:00. The window is the start
# time bound; forbidden_hours only keeps overnight hours out of scoring. Hour 22
# is scored, and its slot is exactly latest_start (22:00), never 22:15.
EARLIEST_START = W.get("earliest_start", "06:00")
LATEST_START = W.get("latest_start", "22:00")
FORBIDDEN_HOURS = set(W.get("forbidden_hours", [0, 1, 2, 3, 4, 5, 23]))


def _minutes(hhmm):
    h, m = map(int, str(hhmm).split(":")[:2])
    return h * 60 + m


def in_window(hhmm):
    """True when an "HH:MM" CT start time is inside earliest_start..latest_start, inclusive."""
    return _minutes(EARLIEST_START) <= _minutes(hhmm) <= _minutes(LATEST_START)


# Lead time: a new post may be placed as soon as this many hours from now.
LEAD_HOURS = float(_pl.get("approval", {}).get("lead_hours", 1))
VIEW_RELIABLE = set(W.get("view_reliable_platforms", ["youtube", "tiktok", "facebook"]))
LIKE_SIGNAL = set(W.get("like_signal_platforms", ["instagram"]))
VIEW_WEIGHT = float(W.get("view_weight", 0.75))
LIKE_WEIGHT = float(W.get("like_weight", 0.25))
# Optional precomputed windows (War Room warehouse verb social.windows). Empty = live only.
WAREHOUSE_URL = W.get("warehouse_url", "")
WAREHOUSE_MAX_AGE_HOURS = float(W.get("warehouse_max_age_hours", 48))
# The same-account gap (channels.json min_gap_minutes, 45) applies per account. Across
# DIFFERENT accounts only this small stagger applies, so two records never land
# on the same minute.
MIN_GLOBAL_STAGGER = int(_pl.get("min_global_stagger_minutes", 10))
TZ = _pl.get("timezone", {"dst_offset_hours": -5, "std_offset_hours": -6, "dst_months": [3, 11]})
TOOLS = {k: expand(v) for k, v in _pl.get("tools", {}).items()}
CAPTION_RULES = _pl.get("captions", {})

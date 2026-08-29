"""Shared channel configuration loader.

Resolution order:
  1. $RE_SKILLS_CHANNELS
  2. <repo>/config/channels.json
  3. built-in default (Ryan's AIA + BT2 set)

Keeping this in one place is what lets the bundle serve a second professional
without editing four scripts.
"""
import json, os

_DEFAULT = {
    72366: 'ig/AIA-RE', 75846: 'fb/AIA-RE', 75843: 'yt/AIA-RE', 72367: 'x/AIA',
    72370: 'li/AIA', 75850: 'gbp/AIA', 75848: 'fb/BT2', 75841: 'ig/BT2', 75844: 'tt/BT2',
}
_DEFAULT_GBP = 75850
_DEFAULT_GAP = 90


def _find():
    p = os.environ.get("RE_SKILLS_CHANNELS")
    if p and os.path.exists(p):
        return p
    here = os.path.dirname(os.path.abspath(__file__))
    for up in range(1, 5):
        c = os.path.join(here, *[".."] * up, "config", "channels.json")
        if os.path.exists(c):
            return os.path.normpath(c)
    return None


def load():
    p = _find()
    if not p:
        return dict(NAME=dict(_DEFAULT), GBP=_DEFAULT_GBP, MIN_GAP=_DEFAULT_GAP, source="built-in")
    cfg = json.load(open(p))
    name = {int(k): v["label"] for k, v in cfg["channels"].items()}
    return dict(NAME=name,
                GBP=int(cfg.get("gbp_account_id", _DEFAULT_GBP)),
                MIN_GAP=int(cfg.get("min_gap_minutes", _DEFAULT_GAP)),
                source=p)


CFG = load()
NAME = CFG["NAME"]
GBP = CFG["GBP"]
MIN_GAP = CFG["MIN_GAP"]

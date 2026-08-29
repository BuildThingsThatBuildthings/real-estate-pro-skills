#!/usr/bin/env python3
"""
Preflight environment check. Run this first on any new machine or profile.

  doctor.py
"""
import json, os, shutil, subprocess, sys, urllib.error

_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, _HERE)

OK, WARN, FAIL = "  ok  ", " warn ", " FAIL "
rows = []


def add(status, name, detail=""):
    rows.append((status, name, detail))


# --- config ---
try:
    import config as cfg
    add(OK, "config/channels.json", f"{len(cfg.NAME)} channels from {cfg.CHANNELS_SOURCE}")
    if cfg.GBP is None:
        add(WARN, "image-only channel", "none declared; platforms that reject video will fail")
    else:
        add(OK, "image-only channel", f"{cfg.NAME[cfg.GBP]} will receive a still, not video")
    add(OK if cfg.BRAND_NAME else WARN, "config/brand.json",
        cfg.BRAND_NAME or "missing; card generator and default CTA will not work")
    add(OK, "ramp", f"rungs {cfg.RUNGS}, {cfg.BLOCK_DAYS} day blocks, {cfg.HORIZON_BLOCKS} block horizon")
    add(OK, "collision rule", f"{cfg.MIN_GAP} minutes minimum on the same channel")
except Exception as e:
    add(FAIL, "config", str(e).splitlines()[0])
    cfg = None

# --- binaries ---
for b, why in (("ffmpeg", "media probing and card rendering"),
               ("ffprobe", "duration and dimension checks"),
               ("node", "card generator"),
               ("python3", "pipeline scripts")):
    p = shutil.which(b)
    add(OK if p else FAIL, b, p or f"not on PATH, needed for {why}")

# --- whisper ---
if cfg:
    wbin = cfg.TOOLS.get("whisper_cli", "whisper-cli")
    wmodel = cfg.TOOLS.get("whisper_model", "")
    add(OK if shutil.which(wbin) else WARN, "whisper cli",
        shutil.which(wbin) or f"{wbin} not found; transcription step unavailable")
    add(OK if wmodel and os.path.isfile(wmodel) else WARN, "whisper model",
        wmodel if wmodel and os.path.isfile(wmodel) else "not found; set tools.whisper_model")

# --- api ---
try:
    import pb
    accts = pb.paged("/social-accounts")
    add(OK, "Post Bridge API", f"{len(accts)} accounts reachable")
    ids = {a["id"] for a in accts}
    if cfg:
        missing = [f"{a} ({n})" for a, n in cfg.NAME.items() if a not in ids]
        add(OK if not missing else FAIL, "configured channels exist",
            "all present" if not missing else "not on this account: " + ", ".join(missing))
        stale = [a["username"] for a in accts if a.get("needs_reconnect") and a["id"] in cfg.NAME]
        add(OK if not stale else FAIL, "channel auth",
            "none need reconnect" if not stale else "reconnect: " + ", ".join(stale))
    an = pb.paged("/analytics")
    add(OK if len(an) >= 30 else WARN, "analytics history",
        f"{len(an)} records" + ("" if len(an) >= 30 else "; too few to derive windows, defaults will be used"))
except Exception as e:
    add(FAIL, "Post Bridge API", str(e).splitlines()[0])

# --- card generator ---
tool = os.path.realpath(os.path.join(_HERE, "..", "tools", "make-card.mjs"))
add(OK if os.path.isfile(tool) else FAIL, "card generator", tool if os.path.isfile(tool) else "missing")
if cfg and cfg.CARD:
    for k in ("font_bold", "font_regular"):
        f = cfg.CARD.get(k, "")
        add(OK if f and os.path.isfile(f) else WARN, f"font {k}", f if f and os.path.isfile(f) else "not found")

print(f"{'STATUS':<8}{'CHECK':<28}DETAIL")
for s, n, d in rows:
    print(f"[{s}] {n:<26}{d}")
bad = sum(1 for s, _, _ in rows if s == FAIL)
warn = sum(1 for s, _, _ in rows if s == WARN)
print(f"\n{len(rows)} checks: {bad} failing, {warn} warnings")
sys.exit(1 if bad else 0)

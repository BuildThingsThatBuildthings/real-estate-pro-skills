#!/usr/bin/env python3
"""
Pull client context from Google Drive.

  drive_sync.py clients                          list configured clients
  drive_sync.py brand   --client <slug>          sync brand context (every run)
  drive_sync.py weekly  --client <slug> [--week 2026-W35]
  drive_sync.py all     --client <slug>          brand + weekly
  drive_sync.py inventory --client <slug>        classify what the weekly dump contains
  drive_sync.py deliver --client <slug> --from <dir> [--as <name>] [--yes]
                                                 push a finished set to 01 Waiting
  drive_sync.py clear   --client <slug> [--week ...] [--yes]
                                                 archive the drop folder after processing

Uses rclone, not the Drive MCP. The MCP returns file content as base64 into the
model context, which is wrong for a folder of photos and video. rclone syncs
binaries incrementally and runs unattended.

Brand context is synced on EVERY run because guardrails, voice and client cards
change between weeks and stale compliance rules are the expensive kind of stale.
"""
import argparse, json, os, re, subprocess, sys, shutil
from datetime import date, datetime

_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.realpath(os.path.join(_HERE, "..", "..", "post-bridge-schedule", "scripts")))
import config as _cfg  # noqa: E402

MEDIA_IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff"}
MEDIA_VIDEO = {".mp4", ".mov", ".m4v", ".avi", ".webm"}
DOCS = {".md", ".txt", ".pdf", ".doc", ".docx", ".csv", ".xlsx", ".rtf"}
AUDIO = {".m4a", ".mp3", ".wav", ".aac"}


def clients_cfg():
    return _cfg.load("clients")


def client(slug):
    c = clients_cfg()
    if slug not in c["clients"]:
        raise SystemExit(f"unknown client '{slug}'. configured: {', '.join(c['clients'])}")
    return c, c["clients"][slug]


def cache_dir(cfg, slug, *parts):
    root = os.path.expanduser(cfg.get("cache_root", "~/.cache/re-skills/clients"))
    p = os.path.join(root, slug, *parts)
    os.makedirs(p, exist_ok=True)
    return p


def rclone(remote, folder_id, dest, extra=None):
    if not shutil.which("rclone"):
        raise SystemExit("rclone not installed. brew install rclone, then `rclone config` a Drive remote.")
    if not folder_id or folder_id.startswith("PUT_"):
        raise SystemExit(f"folder id not configured for this client (got {folder_id!r})")
    cmd = ["rclone", "sync", remote, dest,
           "--drive-root-folder-id", folder_id,
           "--drive-export-formats", "md,txt",
           "--create-empty-src-dirs", "--stats-one-line"] + (extra or [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    noise = [l for l in r.stderr.splitlines()
             if l.strip() and "client_id" not in l and "NOTICE" not in l]
    if r.returncode != 0:
        raise SystemExit("rclone failed:\n" + "\n".join(noise[-8:]))
    return noise


def walk(d):
    for root, _, files in os.walk(d):
        for f in files:
            if f.startswith("."):
                continue
            yield os.path.join(root, f)


def classify(path):
    e = os.path.splitext(path)[1].lower()
    if e in MEDIA_IMAGE:
        return "image"
    if e in MEDIA_VIDEO:
        return "video"
    if e in AUDIO:
        return "audio"
    if e in DOCS:
        return "doc"
    return "other"


def cmd_clients(a):
    c = clients_cfg()
    for slug, v in c["clients"].items():
        d = v.get("drive", {})
        ready = all(not str(d.get(k, "")).startswith("PUT_") for k in ("brand_context_folder_id", "weekly_context_folder_id"))
        print(f"{slug:<24} {v.get('name',''):<26} {'configured' if ready else 'NEEDS FOLDER IDS'}"
              f"  posting={'on' if v.get('posting_enabled') else 'off'}")


def cmd_brand(a):
    cfg, cl = client(a.client)
    dest = cache_dir(cfg, a.client, "brand-context")
    rclone(cfg.get("rclone_remote", "gdrive:"), cl["drive"]["brand_context_folder_id"], dest)
    files = list(walk(dest))
    print(f"brand context -> {dest}")
    print(f"  {len(files)} files")
    for f in sorted(files):
        if f.lower().endswith((".md", ".txt")):
            print(f"    {os.path.relpath(f, dest)}")
    g = [f for f in files if "guardrail" in os.path.basename(f).lower()]
    print(f"  GUARDRAILS: {'found -> ' + os.path.relpath(g[0], dest) if g else 'NOT FOUND (compliance lint will use defaults only)'}")


def cmd_weekly(a):
    cfg, cl = client(a.client)
    week = a.week or date.today().strftime("%Y-W%V")
    dest = cache_dir(cfg, a.client, "weekly", week)
    rclone(cfg.get("rclone_remote", "gdrive:"), cl["drive"]["weekly_context_folder_id"], dest)
    print(f"weekly context [{week}] -> {dest}")
    _inventory(dest, cl)


def _inventory(root, cl):
    buckets = {}
    for f in walk(root):
        buckets.setdefault(classify(f), []).append(f)
    total_bytes = sum(os.path.getsize(f) for b in buckets.values() for f in b)
    print(f"  {sum(len(v) for v in buckets.values())} files, {total_bytes/1e6:.1f} MB")
    for k in ("image", "video", "audio", "doc", "other"):
        if buckets.get(k):
            print(f"    {k:<7} {len(buckets[k]):>3}")
    out = cl.get("output", {})
    print(f"  target this week: {out.get('photos_floor',5)}-{out.get('photos_cap',20)} photos, "
          f"{out.get('videos_floor',5)}-{out.get('videos_cap',20)} faceless videos")
    if not buckets.get("image") and not buckets.get("video"):
        print("  WARNING: no usable media in the dump. Ask before generating anything.")
    return buckets


def cmd_inventory(a):
    cfg, cl = client(a.client)
    week = a.week or date.today().strftime("%Y-W%V")
    dest = cache_dir(cfg, a.client, "weekly", week)
    if not os.path.isdir(dest) or not list(walk(dest)):
        raise SystemExit(f"nothing synced for {week}. run: drive_sync.py weekly --client {a.client}")
    print(f"weekly dump [{week}] at {dest}")
    _inventory(dest, cl)


def cmd_all(a):
    cmd_brand(a)
    print()
    cmd_weekly(a)


def safe_folder_name(s):
    """Drive tolerates most characters; humans scanning a folder list do not."""
    s = re.sub(r"[\\/:*?\"<>|]", "-", (s or "").strip())
    return re.sub(r"\s+", " ", s)[:120] or "delivery"


def cmd_deliver(a):
    """Push a finished set to the client's 01 Waiting folder.

    EVERY asset any skill in this bundle creates lands here and nowhere else.
    Waiting is the client's review queue -- they move it to Approved themselves.
    Nothing in this bundle writes to Approved, and nothing publishes."""
    cfg, cl = client(a.client)
    src = os.path.abspath(os.path.expanduser(a.src))
    if not os.path.isdir(src):
        raise SystemExit(f"not a directory: {src}")
    fid = cl["drive"].get("waiting_folder_id", "")
    if not fid or fid.startswith("PUT_"):
        raise SystemExit("waiting_folder_id not configured")
    files = list(walk(src))
    n = len(files)
    if not n:
        raise SystemExit(f"nothing to deliver: {src} has no files")
    # Each delivery gets its own dated folder. Loose files accumulating across
    # weeks in one review queue is how a client stops reviewing.
    label = safe_folder_name(a.label or f"{date.today().isoformat()} {os.path.basename(src.rstrip('/'))}")
    remote = cfg.get("rclone_remote", "gdrive:")
    if not a.yes:
        print(f"would upload {n} file(s) from {src}")
        print(f"                  to 01 Waiting / {label}")
        for p in sorted(files)[:12]:
            print(f"    {os.path.relpath(p, src)}")
        if n > 12:
            print(f"    ... and {n - 12} more")
        print("\nthis becomes visible to the client. re-run with --yes to send.")
        return
    cmd = ["rclone", "copy", src, f"{remote}{label}",
           "--drive-root-folder-id", fid, "--stats-one-line"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("rclone failed:\n" + r.stderr[-800:])
    print(f"delivered {n} file(s) to 01 Waiting / {label}")
    print("the client moves it to Approved. this bundle never does.")


def cmd_clear(a):
    """Archive the weekly drop folder in Drive once its contents are processed.

    Archive, not delete. These are the client's originals -- listing photos and
    walkthrough footage they may hold no other copy of -- and an irreversible
    delete triggered by a script is not a risk worth the tidiness.

    Refuses unless the same week has been synced locally first, so a drop folder
    can never be cleared before anyone has actually pulled what was in it."""
    cfg, cl = client(a.client)
    week = a.week or date.today().strftime("%Y-W%V")
    local = cache_dir(cfg, a.client, "weekly", week)
    pulled = list(walk(local)) if os.path.isdir(local) else []
    if not pulled:
        raise SystemExit(
            f"refusing to clear: nothing synced locally for {week}.\n"
            f"  run first: drive_sync.py weekly --client {a.client} --week {week}\n"
            f"  clearing a drop folder nobody has pulled would lose the client's originals.")
    fid = cl["drive"].get("weekly_context_folder_id", "")
    if not fid or fid.startswith("PUT_"):
        raise SystemExit("weekly_context_folder_id not configured")
    remote = cfg.get("rclone_remote", "gdrive:")
    dest = f"_archive/{week}"
    if not a.yes:
        print(f"would archive the drop folder into: {dest}")
        print(f"  {len(pulled)} file(s) were pulled locally for {week} -> {local}")
        print("  nothing is deleted; files move into the archive subfolder.")
        print("\nre-run with --yes to move them.")
        return
    cmd = ["rclone", "move", remote, f"{remote}{dest}",
           "--drive-root-folder-id", fid,
           "--exclude", "_archive/**", "--delete-empty-src-dirs", "--stats-one-line"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("rclone failed:\n" + r.stderr[-800:])
    print(f"drop folder cleared -> _archive/{week} (nothing deleted)")



# content-foundry expects an agent folder with Tier-1 files at its root.
# Drive brand context nests them under "my business/". Bridge the two without
# copying, so the Drive sync stays the single source of truth.
CF_TIER1 = ["about-me.md", "brand-voice.md", "working-style.md"]
CF_TIER2 = {"GUARDRAILS.md": "brand-context-compliance.md",
            "brand-context-visual.md": "brand-context-visual.md"}


def cmd_agent_folder(a):
    cfg, cl = client(a.client)
    src = cache_dir(cfg, a.client, "brand-context")
    if not list(walk(src)):
        raise SystemExit(f"brand context not synced. run: drive_sync.py brand --client {a.client}")
    dest = cache_dir(cfg, a.client, "agent")
    found = {}
    for f in walk(src):
        found.setdefault(os.path.basename(f), f)
    missing = []
    for name in CF_TIER1:
        s = found.get(name)
        if not s:
            missing.append(name); continue
        d = os.path.join(dest, name)
        if os.path.islink(d) or os.path.exists(d):
            os.remove(d)
        os.symlink(s, d)
    for src_name, cf_name in CF_TIER2.items():
        s = found.get(src_name)
        if not s:
            missing.append(f"{cf_name} (looked for {src_name})"); continue
        d = os.path.join(dest, cf_name)
        if os.path.islink(d) or os.path.exists(d):
            os.remove(d)
        os.symlink(s, d)
    # client and deal cards travel as-is
    for sub in ("my clients", "my deals"):
        s = os.path.join(src, sub)
        if os.path.isdir(s):
            d = os.path.join(dest, sub.replace(" ", "-"))
            if os.path.islink(d):
                os.remove(d)
            if not os.path.exists(d):
                os.symlink(s, d)
    print(f"agent folder -> {dest}")
    for f in sorted(os.listdir(dest)):
        print(f"    {f}")
    if missing:
        print("\n  MISSING, content-foundry will stop at setup:")
        for m in missing:
            print(f"    {m}")
        print("  brand-context-visual.md holds hexes, logo paths and fonts. Without it")
        print("  the composite stage cannot place brand colour or the logo.")
    return dest

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("clients").set_defaults(fn=cmd_clients)
    for name, fn in (("brand", cmd_brand), ("weekly", cmd_weekly), ("all", cmd_all), ("inventory", cmd_inventory)):
        p = sub.add_parser(name); p.add_argument("--client", required=True)
        p.add_argument("--week"); p.set_defaults(fn=fn)
    g = sub.add_parser("agent-folder"); g.add_argument("--client", required=True)
    g.add_argument("--week"); g.set_defaults(fn=cmd_agent_folder)
    d = sub.add_parser("deliver"); d.add_argument("--client", required=True)
    d.add_argument("--from", dest="src", required=True); d.add_argument("--yes", action="store_true")
    d.add_argument("--as", dest="label", help="folder name inside 01 Waiting; defaults to date + source dir")
    d.set_defaults(fn=cmd_deliver)
    cl_ = sub.add_parser("clear"); cl_.add_argument("--client", required=True)
    cl_.add_argument("--week"); cl_.add_argument("--yes", action="store_true")
    cl_.set_defaults(fn=cmd_clear)
    args = ap.parse_args()
    args.fn(args)

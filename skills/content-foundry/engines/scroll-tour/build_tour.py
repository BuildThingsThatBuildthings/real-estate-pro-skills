#!/usr/bin/env python3
"""Interactive Scroll Tour builder v2 — scroll-world engine + real-photo flights.

A listing microsite where scrolling flies room-to-room through the home, built on
the vendored scroll-world scrub engine (oso95/scroll-world, MIT).

Craft rules encoded here:
- Flights come from the listing's REAL photos (ffmpeg zoompan): supersampled 2x
  so motion is sub-pixel smooth, gentle dolly (1.10), 5s per room. No AI rooms,
  no credits.
- Connectors are built from the MOVING tails of adjacent flights joined with an
  xfade `zoomin` — a push-through-the-doorway move, seam-frame-identical by
  construction (the engine's seam rule).
- Every clip encoded to the engine's scrub spec: h264, crf 20, `-g 8`,
  `+faststart`, no audio. Miss the GOP setting and scrubbing stutters.
- The generated page themes the engine to the brand (Didot display, gold
  accents, navy glass chrome) and adds a staggered info-reveal: number →
  eyebrow → title → body → tags → CTA pop in sequence as the camera settles
  (per-section `linger`), and reverse out on scroll-back.

Usage:
    python build_tour.py --agent <agent-dir> --scenes <scenes.json> --out <dir>

Exit codes: 0 = ok, 1 = blocked, 2 = usage
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from brandkit import AgentBrand, BrandError  # noqa: E402

W, H, FPS = 1280, 720, 30
FLIGHT_S = 5.0          # per-room camera flight
TAIL_S = 0.8            # moving tail taken from each neighbor for a connector
XFADE_S = 0.7           # doorway push duration
ENCODE = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
          "-g", "8", "-movflags", "+faststart", "-an"]
VENDOR = Path(__file__).resolve().parent / "vendor"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"STOP: ffmpeg failed:\n{r.stderr[-900:]}", file=sys.stderr)
        sys.exit(1)


def flight(photo, out, direction):
    """Supersampled dolly + traverse inside the real photo (sub-pixel smooth)."""
    frames = int(FLIGHT_S * FPS)
    x = (f"(iw-iw/zoom)*(on/{frames - 1})" if direction > 0
         else f"(iw-iw/zoom)*(1-on/{frames - 1})")
    vf = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,"
          f"crop={W * 2}:{H * 2},"
          f"zoompan=z='1+0.10*on/{frames - 1}':x='{x}':"
          f"y='(ih-ih/zoom)/2':d={frames}:s={W}x{H}:fps={FPS}")
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(photo),
         "-vf", vf, "-t", str(FLIGHT_S), *ENCODE, str(out)])


def still_of(clip, out):
    run(["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-frames:v", "1",
         str(out)])


def last_frame(clip, out):
    run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", str(clip),
         "-frames:v", "1", str(out)])


PORTAL_S = 0.9          # each half of the doorway portal
PORTAL_Z = 3.4          # how deep the camera dives into the doorway
SPIN_RAD = 0.10         # subtle spiral (~6°) during the dive


def _focal_xy(fx, fy):
    """zoompan window position locked onto a focal point, clamped in-frame."""
    x = f"min(max({fx}*iw-(iw/zoom)/2,0),iw-iw/zoom)"
    y = f"min(max({fy}*ih-(ih/zoom)/2,0),ih-ih/zoom)"
    return x, y


def portal_half(frame_png, out, focal, mode):
    """One half of the doorway portal, generated from a real seam frame.

    mode='out': accelerating dive INTO the room's doorway focal point with a
    slight spiral, blooming to white — stepping through the door.
    mode='in':  the mirror — emerging from white deep inside the next room and
    pulling back to its full frame (exactly the frame its flight starts on).
    """
    frames = int(PORTAL_S * FPS)
    fx, fy = focal
    x, y = _focal_xy(fx, fy)
    if mode == "out":
        z = f"1+{PORTAL_Z - 1}*pow(on/{frames - 1},2.2)"        # slow → plunge
        rot = f"{SPIN_RAD}*pow(t/{PORTAL_S},2)"
        fade = f"fade=t=out:st={PORTAL_S - 0.32}:d=0.32:color=white"
    else:
        z = f"1+{PORTAL_Z - 1}*pow(1-on/{frames - 1},2.2)"      # plunge → settle
        rot = f"-{SPIN_RAD}*pow(1-t/{PORTAL_S},2)"
        fade = "fade=t=in:st=0:d=0.32:color=white"
    vf = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,"
          f"crop={W * 2}:{H * 2},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={int(W * 1.16)}x{int(H * 1.16)}:fps={FPS},"
          f"rotate=a='{rot}':fillcolor=black,"
          f"crop={W}:{H},"
          f"{fade}")
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(frame_png),
         "-vf", vf, "-t", str(PORTAL_S), *ENCODE, str(out)])


def connector(clip_a, clip_b, focal_a, out, tmp):
    """Doorway portal between rooms: dive into room A's actual doorway, bloom
    through white, emerge deep inside room B and settle onto its opening frame.

    Both halves are generated from the neighboring flights' REAL seam frames,
    so the seams are frame-identical: A's flight ends on the exact frame the
    dive starts from, and the emergence lands on the exact frame B's flight
    begins with. The camera never cuts — it walks through the door.
    """
    a_png = tmp / "seam-a.png"
    b_png = tmp / "seam-b.png"
    a_half = tmp / "half-a.mp4"
    b_half = tmp / "half-b.mp4"
    last_frame(clip_a, a_png)
    still_of(clip_b, b_png)
    portal_half(a_png, a_half, focal_a, "out")
    portal_half(b_png, b_half, (0.5, 0.5), "in")
    lst = tmp / "concat.txt"
    lst.write_text(f"file '{a_half.resolve()}'\nfile '{b_half.resolve()}'\n")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), *ENCODE, str(out)])
    for f in (a_png, b_png, a_half, b_half, lst):
        f.unlink()


PAGE_EXTRA_CSS = """
    /* ---- Content Foundry theme on top of the engine (engine CSS is @layer sw,
       so these unlayered rules always win). ---- */
    .sw-copy__title { font-family: var(--sw-font-display); font-weight: 400; }
    .sw-nav { background: color-mix(in srgb, var(--cf-navy) 62%, transparent);
      border-color: color-mix(in srgb, var(--cf-gold) 35%, transparent); }
    .sw-nav__item { color: color-mix(in srgb, #fff 72%, transparent); }
    .sw-nav__item:hover { color: #fff; }
    .sw-nav__item.is-active { color: var(--cf-navy); background: var(--cf-gold); }
    .sw-topcta { background: var(--cf-gold); color: var(--cf-navy); }
    .sw-brand__name { font-family: var(--sw-font-display); font-weight: 400;
      letter-spacing: .02em; }
    .sw-copy__tags li { background: transparent; border: 1px solid
      color-mix(in srgb, var(--cf-gold) 55%, transparent);
      color: var(--cf-gold); text-transform: uppercase;
      letter-spacing: .08em; font-weight: 500; font-size: .74rem; }
    .sw-route__label { background: color-mix(in srgb, var(--cf-navy) 80%, transparent);
      color: #fff; border-color: color-mix(in srgb, var(--cf-gold) 30%, transparent); }
    .sw-btn--primary { background: var(--cf-gold); color: var(--cf-navy); }
    .sw-btn--ghost { color: #fff; border-color:
      color-mix(in srgb, #fff 35%, transparent); }

    /* ---- Staggered info reveal ("information pops up") ----
       The engine drives .sw-copy's opacity from scroll; the tiny script below
       flips .is-live at a threshold and these transitions sequence the children.
       Scroll back and the sequence reverses. */
    .sw-copy > * { opacity: 0; transform: translateY(22px);
      transition: opacity .5s cubic-bezier(.22,.9,.24,1),
                  transform .6s cubic-bezier(.22,.9,.24,1); }
    .sw-copy.is-live > * { opacity: 1; transform: none; }
    .sw-copy.is-live > .sw-copy__num     { transition-delay: .02s; }
    .sw-copy.is-live > .sw-copy__eyebrow { transition-delay: .10s; }
    .sw-copy.is-live > .sw-copy__title   { transition-delay: .20s; }
    .sw-copy.is-live > .sw-copy__body    { transition-delay: .34s; }
    .sw-copy.is-live > .sw-copy__tags    { transition-delay: .46s; }
    .sw-copy.is-live > .sw-copy__cta     { transition-delay: .58s; }
    .sw-copy__tags li { opacity: 0; transform: translateY(12px) scale(.96);
      transition: opacity .4s ease, transform .45s cubic-bezier(.22,.9,.24,1); }
    .sw-copy.is-live .sw-copy__tags li { opacity: 1; transform: none; }
    .sw-copy.is-live .sw-copy__tags li:nth-child(1) { transition-delay: .50s; }
    .sw-copy.is-live .sw-copy__tags li:nth-child(2) { transition-delay: .60s; }
    .sw-copy.is-live .sw-copy__tags li:nth-child(3) { transition-delay: .70s; }
    /* gold rule that draws in under the title */
    .sw-copy__title::after { content: ""; display: block; width: 0; height: 3px;
      margin-top: 18px; background: var(--cf-gold);
      transition: width .6s cubic-bezier(.22,.9,.24,1) .30s; }
    .sw-copy.is-live .sw-copy__title::after { width: 84px; }
"""

PAGE_EXTRA_JS = """
    // Staggered reveal driver: the engine scrubs .sw-copy opacity from scroll;
    // we quantize that into .is-live so the CSS sequence above plays (and
    // reverses on scroll-back). Hysteresis stops flicker at the threshold.
    (function () {
      const copies = Array.from(document.querySelectorAll('.sw-copy'));
      const live = new WeakMap();
      (function watch() {
        for (const c of copies) {
          const o = parseFloat(c.style.opacity || '0');
          const was = live.get(c) || false;
          if (!was && o > 0.55) { c.classList.add('is-live'); live.set(c, true); }
          else if (was && o < 0.25) { c.classList.remove('is-live'); live.set(c, false); }
        }
        requestAnimationFrame(watch);
      })();
    })();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--scenes", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-demo", action="store_true")
    ap.add_argument("--flights-dir", default=None,
                    help="dir of per-room i2v parallax clips (s1.mp4..sN.mp4); used instead of zoompan when present")
    args = ap.parse_args()

    try:
        brand = AgentBrand(args.agent)
        colors = brand.colors
        required = brand.required_strings()
    except BrandError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 1
    if brand.demo and not args.allow_demo:
        print(f"STOP: {brand.slug} is a DEMO persona — listing tours require the "
              f"presenting agent's folder (or --allow-demo).", file=sys.stderr)
        return 1

    missing = [k for k, v in required.items() if v is None]
    if missing:
        print(f"STOP: compliance strings not filled: {', '.join(missing)}",
              file=sys.stderr)
        return 1
    design = brand.design

    cfg = json.loads(Path(args.scenes).read_text())
    scenes = cfg["scenes"]
    out = Path(args.out)
    assets = out / "assets"
    vids = assets / "vid"
    vids.mkdir(parents=True, exist_ok=True)

    navy = colors["primary"]
    gold = colors.get("accent", "#a88c60")

    # Flights + stills
    sections = []
    for i, s in enumerate(scenes):
        photo = Path(s["photo"])
        if not photo.exists():
            print(f"STOP: photo not found: {photo}", file=sys.stderr)
            return 1
        sid = f"room{i + 1}"
        clip = vids / f"{sid}.mp4"
        i2v = Path(args.flights_dir) / f"s{i + 1}.mp4" if args.flights_dir else None
        if i2v and i2v.exists():
            # real parallax flight: re-encode to the engine's scrub spec
            run(["ffmpeg", "-y", "-v", "error", "-i", str(i2v),
                 "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
                 *ENCODE, str(clip)])
        else:
            flight(photo, clip, direction=1 if i % 2 == 0 else -1)
        still_of(clip, assets / f"{sid}.webp")
        feats = [f.strip() for f in s["feature"].split(",")]
        sections.append({
            "id": sid, "label": s["room"],
            "still": f"assets/{sid}.webp", "clip": f"assets/vid/{sid}.mp4",
            "accent": gold,
            "scroll": 1.5, "linger": 0.45,   # settle mid-room while info reveals
            "eyebrow": cfg.get("subline", ""),
            "title": s["room"],
            "body": s["feature"] + ".",
            "tags": feats[:3],
        })
    sections[-1]["cta"] = {
        "primary": {"label": "Schedule a showing", "href": "#"},
        "secondary": {"label": brand.slug.replace('-', ' ').title(), "href": "#top"},
    }

    # Doorway-portal connectors: dive into each room's real doorway focal.
    connectors = []
    for i in range(len(scenes) - 1):
        conn = vids / f"conn{i + 1}.mp4"
        focal = tuple(scenes[i].get("focal", [0.5, 0.5]))
        connector(vids / f"room{i + 1}.mp4", vids / f"room{i + 2}.mp4",
                  focal, conn, vids)
        connectors.append(f"assets/vid/conn{i + 1}.mp4")

    fonts_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
    if (fonts_dir / "PlayfairDisplay.ttf").exists():
        shutil.copy2(fonts_dir / "PlayfairDisplay.ttf", assets / "font-display.ttf")
    if (fonts_dir / "SourceSans3.ttf").exists():
        shutil.copy2(fonts_dir / "SourceSans3.ttf", assets / "font-sans.ttf")
    shutil.copy2(VENDOR / "scrub-engine.js", out / "scrub-engine.js")
    shutil.copy2(VENDOR / "LICENSE", out / "LICENSE-scroll-world")

    agent_name = brand.slug.replace("-", " ").title()
    config = {
        "brand": {"name": agent_name, "href": "#top"},
        "cta": {"label": "Schedule a showing", "href": "#finale"},
        "hint": "scroll to walk through",
        "diveScroll": 1.5, "connScroll": 0.9,
        "sections": sections,
        "connectors": connectors,
    }
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>{cfg['headline']} — {agent_name}</title>
  <meta name="description" content="Scroll to walk through {cfg['headline']}." />
  <link rel="preload" as="image" href="assets/room1.webp" />
  <style>
    @font-face {{ font-family: "CF Serif"; src: url("assets/font-display.ttf");
                  font-display: swap; }}
    @font-face {{ font-family: "CF Sans"; src: url("assets/font-sans.ttf");
                  font-weight: 200 900; font-display: swap; }}
    :root, .sw-root {{
      --cf-navy: {navy};
      --cf-gold: {gold};
      --sw-bg: {navy};
      --sw-ink: {colors.get('text-on-dark', '#ffffff')};
      --sw-ink-soft: #9fb0c0;
      --sw-accent: {gold};
      --sw-font-display: {("\"CF Sans\", Helvetica, Arial, sans-serif" if design.get("display_type") == "sans" else '\"CF Serif\", Didot, \"Hoefler Text\", Georgia, serif')};
      --sw-font-body: {("Helvetica, Arial, sans-serif" if design.get("display_type") == "sans" else 'Georgia, \"Times New Roman\", serif')};
    }}
    body {{ background: {navy}; margin: 0; }}
    .cf-compliance {{
      position: fixed; left: 0; right: 0; bottom: 0; z-index: 60;
      padding: 10px 18px; font: 12px/1.5 Helvetica, Arial, sans-serif;
      color: {colors.get('text-on-dark', '#ffffff')}; opacity: 0.85;
      background: {navy}e6; text-align: center;
    }}
{PAGE_EXTRA_CSS}
  </style>
</head>
<body>
  <div id="top"></div>
  <div id="world"></div>
  <div class="cf-compliance">
    {required['license']} &nbsp;·&nbsp; {required['disclosure']} &nbsp;·&nbsp; {required['fair_housing']}
  </div>
  <script src="scrub-engine.js"></script>
  <script>
    mountScrollWorld(document.getElementById('world'), {json.dumps(config, indent=2)});
{PAGE_EXTRA_JS}
  </script>
</body>
</html>
"""
    (out / "index.html").write_text(html)
    total_mb = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    print(f"SCROLL TOUR v2 -> {out}")
    print(f"  {len(sections)} rooms, {len(connectors)} doorway connectors, "
          f"{total_mb:.1f} MB total")
    return 0


if __name__ == "__main__":
    sys.exit(main())

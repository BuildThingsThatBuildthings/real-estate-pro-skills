#!/usr/bin/env python3
"""Outreach page builder — the outbound spec-sample deliverable.

Assembles a single self-contained landing page for a prospect agent: their
videos as the main event, the stills, the interactive scroll tour, and — when
the agent folder declares a headshot — their face in the header and in the
closing section. Brand tokens, design language, and compliance all come from
the agent folder via brandkit, same as every other engine.

Usage:
    python build_page.py --agent <agent-dir> --scenes <scenes.json> \\
        --videos-dir <dir with walkthrough|salesbrief|teaser.mp4> \\
        --stills <img> [<img> ...] [--tour-dir <built tour dir>] \\
        [--contact "phone or line"] [--prepared-for "display name"] --out <dir>

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

VIDEO_META = {
    "walkthrough": ("Digital Walkthrough", "narrated room-by-room"),
    "salesbrief": ("Digital Sales Brief", "feature cards, offered price"),
    "teaser": ("Listing Teaser", "hook cut for Reels & Stories"),
}


def poster(video, out):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1.5", "-i",
                    str(video), "-frames:v", "1", str(out)], check=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--scenes", required=True)
    ap.add_argument("--videos-dir", required=True)
    ap.add_argument("--stills", nargs="+", default=[])
    ap.add_argument("--tour-dir", default=None)
    ap.add_argument("--contact", default=None)
    ap.add_argument("--prepared-for", default=None)
    ap.add_argument("--allow-demo", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        brand = AgentBrand(args.agent)
        colors = brand.colors
        required = brand.required_strings()
    except BrandError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 1
    if brand.demo and not args.allow_demo:
        print(f"STOP: {brand.slug} is a DEMO persona.", file=sys.stderr)
        return 1
    missing = [k for k, v in required.items() if v is None]
    if missing:
        print(f"STOP: compliance strings not filled: {', '.join(missing)}",
              file=sys.stderr)
        return 1

    design = brand.design
    cfg = json.loads(Path(args.scenes).read_text())
    out = Path(args.out)
    media = out / "media"
    media.mkdir(parents=True, exist_ok=True)

    # media staging
    videos = []
    for key, (title, sub) in VIDEO_META.items():
        src = Path(args.videos_dir) / f"{key}.mp4"
        if src.exists():
            shutil.copy2(src, media / f"{key}.mp4")
            poster(src, media / f"poster-{key}.jpg")
            videos.append((key, title, sub))
    stills = []
    for i, s in enumerate(args.stills, 1):
        sp = Path(s)
        if sp.exists():
            shutil.copy2(sp, media / f"still-{i}.jpg")
            stills.append(f"media/still-{i}.jpg")
    tour_href = None
    if args.tour_dir and Path(args.tour_dir).exists():
        if (out / "tour").exists():
            shutil.rmtree(out / "tour")
        shutil.copytree(args.tour_dir, out / "tour")
        tour_href = "tour/"
    headshot = None
    if brand.headshot_path:
        shutil.copy2(brand.headshot_path, media / "headshot.jpg")
        headshot = "media/headshot.jpg"
    fonts = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
    sans_face = ""
    if (fonts / "SourceSans3.ttf").exists():
        shutil.copy2(fonts / "SourceSans3.ttf", media / "font-sans.ttf")
        sans_face = ('@font-face { font-family: "CF Sans"; '
                     'src: url("media/font-sans.ttf"); font-weight: 200 900; }')
    if (fonts / "PlayfairDisplay.ttf").exists():
        shutil.copy2(fonts / "PlayfairDisplay.ttf", media / "font-serif.ttf")
        sans_face += ('\n    @font-face { font-family: "CF Serif"; '
                      'src: url("media/font-serif.ttf"); }')

    is_sans = design.get("display_type") == "sans"
    disp = ('"CF Sans", "Helvetica Neue", Helvetica, sans-serif' if is_sans
            else '"CF Serif", Didot, Georgia, serif')
    disp_weight = "800" if is_sans else "400"
    agent_name = brand.slug.replace("-", " ").title()
    prepared_for = args.prepared_for or agent_name
    primary = colors["primary"]
    accent = colors.get("accent", primary)
    secondary = colors.get("secondary", primary)

    header_headshot = (f'<img class="hs" src="{headshot}" alt="{prepared_for}" />'
                       if headshot else "")
    video_cards = "\n".join(
        f'''<div class="card"><video controls preload="none"
          poster="media/poster-{k}.jpg" src="media/{k}.mp4"></video>
          <div class="meta"><b>{t}</b><span>{sub}</span></div></div>'''
        for k, t, sub in videos)
    stills_imgs = "\n".join(f'<img src="{s}" alt="listing still" />' for s in stills)
    tour_block = (f'''
    <section class="section">
      <h2>Walk the listing yourself</h2>
      <div class="tourbox">
        <p>An interactive scroll tour — real camera flights through the listing,
        room to room.</p>
        <a class="btn" href="{tour_href}">Open the tour →</a>
      </div>
    </section>''' if tour_href else "")
    closing_headshot = (f'<img class="hs-big" src="{headshot}" alt="{prepared_for}" />'
                        if headshot else "")
    contact_line = f'<p class="contact">{args.contact}</p>' if args.contact else ""

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Prepared for {prepared_for} — listing content sample</title>
<style>
    {sans_face}
    :root {{ --primary:{primary}; --accent:{accent}; --secondary:{secondary}; }}
    * {{ box-sizing:border-box; margin:0; }}
    body {{ background:var(--primary); color:#fff;
           font:17px/1.6 {'Helvetica, Arial, sans-serif' if is_sans else 'Georgia, serif'}; }}
    .wrap {{ max-width:1180px; margin:0 auto; padding:0 24px; }}
    .topbar {{ display:flex; align-items:center; gap:16px; padding:26px 0; }}
    .hs {{ width:64px; height:64px; border-radius:50%; object-fit:cover;
          border:3px solid var(--accent); }}
    .topname {{ font-family:{disp}; font-weight:{disp_weight}; font-size:1.35rem; }}
    .topname small {{ display:block; font-size:.68rem; opacity:.7; letter-spacing:.12em;
                     font-weight:500; }}
    .ribbon {{ margin-left:auto; background:var(--accent); color:#fff; font-weight:700;
              font-family:Helvetica,Arial,sans-serif; font-size:.78rem; letter-spacing:.1em;
              text-transform:uppercase; padding:9px 18px; border-radius:999px; }}
    header.hero {{ padding:56px 0 26px; text-align:center; }}
    .eyebrow {{ color:var(--accent); letter-spacing:.22em; text-transform:uppercase;
               font-size:13px; font-family:Helvetica,Arial,sans-serif; font-weight:700; }}
    h1 {{ font-family:{disp}; font-weight:{disp_weight};
         font-size:clamp(2.3rem,5.4vw,4rem); margin:16px 0 10px; }}
    .sub {{ color:#c8cfdd; max-width:64ch; margin:0 auto; }}
    .blockrule {{ width:64px; height:16px; background:var(--accent); margin:28px auto 0; }}
    h2 {{ font-family:{disp}; font-weight:{disp_weight};
         font-size:clamp(1.5rem,3vw,2.1rem); margin:0 0 18px; }}
    .section {{ padding:48px 0 6px; }}
    .videos {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
              gap:26px; align-items:start; }}
    .card {{ background:{secondary}; border-radius:10px; overflow:hidden; }}
    .card video {{ width:100%; display:block; aspect-ratio:9/16; background:#000; }}
    .card .meta {{ padding:14px 16px 18px; }}
    .card .meta b {{ font-family:{disp}; font-weight:{disp_weight};
                    font-size:1.15rem; display:block; }}
    .card .meta span {{ color:#dfe5f0; font-size:.9rem;
                       font-family:Helvetica,Arial,sans-serif; }}
    .stills {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
              gap:18px; }}
    .stills img {{ width:100%; border-radius:8px; display:block; }}
    .tourbox {{ background:{secondary}; border-radius:10px; padding:30px; display:flex;
               flex-wrap:wrap; gap:22px; align-items:center; justify-content:space-between; }}
    .btn {{ display:inline-block; background:var(--accent); color:#fff; text-decoration:none;
           font-weight:700; font-family:Helvetica,Arial,sans-serif; padding:14px 26px;
           border-radius:999px; }}
    .closing {{ text-align:center; padding:70px 0 30px; }}
    .hs-big {{ width:200px; height:200px; border-radius:50%; object-fit:cover;
              border:6px solid var(--accent); margin-bottom:26px; }}
    .closing h2 {{ margin-bottom:8px; }}
    .closing p {{ color:#c8cfdd; max-width:56ch; margin:0 auto; }}
    .contact {{ margin-top:16px !important; color:#fff !important; font-weight:600; }}
    footer {{ padding:44px 0 60px; color:#9aa4b8; font-size:.84rem; text-align:center;
             font-family:Helvetica,Arial,sans-serif; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      {header_headshot}
      <div class="topname">{prepared_for}
        <small>{required['disclosure'].split('|')[-1].strip().upper()}</small></div>
      <div class="ribbon">Sample — prepared for {prepared_for.split()[0]}</div>
    </div>

    <header class="hero">
      <div class="eyebrow">{cfg.get('subline', '')}</div>
      <h1>{cfg.get('headline', '')}</h1>
      <p class="sub">Every asset below was produced from this listing's real photos and
      details, in your brand — narration, music, and compliance included. This is what
      your listings could look like, every time.</p>
      <div class="blockrule"></div>
    </header>

    <section class="section">
      <h2>The videos</h2>
      <div class="videos">
{video_cards}
      </div>
    </section>

    <section class="section">
      <h2>Channel-ready stills</h2>
      <div class="stills">
{stills_imgs}
      </div>
    </section>
{tour_block}

    <section class="closing">
      {closing_headshot}
      <h2>Made for {prepared_for}</h2>
      <p>Everything here carries your name, your brokerage's brand, and your license —
      generated from one folder of listing photos. Imagine this for every listing you take.</p>
      {contact_line}
    </section>

    <footer>
      {required['license']} &nbsp;·&nbsp; {required['disclosure']} &nbsp;·&nbsp;
      {required['fair_housing']}<br/>
      Sample for review — not published. Listing imagery courtesy of the listing brokerage.
    </footer>
  </div>
</body>
</html>
"""
    (out / "index.html").write_text(html)
    total_mb = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    print(f"OUTREACH PAGE -> {out}")
    print(f"  {len(videos)} videos, {len(stills)} stills, "
          f"tour: {'yes' if tour_href else 'no'}, headshot: {'yes' if headshot else 'no'}, "
          f"{total_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

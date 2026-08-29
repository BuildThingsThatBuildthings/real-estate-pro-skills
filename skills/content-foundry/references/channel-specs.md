---
version: 1
researched_on: 2026-07-28
note: >
  DATA, NOT CODE. Platform specs drift faster than anything else in this product.
  Update this file independently of a skill release. Agents may override per preference.
---

# Channel Specs

Dimensions, safe zones, and caption rules per platform. `composite.py` reads the safe zones;
`export.py` reads the dimensions. Stills are Phase 1; video specs are here for Phase 2.

## Safe-zone principle

A safe zone is where **brand-critical elements may be placed**: logo, headline, license number,
disclosure. Platform chrome (usernames, action buttons, captions, progress bars) overlays the
edges and will cover anything placed there. Compliance text covered by UI is a compliance failure,
so `composite.py` treats safe zones as hard constraints, not suggestions.

---

## Instagram

**Stills**
| Format | Dimensions | Aspect |
|---|---|---|
| Feed square | 1080 × 1080 | 1:1 |
| Feed portrait (preferred) | 1080 × 1350 | 4:5 |
| Story / Reel cover | 1080 × 1920 | 9:16 |
| Carousel | 1080 × 1350 | 4:5, up to 10 slides |

**Safe zones (1080 × 1920 vertical):** top ≥ 108px, bottom ≥ 320px (≥ 480px if caption-heavy),
left ≥ 60px, right ≥ 120px.
**Safe zones (1080 × 1350 feed):** ≥ 60px all edges; keep the bottom 120px clear of critical text —
feed captions and the "more" truncation crowd it.

**Video:** 1080 × 1920, 30fps, 9:16, 15–60s. h264 / yuv420p, CRF 18, 8M bitrate, 256k audio.

**Caption rules**
- First line = keyword + payoff, ≤ 100 characters. Public posts are indexed by Google.
- 2,200 character limit; only the first ~125 show before "more".
- Keywords should appear in the caption, on-screen, and spoken.
- Sends-per-reach is the top discovery signal — write for the DM share, not the like.
- Vary layouts between posts. Templated output is penalized by originality detection.
- AI-generated imagery requires in-app disclosure. Never strip C2PA / SynthID metadata.

---

## Facebook

**Stills**
| Format | Dimensions | Aspect |
|---|---|---|
| Feed | 1200 × 630 | 1.91:1 |
| Feed square | 1080 × 1080 | 1:1 |
| Story | 1080 × 1920 | 9:16 |

**Safe zones (1080 × 1920 story):** top ≥ 250px, bottom ≥ 250px, sides ≥ 60px.
**Feed:** ≥ 40px all edges.
**Video:** 1080 × 1920 or 1280 × 720, 30fps, up to 90s for Reels.

**Caption rules**
- 63,206 character limit; ~80 characters show before truncation.
- Link previews pull the 1200 × 630 image — size listing links accordingly.
- Local/community framing outperforms broadcast framing for real estate.

---

## LinkedIn

**Stills**
| Format | Dimensions | Aspect |
|---|---|---|
| Feed (preferred) | 1200 × 1200 | 1:1 |
| Feed landscape | 1200 × 627 | 1.91:1 |
| Document / carousel | 1080 × 1350 | 4:5, PDF |

**Safe zones:** ≥ 64px all edges. LinkedIn crops previews aggressively on mobile — keep the logo and
license text well inside.
**Video:** 1080 × 1920 or 1920 × 1080, 30fps, 30s–5min.

**Caption rules**
- 3,000 character limit; ~140 characters before "see more".
- No hashtag stuffing; 3–5 maximum, or none.
- Professional register — this is the channel where "just sold!!" underperforms a market insight.
- External links suppress reach; put the URL in the first comment.

---

## TikTok

| Format | Dimensions | Aspect |
|---|---|---|
| Video | 1080 × 1920 | 9:16 |
| Cover | 1080 × 1920 | 9:16 |

**Safe zones:** top ≥ 130px, bottom ≥ 480px (caption + UI stack is tall), left ≥ 60px,
right ≥ 140px. The right rail is the most commonly violated zone — never place a logo there.
**Video:** 1080 × 1920, 30fps, 15–180s.

**Caption rules**
- 2,200 character limit; ~100 characters visible.
- Hook must land in the first 1.5 seconds and vary visually between variants.
- Real estate compliance text is easy to lose here — place it top-area, not bottom.

---

## YouTube

| Format | Dimensions | Aspect |
|---|---|---|
| Thumbnail | 1280 × 720 | 16:9 |
| Short | 1080 × 1920 | 9:16 |
| Standard video | 1920 × 1080 | 16:9 |

**Safe zones (Shorts):** top ≥ 120px, bottom ≥ 420px, sides ≥ 60px.
**Thumbnail:** ≥ 60px all edges; bottom-right 200 × 80px is covered by the duration stamp.

**Caption rules**
- Title ≤ 100 characters, front-load the keyword.
- Description 5,000 characters; first 150 show in search.
- Thumbnail text ≤ 5 words, legible at 168 × 94px.

---

## X

| Format | Dimensions | Aspect |
|---|---|---|
| Single image | 1600 × 900 | 16:9 |
| Square | 1080 × 1080 | 1:1 |
| Video | 1280 × 720 | 16:9 |

**Safe zones:** ≥ 48px all edges. Timeline previews crop to 16:9 — critical elements must survive
that crop.

**Caption rules**
- 280 characters standard.
- Links consume characters and suppress reach — prefer no URL in the post body.

---

## Export defaults

| Channel | Default still | Format | Max size |
|---|---|---|---|
| Instagram | 1080 × 1350 | JPEG q90 | 8 MB |
| Facebook | 1200 × 630 | JPEG q90 | 8 MB |
| LinkedIn | 1200 × 1200 | PNG or JPEG q90 | 5 MB |
| TikTok | 1080 × 1920 | JPEG q90 | 8 MB |
| YouTube | 1280 × 720 | JPEG q90 | 2 MB |
| X | 1600 × 900 | JPEG q90 | 5 MB |

**Hard guard:** any video variant over 300 MB is rejected before Post Bridge upload — YouTube,
LinkedIn, and X silently drop oversized media rather than erroring.

## Naming convention

```
[AGENT]_[TYPE]_[descriptor]_[YYYY-MM-DD]_[channel].[ext]
```
Example: `riley-shore_new-listing_lakefront-craftsman_2026-07-28_ig.jpg`

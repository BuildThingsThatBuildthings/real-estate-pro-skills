# Prospect Research — research-drafted foundations (the outreach flow)

Normal production assumes a full Context Kit exists. **Outreach spec samples** (content built to
win an agent you haven't met) use this flow instead: **research → create.** The research drafts
the brand AND drives the design — never reuse a demo or another agent's folder. The demo guard
enforces this: demo personas refuse listing content.

## Invocation

`setup --from-research {profile urls}` — e.g. the agent's brokerage profile, team site,
public social pages.

## The protocol

1. **Identity + market.** Name, title, team/brokerage, office address, market area, phone,
   license number (often public on profiles), designations, years.
2. **Brand system.** The brokerage's real palette extracted from their SERVED assets (logo
   SVG fills, page styles) — never from memory. Personal/team branding on top.
3. **Voice evidence.** Their actual bio, taglines, testimonial language. Tier-1 voice files are
   drafted FROM this evidence and cite it.
4. **Design axes.** From the brand system + persona: energy (bold↔quiet), register
   (corporate↔boutique), temperature (warm↔crisp) → `brand-context-design.md` tokens
   (layout family, display type, motion energy, accent treatment). A RE/MAX-bold sample and a
   boutique sample must be STRUCTURALLY different, not recolored.
5. **Provenance.** Every drafted file carries `research_drafted: true` + source URLs + access
   date, and the folder requires agent confirmation before production (non-sample) use.
6. **Headshot.** Pull the agent's profile photo (their public headshot) into
   `assets/headshot.jpg` and declare it in the visual file — endcards and outreach pages
   feature it automatically. The agent IS the brand.
7. **Wordmark.** Generated in the researched palette with bundled fonts. Never reproduce a
   brokerage's trademarked mark (logos, balloons, crests) inside generated assets — carry the
   brand through color, type, and geometry.

## Rules

- Spec samples stay LOCAL until the agent consents to anything public.
- License/compliance strings: real values only when public; otherwise `[PENDING]` (blocks
  production output by design).
- Facts on assets: the listing's own data only — research grounds voice and design, never
  invents claims.
- The distinctness gate (brand lint) fails output whose palette matches a demo fixture.

## The outreach deliverable

`python engines/outreach/build_page.py --agent agents/{slug} --scenes {run}/scenes.json
--videos-dir {run}/working --stills ... --tour-dir {run}/scroll-tour
--contact "..." --out {run}/outreach/`

One self-contained page: the agent's headshot in the header, the three videos as the main
event, stills, the interactive tour, and a closing section with their face and a
made-for-you message. Serve locally or host privately; send the link as the outreach hook.

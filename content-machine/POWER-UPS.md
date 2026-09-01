# Power-Ups

Optional upgrades for the Content Machine. **None of these are required.** The machine runs completely on the core install: your AI's desktop app, the Google Drive connector, and the four context cards.

Read this only when the owner has said they want to hear about power-ups. Offer them one at a time, plainly, and take "no" the first time. Every power-up degrades gracefully — if it is absent, the machine still runs and the fallback below applies.

---

## Power-Up 1 — An agent browser

**What it is:** a browser your AI can drive — Claude in Chrome, or an agent browser like Comet or an equivalent your AI offers.

**What it unlocks:** Station 7 (Learn). Instead of you copying your post numbers into the chat every week, the machine can open your accounts in the browser you are already signed into, read what actually happened, and write the production brief itself.

**How to get it:** turn it on inside your AI's own settings (for Claude, the "Claude in Chrome" extension). Follow the AI app's own setup screens. Nothing to type, nothing to configure by hand.

**Rules that still apply:** the machine reads. It never posts, never clicks "publish," never replies to anyone, and never logs into anything for you.

**Without it:** you paste a screenshot or a short list of your numbers once a week. Two minutes. The machine works exactly the same.

---

## Power-Up 2 — The video lane (Remotion + HyperFrames)

**What it is:** a rendering toolchain that turns the machine's faceless-video scripts into finished, branded video files instead of scripts you hand to an editor or an app.

**Honest label:** this is the one power-up that is genuinely technical. It runs on the advanced lane of this repo (Claude Code, for operators and assistants comfortable with a terminal). If that is not you, skip it without guilt.

**Where it lives:** the advanced lane of this repository — see the main README's "Advanced: Claude Code lane" section and `skills/content-foundry`.

**Without it:** Station 4 still produces everything that matters — the script, the first frame, the on-screen text, the shot list. You (or CapCut, Canva, or any editor) turn it into the file. Most owners never need more than this.

---

## Power-Up 3 — Image and video generation accounts (Higgsfield, Gemini, OpenAI)

**What it is:** if you already pay for an image or video generation service — Higgsfield, Google's Gemini, OpenAI — the machine can use it for branded stills and b-roll instead of relying only on your camera roll.

**Only if you already have the account.** Do not sign up for anything to use the Content Machine.

**How to connect it:** through your AI app's own connector or integration settings — the same place you turned on Google Drive. **Never paste an API key, password, or account credential into a chat.** If a setup screen asks for a key, do it in that service's own website, not here.

**Rules that still apply:** generated imagery follows the same guardrails — no fake property photos presented as real, no invented rooms or renovations on a real listing, rights and disclosure rules from `guardrails.md` apply to generated media too.

**Without it:** stills come from your camera roll and simple typography. That is the default, and it is enough — a real photo of a real place beats a generated one for trust anyway.

---

## The order that makes sense

1. Run the core machine for two or three weeks first. No power-ups.
2. If pasting weekly numbers annoys you → Power-Up 1.
3. If you are approving lots of video scripts you never turn into video → Power-Up 2 (or an assistant who runs it).
4. If you already pay for a generation tool → Power-Up 3.

The machine compounds because of the cards and the weekly loop, not because of the tools bolted onto it.

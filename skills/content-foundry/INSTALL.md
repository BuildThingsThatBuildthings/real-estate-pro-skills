# Content Foundry — Install Guide

Written for someone who has never opened a terminal. Total time: about 15 minutes, most of it
one download.

## What you're installing

A content engine that runs inside Claude Code. You set up your brand once, then: drop listing
photos into a folder, say what you want ("new listing announcement"), and get finished,
branded, compliance-checked posts — sized for Instagram, Facebook, and LinkedIn — plus optional
video and scheduling.

## Step 1 — Install Claude Code (one time)

1. Go to **claude.com/claude-code** and download the desktop app for your computer
   (Mac or Windows). Install it like any other app.
2. Open it and sign in with your Claude account (your brokerage may provide one).
3. That's it. You will never need to type commands — you talk to it in plain English.

## Step 2 — Install Content Foundry (one time)

1. Your brokerage gives you a folder (or zip) called `content-foundry`.
2. Put it here:
   - **Mac:** `Home → .claude → skills → content-foundry`
   - If you can't see the `.claude` folder in Finder, press **Cmd+Shift+.** (period) to show
     hidden folders.
3. Restart Claude Code. Type `/content-foundry` — if it responds, you're installed.

## Step 3 — Set up your brand (one time, ~10 minutes)

Say: **"Set up my brand in Content Foundry."**

It will interview you — your name, your market, how you sound, your colors, your logo file,
and your brokerage's required license/disclosure wording. Have these handy:

- Your logo (a PNG file is ideal; a brand-guide PDF also works)
- Your license number
- The exact disclosure line your brokerage requires (ask your broker — Content Foundry will
  not write legal wording for you)

Everything is saved in one folder with your name on it. You never re-explain your brand.

## Step 4 — Make your first post (~5 minutes)

1. Make a folder anywhere (Desktop is fine). Drop in your listing photos — and anything else:
   the MLS sheet PDF, a walkthrough video, a link in a text file. Messy is fine.
2. Say: **"New listing announcement from the folder on my Desktop."**
3. It shows you a short brief first — the plan for the post. Say "go" or ask for changes.
4. Finished, branded, sized images land in an `output` folder. Every one carries your logo,
   your exact colors, your license line, and your brokerage's disclosure — checked by software,
   not by memory.

## What can go wrong (and what it means)

| It says | It means |
|---|---|
| "brand file is still a blank template" | Step 3 isn't finished — run the setup interview |
| "logo path does not resolve" | The logo file moved — put it back in your brand folder |
| "compliance strings not filled" | Your brokerage's disclosure wording is missing — it will never invent it |
| "headline does not fit" | Your headline is too long for the format — it will ask for shorter copy instead of shrinking text into illegibility |

## Video and scheduling (optional)

- **Video** needs one extra install the first time — Content Foundry will walk you through it
  when you first ask for a video (under the hood: `cd engines/remotion && npm install`, about a
  minute). If you skip it, you still get image versions of everything.
- **Scheduling** connects to Post Bridge (post-bridge.com). Everything is created as a **draft
  you approve** — nothing ever publishes by itself.

## Support

Contact your brokerage's Content Foundry administrator. This tool assists with compliance
placement; your brokerage owns the wording. It is not legal advice.

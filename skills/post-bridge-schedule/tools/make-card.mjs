#!/usr/bin/env node
// Build an image card for platforms that reject video (Google Business, etc).
//
//   make-card.mjs <mediaId|localFile> <out.jpg> "HEADLINE" "subline" [seekSeconds]
//
// Crops the UPPER portion of a vertical frame. On a vertical talking-head shot
// the subject's head and any on-screen content live there; the middle band is
// table and legs and the bottom carries burned-in captions. Never center crop.
//
// Pass an empty headline for sources that are already designed cards: the whole
// frame is fitted onto the brand background with no overprinting.
//
// Brand tokens come from config/brand.json.
import fs from 'node:fs/promises';
import fss from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
const run = promisify(execFile);

const HERE = path.dirname(new URL(import.meta.url).pathname);
function findConfig(name) {
  const env = process.env.RE_SKILLS_CONFIG_DIR;
  if (env) { const p = path.join(env.replace(/^~/, os.homedir()), `${name}.json`); if (fss.existsSync(p)) return p; }
  for (let up = 1; up <= 5; up++) {
    const p = path.resolve(HERE, ...Array(up).fill('..'), 'config', `${name}.json`);
    if (fss.existsSync(p)) return p;
  }
  return null;
}
const brandPath = findConfig('brand');
if (!brandPath) { console.error('missing config/brand.json (copy brand.example.json)'); process.exit(1); }
const brand = JSON.parse(await fs.readFile(brandPath, 'utf8'));
const C = brand.card || {};
const W = C.width ?? 1200, H = C.height ?? 1200, FRAME_H = C.frame_height ?? 600;
const INK = C.ink ?? '#0B0B0C', ACCENT = C.accent ?? '#F5A524';
const FONT_B = C.font_bold, FONT_R = C.font_regular;
const LOCKUP = brand.lockup_text ?? (brand.name ?? '').toUpperCase();
const PAD = 70, TEXT_W = W - PAD * 2;

const [source, out, headline = '', subline = '', seek = '2'] = process.argv.slice(2);
if (!source || !out) { console.error('usage: make-card.mjs <mediaId|file> <out.jpg> "HEADLINE" "subline" [seek]'); process.exit(1); }

// Resolve the source: a local file, or a Post Bridge media id.
let input = source;
if (!fss.existsSync(source)) {
  const pbPath = findConfig('pipeline');
  const pl = pbPath ? JSON.parse(await fs.readFile(pbPath, 'utf8')) : {};
  const keyFile = (pl.tools?.post_bridge_config ?? '~/.config/post-bridge/config.json').replace(/^~/, os.homedir());
  const apiKey = process.env.POST_BRIDGE_API_KEY ?? JSON.parse(await fs.readFile(keyFile, 'utf8')).apiKey;
  const r = await fetch(`https://api.post-bridge.com/v1/media/${source}`, { headers: { Authorization: `Bearer ${apiKey}` } });
  if (!r.ok) throw new Error(`media lookup ${r.status}`);
  const url = (await r.json()).object?.url;
  if (!url) throw new Error('no signed url for media');
  input = url;
}

const wrapAt = (t, max) => {
  const words = t.split(/\s+/); const lines = []; let cur = '';
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > max) { if (cur) lines.push(cur.trim()); cur = w; }
    else cur = (cur + ' ' + w).trim();
  }
  if (cur) lines.push(cur.trim());
  return lines;
};
function fit(text, sizes, maxLines) {
  for (const size of sizes) {
    const lines = wrapAt(text, Math.floor(TEXT_W / (size * 0.60)));
    if (lines.length <= maxLines) return { size, lines };
  }
  const size = sizes.at(-1);
  return { size, lines: wrapAt(text, Math.floor(TEXT_W / (size * 0.60))).slice(0, maxLines) };
}

if (!headline.trim()) {
  const ff = [
    `[0:v]scale=${W}:${H}:force_original_aspect_ratio=decrease,setpts=PTS-STARTPTS[frame]`,
    `color=c=${INK}:s=${W}x${H}:d=1[bg]`,
    `[bg][frame]overlay=(W-w)/2:(H-h)/2:eof_action=pass:shortest=1[v]`,
  ].join(';');
  await run('ffmpeg', ['-nostdin', '-v', 'error', '-y', '-ss', String(seek), '-i', input,
    '-filter_complex', ff, '-map', '[v]', '-frames:v', '1', '-q:v', '2', out]);
  console.log(`${out}  ${((await fs.stat(out)).size / 1024).toFixed(0)} KB  FULL-FRAME`);
  process.exit(0);
}

const head = fit(headline.toUpperCase(), [84, 74, 66, 58, 50], 3);
const sub = subline ? fit(subline, [40, 36, 32], 3) : { size: 40, lines: [] };
const tmp = path.join(os.tmpdir(), `card-${Date.now()}`);
await fs.writeFile(`${tmp}-head.txt`, head.lines.join('\n'));
if (sub.lines.length) await fs.writeFile(`${tmp}-sub.txt`, sub.lines.join('\n'));
const headY = FRAME_H + 64;
const subY = headY + head.lines.length * (head.size + 14) + 24;

const filters = [
  `[0:v]scale=${W}:-1:force_original_aspect_ratio=increase,crop=${W}:${FRAME_H}:0:'min(max(ih*0.12\\,0)\\,ih-${FRAME_H})',eq=brightness=-0.03,setpts=PTS-STARTPTS[frame]`,
  `color=c=${INK}:s=${W}x${H}:d=1[bg]`,
  `[bg][frame]overlay=0:0:eof_action=pass:shortest=1[base]`,
  `[base]drawbox=x=0:y=${FRAME_H}:w=${W}:h=6:color=${ACCENT}@1:t=fill[rule]`,
  `[rule]drawtext=fontfile='${FONT_B}':textfile='${tmp}-head.txt':fontcolor=white:fontsize=${head.size}:line_spacing=14:x=${PAD}:y=${headY}[h]`,
  sub.lines.length
    ? `[h]drawtext=fontfile='${FONT_R}':textfile='${tmp}-sub.txt':fontcolor=#C9CBD1:fontsize=${sub.size}:line_spacing=10:x=${PAD}:y=${subY}[s]`
    : `[h]null[s]`,
  `[s]drawtext=fontfile='${FONT_B}':text='${LOCKUP}':fontcolor=${ACCENT}:fontsize=30:x=${PAD}:y=${H - 72}[v]`,
].join(';');

await run('ffmpeg', ['-nostdin', '-v', 'error', '-y', '-ss', String(seek), '-i', input,
  '-filter_complex', filters, '-map', '[v]', '-frames:v', '1', '-q:v', '2', out]);
console.log(`${out}  ${((await fs.stat(out)).size / 1024).toFixed(0)} KB  head=${head.size}px/${head.lines.length}L sub=${sub.size}px/${sub.lines.length}L`);

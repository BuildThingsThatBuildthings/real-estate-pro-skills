import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {z} from 'zod';

export const FPS = 30;

// IG story/reel safe zones from channel-specs.md.
export const SAFE = {top: 108, bottom: 320, left: 60, right: 120};

// Brand display font: the bundled OFL serif staged by video_props.py
// (public/job/font-display.ttf). Loaded via FontFace so renders are identical
// on every OS; the stack degrades to system serifs when the file is absent.
export const serif = '"CF Serif", Didot, "Hoefler Text", Georgia, serif';
export const sansDisplay = '"CF Sans", "Helvetica Neue", Helvetica, Arial, sans-serif';
export const sans = 'Helvetica Neue, Helvetica, Arial, sans-serif';

export type Design = {layout_family?: string; display_type?: string;
                      motion_energy?: string; accent_treatment?: string};

/** Display typography driven by the brand's design tokens. */
export const displayStyle = (design?: Design) =>
  design?.display_type === 'sans'
    ? {fontFamily: sansDisplay, fontWeight: 800 as const, letterSpacing: '-0.015em'}
    : {fontFamily: serif, fontWeight: 400 as const, letterSpacing: 'normal'};

/** Spring config scaled by motion energy. */
export const springCfg = (design?: Design) => {
  const e = design?.motion_energy;
  if (e === 'energetic') return {damping: 100, stiffness: 260};
  if (e === 'confident') return {damping: 140, stiffness: 180};
  return {damping: 200, stiffness: 100};
};

let fontLoaded = false;

/** Load the bundled brand font once per render. Call at the top of each
 * composition component — delayRender must run inside a render context. */
export const useBrandFont = () => {
  const [handle] = React.useState(() =>
    fontLoaded ? null : delayRender('load brand font'));
  React.useEffect(() => {
    if (handle === null) return;
    const done = () => continueRender(handle);
    try {
      const serifFace = new FontFace('CF Serif',
        `url(${staticFile('job/font-display.ttf')})`);
      const sansFace = new FontFace('CF Sans',
        `url(${staticFile('job/font-sans.ttf')})`, {weight: '200 900'} as any);
      Promise.allSettled([serifFace.load(), sansFace.load()]).then((rs) => {
        rs.forEach((r) => {
          if (r.status === 'fulfilled') (document as any).fonts.add(r.value);
        });
        fontLoaded = true;
        done();
      }).catch(done);
    } catch {
      done();
    }
  }, [handle]);
};

export const wordSchema = z.object({t: z.string(), s: z.number(), e: z.number()});

export const sceneSchema = z.object({
  photo: z.string(),
  clip: z.string().nullable().optional(),
  width: z.number(),
  height: z.number(),
  aspect: z.number(),
  room: z.string(),
  feature: z.string(),
  vo: z.string().nullable(),
  voDurationS: z.number(),
  voWords: z.array(wordSchema).optional(),
  pins: z.array(z.object({text: z.string(), atS: z.number()})).optional(),
  frames: z.number(),
});

export const propsSchema = z.object({
  design: z.object({
    layout_family: z.string().optional(),
    display_type: z.string().optional(),
    motion_energy: z.string().optional(),
    accent_treatment: z.string().optional(),
  }).optional(),
  brand: z.object({
    primary: z.string(),
    secondary: z.string(),
    accent: z.string(),
    textOnDark: z.string(),
    logoDark: z.string(),
    headshot: z.string().nullable().optional(),
    name: z.string(),
  }),
  addressChip: z.string().optional(),
  headline: z.string(),
  subline: z.string(),
  hook: z.string(),
  community: z.string(),
  scenes: z.array(sceneSchema),
  briefCards: z.array(z.object({
    photo: z.string(), width: z.number(), height: z.number(),
    aspect: z.number(), line: z.string(),
  })),
  endcard: z.object({
    vo: z.string().nullable(), voDurationS: z.number(),
    voWords: z.array(wordSchema).optional(), frames: z.number(),
  }),
  audio: z.object({
    bed: z.string().nullable(), bedVolume: z.number(), bedVolumeSolo: z.number(),
  }),
  compliance: z.object({
    license: z.string(), disclosure: z.string(), fairHousing: z.string(),
  }),
  warnings: z.array(z.string()),
});
export type VideoProps = z.infer<typeof propsSchema>;
export type Scene = z.infer<typeof sceneSchema>;

/**
 * Music bed for a whole composition. Loops, holds a base volume, fades out
 * over the final 1.5s. Volume is a per-frame function so ducking is
 * deterministic, not a mix guess.
 */
export const Bed: React.FC<{
  src: string | null;
  volume: number;
  totalFrames: number;
}> = ({src, volume, totalFrames}) => {
  if (!src) return null;
  return (
    <Audio
      loop
      src={staticFile(src)}
      volume={(f) =>
        interpolate(f, [0, 20, totalFrames - 45, totalFrames - 5], [0, volume, volume, 0], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      }
    />
  );
};

/**
 * Aspect-aware photo treatment. The fix for "images don't fit the screen":
 *
 * - Landscape photo on a portrait canvas → the photo is FITTED to full width
 *   (never cropped beyond the traversal margin, ~5% per side) and placed in an
 *   editorial band; the surrounding brand field carries the typography. Motion
 *   is a slow lateral traversal INSIDE the fitted frame — it reveals the
 *   photograph instead of amputating it.
 * - Portrait/near-square photo → full-bleed cover with a slow push.
 */
export const FittedPhoto: React.FC<{
  scene: {photo: string; aspect: number; clip?: string | null};
  frames: number;
  centerY: number;
  index?: number;
}> = ({scene, frames, centerY, index = 0}) => {
  const frame = useCurrentFrame();
  const {width: W, height: H, fps} = useVideoConfig();
  const isLandscape = scene.aspect > 1.05;
  const settle = interpolate(frame, [0, Math.min(24, frames / 3)], [0, 1], {
    extrapolateRight: 'clamp',
  });

  // Real i2v parallax flight: play the clip inside the band, time-stretched to
  // fill the scene (5s source over an ~7s scene = graceful slow motion).
  if (scene.clip) {
    const CLIP_S = 5;
    const rate = Math.min(1, (CLIP_S * fps) / frames);
    const fitH = isLandscape ? Math.round(W / scene.aspect) : H;
    const top = isLandscape ? Math.round(centerY - fitH / 2) : 0;
    return (
      <div style={{position: 'absolute', left: 0, top, width: W, height: fitH,
                   overflow: 'hidden', opacity: settle}}>
        <OffthreadVideo
          src={staticFile(scene.clip)}
          muted
          playbackRate={rate}
          style={{width: '100%', height: '100%', objectFit: 'cover'}}
        />
      </div>
    );
  }

  if (!isLandscape) {
    const zoom = interpolate(frame, [0, frames], [1.04, 1.1]);
    return (
      <AbsoluteFill>
        <Img
          src={staticFile(scene.photo)}
          style={{width: '100%', height: '100%', objectFit: 'cover',
                  transform: `scale(${zoom})`}}
        />
      </AbsoluteFill>
    );
  }

  const fitH = Math.round(W / scene.aspect);
  const top = Math.round(centerY - fitH / 2);
  // Traversal: image rendered 10% wider than the window, panning across it.
  const overscan = 1.1;
  const maxPan = (W * overscan - W) / 2;
  const dir = index % 2 === 0 ? 1 : -1;
  const pan = interpolate(frame, [0, frames], [-maxPan * dir, maxPan * dir]);
  return (
    <div
      style={{
        position: 'absolute', left: 0, top, width: W, height: fitH,
        overflow: 'hidden', opacity: settle,
      }}
    >
      <Img
        src={staticFile(scene.photo)}
        style={{
          position: 'absolute',
          left: -(W * overscan - W) / 2 + pan,
          width: W * overscan,
          height: fitH * overscan,
          top: -(fitH * overscan - fitH) / 2,
          objectFit: 'cover',
        }}
      />
    </div>
  );
};

/** Room callout: index + title above the photo band, feature line below. */
export const RoomCallout: React.FC<{
  room: string;
  feature: string;
  indexLabel: string;
  brand: VideoProps['brand'];
  photoTop: number;
  photoBottom: number;
  design?: Design;
}> = ({room, feature, indexLabel, brand, photoTop, photoBottom, design}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const disp = displayStyle(design);
  const rise = spring({frame, fps, config: springCfg(design), durationInFrames: 26});
  const featureIn = interpolate(frame, [14, 34], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  return (
    <>
      <div
        style={{
          position: 'absolute', left: SAFE.left, right: SAFE.right,
          top: photoTop - 190,
          transform: `translateY(${(1 - rise) * 34}px)`, opacity: rise,
        }}
      >
        <div style={{fontFamily: disp.fontFamily, fontWeight: 600, fontSize: 30,
                     letterSpacing: 8, color: brand.accent}}>
          {indexLabel}
        </div>
        <div style={{...disp, fontSize: design?.display_type === 'sans' ? 78 : 84,
                     color: brand.textOnDark,
                     lineHeight: 1.05, marginTop: 10, whiteSpace: 'nowrap'}}>
          {room}
        </div>
      </div>
      <div style={{position: 'absolute', left: SAFE.left, right: SAFE.right,
                   top: photoBottom + 46, opacity: featureIn}}>
        <div style={design?.accent_treatment === 'block'
          ? {height: 14, width: 52, backgroundColor: brand.accent}
          : {height: 4, width: 96, backgroundColor: brand.accent}} />
        <div style={{fontFamily: sans, fontSize: 34, lineHeight: 1.4,
                     color: brand.textOnDark, opacity: 0.94, marginTop: 22}}>
          {feature}
        </div>
      </div>
    </>
  );
};

type Word = {t: string; s: number; e: number};
type WordGroup = {words: Word[]; start: number; end: number};

/** Chunk narration words into caption groups: break on pauses or length. */
/**
 * Reading-speed grouping. People read slower than narrators speak, so:
 * - groups are large (up to ~2 lines / 10 words) → fewer flips to track
 * - a group only breaks on a real pause (>0.8s) or hard length limits
 * - each group LINGERS after its last word until the next group actually
 *   starts speaking (plus a tail at the end) — text never vanishes while
 *   someone could still be reading it.
 */
const groupWords = (words: Word[]): WordGroup[] => {
  const groups: WordGroup[] = [];
  let cur: Word[] = [];
  let chars = 0;
  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    const gap = cur.length ? w.s - cur[cur.length - 1].e : 0;
    if (cur.length && (gap > 0.8 || chars + w.t.length > 48 || cur.length >= 10)) {
      groups.push({words: cur, start: cur[0].s, end: cur[cur.length - 1].e});
      cur = []; chars = 0;
    }
    cur.push(w); chars += w.t.length + 1;
  }
  if (cur.length) groups.push({words: cur, start: cur[0].s, end: cur[cur.length - 1].e});
  return groups;
};

const isKeyword = (t: string) =>
  /\d|\$/.test(t) || t.length > 8;

/**
 * Kinetic word-synced captions: everything the narrator says appears on
 * screen, word by word, timed to the voice. Each caption group holds the
 * lower band; within it every word pops in on its own spoken timestamp with
 * a spring, and the word currently being spoken glows in the accent color.
 */
export const KineticCaption: React.FC<{
  words: Word[];
  brand: VideoProps['brand'];
  design?: Design;
  top: number;
  fontSize?: number;
}> = ({words, brand, design, top, fontSize = 46}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const groups = React.useMemo(() => groupWords(words), [words]);
  const disp = displayStyle(design);
  const gi = groups.findIndex((g, i) => {
    const nextStart = i + 1 < groups.length ? groups[i + 1].start
                                            : g.end + 1.4; // reading tail
    return t >= g.start - 0.15 && t < nextStart;
  });
  if (gi < 0) return null;
  const g = groups[gi];
  return (
    <div style={{position: 'absolute', left: SAFE.left, right: SAFE.right, top,
                 display: 'flex', flexWrap: 'wrap', gap: '0 18px',
                 alignItems: 'baseline'}}>
      {g.words.map((w, i) => {
        const local = Math.max(0, (t - w.s) * fps);
        const pop = spring({frame: local, fps, config: springCfg(design),
                            durationInFrames: 14});
        const speaking = t >= w.s && t <= w.e + 0.12;
        const key = isKeyword(w.t);
        return (
          <span
            key={gi + '-' + i}
            style={{
              ...disp,
              fontSize: key ? fontSize * 1.12 : fontSize,
              lineHeight: 1.25,
              color: speaking || key ? brand.accent : brand.textOnDark,
              opacity: t >= w.s - 0.02 ? pop : 0,
              transform: `translateY(${(1 - pop) * 26}px) scale(${0.9 + 0.1 * pop})`,
              display: 'inline-block',
              textShadow: speaking ? `0 0 26px ${brand.accent}66` : 'none',
            }}
          >
            {w.t}
          </span>
        );
      })}
    </div>
  );
};

/**
 * Persistent fact rail. When the narrator states a key fact, its chip springs
 * into a right-side stack and STAYS for the rest of the scene — the sentence
 * is kinetic, the facts are permanent. The address chip persists above them.
 */
export const FactPins: React.FC<{
  pins: {text: string; atS: number}[];
  addressChip?: string;
  brand: VideoProps['brand'];
  design?: Design;
}> = ({pins, addressChip, brand, design}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const disp = displayStyle(design);
  const chip = (text: string, i: number, appeared: boolean, key: string) => {
    const local = Math.max(0, (t - (i < 0 ? 0 : pins[i]?.atS ?? 0)) * fps);
    const pop = appeared
      ? spring({frame: local, fps, config: springCfg(design), durationInFrames: 18})
      : 0;
    return (
      <div key={key}
        style={{
          opacity: pop,
          transform: `translateX(${(1 - pop) * 90}px)`,
          background: `${brand.primary}d9`,
          borderRight: `10px solid ${brand.accent}`,
          padding: '14px 20px 14px 22px',
          marginBottom: 14,
          textAlign: 'right',
          fontFamily: disp.fontFamily,
          fontWeight: 700,
          fontSize: 30,
          letterSpacing: '.04em',
          color: brand.textOnDark,
          textTransform: 'uppercase',
        }}>
        {text}
      </div>
    );
  };
  return (
    <div style={{position: 'absolute', right: 0, top: SAFE.top + 60,
                 display: 'flex', flexDirection: 'column',
                 alignItems: 'flex-end'}}>
      {addressChip ? (
        <div style={{
          background: brand.accent, color: '#fff', fontFamily: disp.fontFamily,
          fontWeight: 800, fontSize: 28, letterSpacing: '.06em',
          textTransform: 'uppercase', padding: '12px 20px', marginBottom: 18,
        }}>{addressChip}</div>
      ) : null}
      {pins.map((p, i) => chip(p.text, i, t >= p.atS, 'pin-' + i))}
    </div>
  );
};

/** Shared compliance endcard. Optionally narrated. */
export const Endcard: React.FC<{
  brand: VideoProps['brand'];
  subline: string;
  compliance: VideoProps['compliance'];
  vo?: string | null;
  voWords?: Word[];
  design?: Design;
}> = ({brand, subline, compliance, vo, voWords, design}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const disp = displayStyle(design);
  const rise = spring({frame, fps, config: springCfg(design), durationInFrames: 30});
  return (
    <AbsoluteFill style={{backgroundColor: brand.primary}}>
      {vo ? <Audio src={staticFile(vo)} /> : null}
      <div
        style={{
          position: 'absolute', left: SAFE.left, right: SAFE.right,
          top: brand.headshot ? 520 : 690,
          textAlign: 'center',
          transform: `translateY(${(1 - rise) * 50}px)`, opacity: rise,
        }}
      >
        {brand.headshot ? (
          <Img
            src={staticFile(brand.headshot)}
            style={{width: 300, height: 300, borderRadius: '50%',
                    objectFit: 'cover', margin: '0 auto 48px',
                    border: `6px solid ${brand.accent}`, display: 'block'}}
          />
        ) : null}
        <Img src={staticFile(brand.logoDark)} style={{width: 620}} />
        <div style={{fontFamily: disp.fontFamily, fontWeight: 700, fontSize: 36,
                     letterSpacing: 5,
                     color: brand.accent, marginTop: 56,
                     textTransform: 'uppercase'}}>
          Now Showing
        </div>
        <div style={{fontFamily: disp.fontFamily, fontSize: 32, color: brand.textOnDark,
                     marginTop: 18, opacity: 0.92}}>
          {subline}
        </div>
      </div>
      {voWords && voWords.length ? (
        <KineticCaption words={voWords} brand={brand} design={design}
                        top={1330} fontSize={44} />
      ) : null}
      <div
        style={{
          position: 'absolute', left: SAFE.left, right: SAFE.right,
          bottom: SAFE.bottom + 24, fontFamily: sans, fontSize: 26,
          lineHeight: 1.5, color: brand.textOnDark,
        }}
      >
        <div>{compliance.license}</div>
        <div>{compliance.disclosure}</div>
        <div>{compliance.fairHousing}</div>
      </div>
    </AbsoluteFill>
  );
};

/** Brand intro card shared by Walkthrough and Teaser. */
export const IntroCard: React.FC<{
  brand: VideoProps['brand'];
  title: string;
  subline: string;
  frames: number;
  design?: Design;
}> = ({brand, title, subline, frames, design}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const disp = displayStyle(design);
  const rise = spring({frame, fps, config: springCfg(design), durationInFrames: 28});
  const brandIn = spring({frame: Math.max(0, frame - 4), fps,
                          config: springCfg(design), durationInFrames: 26});
  const ruleW = interpolate(frame, [6, 30], [0, 240], {extrapolateRight: 'clamp'});
  const fade = interpolate(frame, [frames - 12, frames], [1, 0], {
    extrapolateLeft: 'clamp',
  });
  return (
    <AbsoluteFill style={{backgroundColor: brand.primary, opacity: fade}}>
      {/* Brand-first opening: the agent's face and wordmark lead, before the
          address. The agent IS the brand. */}
      <div
        style={{
          position: 'absolute', left: SAFE.left, right: SAFE.right, top: 200,
          textAlign: 'center',
          transform: `translateY(${(1 - brandIn) * -40}px)`, opacity: brandIn,
        }}
      >
        {brand.headshot ? (
          <Img
            src={staticFile(brand.headshot)}
            style={{width: 210, height: 210, borderRadius: '50%',
                    objectFit: 'cover', margin: '0 auto 34px',
                    border: `6px solid ${brand.accent}`, display: 'block'}}
          />
        ) : null}
        <Img src={staticFile(brand.logoDark)}
             style={{width: 560, display: 'block', margin: '0 auto'}} />
      </div>
      <div
        style={{
          position: 'absolute', left: SAFE.left, right: SAFE.right, top: 760,
          transform: `translateY(${(1 - rise) * 60}px)`, opacity: rise,
        }}
      >
        <div style={design?.accent_treatment === 'block'
          ? {height: 20, width: Math.max(20, ruleW / 3), backgroundColor: brand.accent}
          : {height: 6, width: ruleW, backgroundColor: brand.accent}} />
        <div style={{...disp, fontSize: design?.display_type === 'sans' ? 86 : 92,
                     lineHeight: 1.1,
                     color: brand.textOnDark, marginTop: 44}}>
          {title}
        </div>
        <div style={{fontFamily: disp.fontFamily, fontWeight: 600, fontSize: 34,
                     letterSpacing: 5,
                     color: brand.accent, marginTop: 38,
                     textTransform: 'uppercase'}}>
          {subline}
        </div>
      </div>
    </AbsoluteFill>
  );
};

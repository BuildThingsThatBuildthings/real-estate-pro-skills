import React from 'react';
import {
  AbsoluteFill, Img, Sequence, interpolate, spring, staticFile,
  useCurrentFrame, useVideoConfig,
} from 'remotion';
import {
  Bed, Endcard, SAFE, VideoProps, displayStyle, logoBox, sans, springCfg,
  useBrandFont,
} from './shared';

const HOOK_F = 90;
const STAT_F = 105;
const VALUE_W = 1080 - SAFE.left - SAFE.right;

export const marketUpdateDuration = (p: VideoProps) =>
  HOOK_F + (p.market?.stats.length ?? 0) * STAT_F + p.endcard.frames;

type Market = NonNullable<VideoProps['market']>;

/** Stat values are the hook, so they run as large as the width allows. The
 * width budget is a conservative per-character estimate for display digits. */
const valueSize = (value: string) =>
  Math.max(96, Math.min(210, Math.floor(VALUE_W / (value.length * 0.6))));

/**
 * Light brand ground: the market's ground colour with a faint primary grid.
 * Every ink on it was picked by video_props.py for measured WCAG contrast, so
 * nothing here assumes a dark photograph behind white type.
 */
const Ground: React.FC<{market: Market; primary: string; children: React.ReactNode}> =
  ({market, primary, children}) => (
    <AbsoluteFill style={{
      backgroundColor: market.ground,
      backgroundImage: `linear-gradient(${primary}14 1px, transparent 1px),` +
        `linear-gradient(90deg, ${primary}14 1px, transparent 1px)`,
      backgroundSize: '90px 90px',
    }}>
      {children}
    </AbsoluteFill>
  );

/** Logo (light-ground variant) and the data area + period on every card. The
 * period is always on screen: a statistic without its date reads as current. */
const BrandBar: React.FC<{brand: VideoProps['brand']; market: Market}> = ({brand, market}) => {
  const logo = logoBox(brand.logoLightAspect ?? brand.logoDarkAspect, 380, 150);
  return (
    <div style={{position: 'absolute', left: SAFE.left, right: SAFE.right, top: SAFE.top}}>
      <Img src={staticFile(brand.logoLight ?? brand.logoDark)}
           style={{width: logo.width, height: logo.height, objectFit: 'contain',
                   display: 'block'}} />
      <div style={{height: 4, width: 140, backgroundColor: market.rule, marginTop: 30}} />
      <div style={{fontFamily: sans, fontWeight: 600, fontSize: 30, letterSpacing: 4,
                   textTransform: 'uppercase', color: market.ink, marginTop: 20}}>
        {[market.area, market.period].filter(Boolean).join(' · ')}
      </div>
    </div>
  );
};

const HookCard: React.FC<{props: VideoProps; market: Market}> = ({props, market}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const disp = displayStyle(props.design);
  const rise = spring({frame, fps, config: springCfg(props.design), durationInFrames: 26});
  const fade = interpolate(frame, [HOOK_F - 12, HOOK_F], [1, 0], {extrapolateLeft: 'clamp'});
  return (
    <Ground market={market} primary={props.brand.primary}>
      <div style={{opacity: fade}}>
        <BrandBar brand={props.brand} market={market} />
        <div style={{position: 'absolute', left: SAFE.left, right: SAFE.right, top: 720,
                     transform: `translateY(${(1 - rise) * 50}px)`, opacity: rise}}>
          <div style={{...disp, fontSize: 104, lineHeight: 1.1, color: market.ink}}>
            {props.hook}
          </div>
          <div style={{fontFamily: sans, fontSize: 38, lineHeight: 1.35,
                       color: market.ink, marginTop: 40}}>
            {props.headline}
          </div>
        </div>
      </div>
    </Ground>
  );
};

const StatCard: React.FC<{
  props: VideoProps; market: Market; index: number;
}> = ({props, market, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const disp = displayStyle(props.design);
  const stat = market.stats[index];
  const cfg = springCfg(props.design);
  const labelIn = spring({frame, fps, config: cfg, durationInFrames: 20});
  const valueIn = spring({frame: Math.max(0, frame - 6), fps, config: cfg, durationInFrames: 24});
  const detailIn = interpolate(frame, [18, 36], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const fade = interpolate(frame, [STAT_F - 12, STAT_F], [1, 0], {extrapolateLeft: 'clamp'});
  const n = market.stats.length;
  return (
    <Ground market={market} primary={props.brand.primary}>
      <div style={{opacity: fade}}>
        <BrandBar brand={props.brand} market={market} />
        {/* One flow column: label, value, detail, source. Flow layout, not
            absolute offsets, so a two-line detail pushes the source down
            instead of overlapping it. */}
        <div style={{position: 'absolute', left: SAFE.left, right: SAFE.right,
                     top: 560, bottom: SAFE.bottom, display: 'flex',
                     flexDirection: 'column'}}>
          <div style={{fontFamily: sans, fontSize: 26, letterSpacing: 6,
                       color: market.ink, opacity: labelIn}}>
            {String(index + 1).padStart(2, '0')} / {String(n).padStart(2, '0')}
          </div>
          <div style={{fontFamily: sans, fontWeight: 700, fontSize: 40, letterSpacing: 3,
                       textTransform: 'uppercase', color: market.ink, marginTop: 26,
                       opacity: labelIn,
                       transform: `translateY(${(1 - labelIn) * 20}px)`}}>
            {stat.label}
          </div>
          <div style={{...disp, fontSize: valueSize(stat.value), lineHeight: 1.05,
                       color: market.valueInk, marginTop: 24, whiteSpace: 'nowrap',
                       opacity: valueIn,
                       transform: `translateY(${(1 - valueIn) * 40}px)`}}>
            {stat.value}
          </div>
          <div style={{height: 6, width: 120, backgroundColor: market.rule,
                       marginTop: 36, opacity: detailIn}} />
          {stat.detail ? (
            <div style={{fontFamily: sans, fontSize: 42, lineHeight: 1.35,
                         color: market.ink, marginTop: 32, opacity: detailIn}}>
              {stat.detail}
            </div>
          ) : null}
          <div style={{flex: 1}} />
          <div style={{fontFamily: sans, fontSize: 28, lineHeight: 1.4,
                       color: market.ink, opacity: detailIn}}>
            Source: {stat.source}
          </div>
        </div>
      </div>
    </Ground>
  );
};

/**
 * Market update data video (prompt-library #4, Phase 2). A hook card, one
 * statistic per card with its source and data period, then the compliance
 * endcard. Built for a no-drop run: no photographs, brand ground only.
 * Props come from video_props.py with scenes.json `kind: "market"`.
 */
export const MarketUpdate: React.FC<VideoProps> = (props) => {
  useBrandFont();
  const market = props.market;
  if (!market) {
    throw new Error('MarketUpdate needs props.market — build props from a scenes.json ' +
                    'with kind: "market" and market.stats');
  }
  const total = marketUpdateDuration(props);
  const endFrom = HOOK_F + market.stats.length * STAT_F;
  return (
    <AbsoluteFill style={{backgroundColor: market.ground}}>
      <Bed src={props.audio.bed} volume={props.audio.bedVolumeSolo} totalFrames={total} />
      <Sequence durationInFrames={HOOK_F}>
        <HookCard props={props} market={market} />
      </Sequence>
      {market.stats.map((s, i) => (
        <Sequence key={s.label + i} from={HOOK_F + i * STAT_F} durationInFrames={STAT_F}>
          <StatCard props={props} market={market} index={i} />
        </Sequence>
      ))}
      <Sequence from={endFrom} durationInFrames={props.endcard.frames}>
        <Endcard design={props.design} brand={props.brand} subline={props.subline}
                 compliance={props.compliance} label={null}
                 vo={props.endcard.vo} voWords={props.endcard.voWords} />
      </Sequence>
    </AbsoluteFill>
  );
};

import React from 'react';
import {
  AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig,
} from 'remotion';
import {
  Bed, Endcard, FittedPhoto, SAFE, serif, VideoProps, useBrandFont,
} from './shared';

const HOOK_F = 84;
const CARD_F = 96;
const COMMUNITY_F = 78;

export const salesBriefDuration = (p: VideoProps) =>
  HOOK_F + p.briefCards.length * CARD_F + COMMUNITY_F + p.endcard.frames;

const TextCard: React.FC<{
  brand: VideoProps['brand']; text: string; frames: number; size?: number;
}> = ({brand, text, frames, size = 96}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const rise = spring({frame, fps, config: {damping: 200}, durationInFrames: 26});
  const fade = interpolate(frame, [frames - 12, frames], [1, 0], {extrapolateLeft: 'clamp'});
  return (
    <AbsoluteFill style={{backgroundColor: brand.primary, opacity: fade}}>
      <div style={{
        position: 'absolute', left: SAFE.left, right: SAFE.right, top: 760,
        transform: `translateY(${(1 - rise) * 50}px)`, opacity: rise,
      }}>
        <div style={{height: 6, width: 200, backgroundColor: brand.accent}} />
        <div style={{fontFamily: serif, fontSize: size, lineHeight: 1.14,
                     color: brand.textOnDark, marginTop: 40}}>
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/**
 * Digital Sales Brief — typography-led. Hook, four feature cards (photo fitted
 * into an editorial band + one large claim each), the community line, endcard.
 */
export const SalesBrief: React.FC<VideoProps> = (props) => {
  useBrandFont();
  const {height: H} = useVideoConfig();
  const total = salesBriefDuration(props);
  let cursor = HOOK_F;
  const photoCenterY = H * 0.42; // photo high, statement below

  return (
    <AbsoluteFill style={{backgroundColor: props.brand.primary}}>
      <Bed src={props.audio.bed} volume={props.audio.bedVolumeSolo} totalFrames={total} />
      <Sequence durationInFrames={HOOK_F}>
        <TextCard brand={props.brand} text={props.hook} frames={HOOK_F} />
      </Sequence>
      {props.briefCards.map((card, i) => {
        const from = cursor;
        cursor += CARD_F;
        const fitH = card.aspect > 1.05 ? Math.round(1080 / card.aspect) : H;
        const top = card.aspect > 1.05 ? Math.round(photoCenterY - fitH / 2) : 0;
        return (
          <Sequence key={card.photo + i} from={from} durationInFrames={CARD_F}>
            <AbsoluteFill style={{backgroundColor: props.brand.primary}}>
              <FittedPhoto scene={card} frames={CARD_F} centerY={photoCenterY} index={i} />
              <BriefLine brand={props.brand} line={card.line}
                         top={card.aspect > 1.05 ? top + fitH + 70 : H - 640} />
            </AbsoluteFill>
          </Sequence>
        );
      })}
      <Sequence from={cursor} durationInFrames={COMMUNITY_F}>
        <TextCard brand={props.brand} text={props.community} frames={COMMUNITY_F} size={72} />
      </Sequence>
      <Sequence from={cursor + COMMUNITY_F} durationInFrames={props.endcard.frames}>
        <Endcard design={props.design} brand={props.brand} subline={props.subline}
                 compliance={props.compliance} />
      </Sequence>
    </AbsoluteFill>
  );
};

const BriefLine: React.FC<{
  brand: VideoProps['brand']; line: string; top: number;
}> = ({brand, line, top}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const rise = spring({frame, fps, config: {damping: 200}, durationInFrames: 24});
  return (
    <div style={{
      position: 'absolute', left: SAFE.left, right: SAFE.right, top,
      transform: `translateY(${(1 - rise) * 36}px)`, opacity: rise,
    }}>
      <div style={{height: 4, width: 96, backgroundColor: brand.accent}} />
      <div style={{fontFamily: serif, fontSize: 66, lineHeight: 1.16,
                   color: brand.textOnDark, marginTop: 26}}>
        {line}
      </div>
    </div>
  );
};

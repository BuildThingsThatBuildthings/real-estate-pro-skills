import React from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {
  Bed, Endcard, FittedPhoto, IntroCard, RoomCallout, VideoProps, useBrandFont,
} from './shared';

const TEASER_INTRO_F = 60;
const TEASER_SHOT_F = 58;
const TEASER_SHOTS = 3;

export const teaserDuration = (p: VideoProps) =>
  TEASER_INTRO_F + TEASER_SHOTS * TEASER_SHOT_F + Math.min(p.endcard.frames, 84);

/** Listing Teaser — a 10-second hook cut: three strongest rooms, endcard. */
export const Teaser: React.FC<VideoProps> = (props) => {
  useBrandFont();
  const {height: H} = useVideoConfig();
  // Strongest arc: first, middle, last scene (arrival → kitchen → backyard).
  const picks = [
    props.scenes[0],
    props.scenes[Math.floor(props.scenes.length / 2)],
    props.scenes[props.scenes.length - 1],
  ].filter(Boolean);
  const endF = Math.min(props.endcard.frames, 84);
  const total = teaserDuration(props);
  const photoCenterY = H * 0.56;

  return (
    <AbsoluteFill style={{backgroundColor: props.brand.primary}}>
      <Bed src={props.audio.bed} volume={props.audio.bedVolumeSolo} totalFrames={total} />
      <Sequence durationInFrames={TEASER_INTRO_F}>
        <IntroCard design={props.design} brand={props.brand} title={props.hook}
                   subline={props.subline} frames={TEASER_INTRO_F} />
      </Sequence>
      {picks.map((scene, i) => {
        const from = TEASER_INTRO_F + i * TEASER_SHOT_F;
        const fitH = scene.aspect > 1.05 ? Math.round(1080 / scene.aspect) : H;
        const top = scene.aspect > 1.05 ? Math.round(photoCenterY - fitH / 2) : 0;
        return (
          <Sequence key={scene.photo} from={from} durationInFrames={TEASER_SHOT_F}>
            <AbsoluteFill style={{backgroundColor: props.brand.primary}}>
              <FittedPhoto scene={scene} frames={TEASER_SHOT_F}
                           centerY={photoCenterY} index={i} />
              <RoomCallout
                design={props.design}
                room={scene.room} feature={scene.feature}
                indexLabel={`${String(i + 1).padStart(2, '0')} / ${String(picks.length).padStart(2, '0')}`}
                brand={props.brand} photoTop={top}
                photoBottom={scene.aspect > 1.05 ? top + fitH : H - 560}
              />
            </AbsoluteFill>
          </Sequence>
        );
      })}
      <Sequence from={TEASER_INTRO_F + picks.length * TEASER_SHOT_F} durationInFrames={endF}>
        <Endcard design={props.design} brand={props.brand} subline={props.subline}
                 compliance={props.compliance} />
      </Sequence>
    </AbsoluteFill>
  );
};

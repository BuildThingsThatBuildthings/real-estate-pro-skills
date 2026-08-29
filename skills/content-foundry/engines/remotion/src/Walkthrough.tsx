import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig} from 'remotion';
import {
  Bed, Endcard, FactPins, FittedPhoto, IntroCard, KineticCaption, RoomCallout,
  VideoProps, useBrandFont,
} from './shared';

export const WALK_INTRO_F = 72;

export const walkthroughDuration = (p: VideoProps) =>
  WALK_INTRO_F + p.scenes.reduce((a, s) => a + s.frames, 0) + p.endcard.frames;

/**
 * Digital Walkthrough — the flagship. Room-by-room, narrated, aspect-aware.
 * The video talks about the HOUSE: every scene names the room, states a real
 * feature from the drop, and carries the agent narration line for that room.
 */
export const Walkthrough: React.FC<VideoProps> = (props) => {
  useBrandFont();
  const {height: H} = useVideoConfig();
  const total = walkthroughDuration(props);
  let cursor = WALK_INTRO_F;
  const photoCenterY = H * 0.56; // photo band sits below the title block

  return (
    <AbsoluteFill style={{backgroundColor: props.brand.primary}}>
      <Bed src={props.audio.bed} volume={props.audio.bedVolume} totalFrames={total} />
      <Sequence durationInFrames={WALK_INTRO_F}>
        <IntroCard
          design={props.design}
          brand={props.brand}
          title={props.headline}
          subline={props.subline}
          frames={WALK_INTRO_F}
        />
      </Sequence>
      {props.scenes.map((scene, i) => {
        const from = cursor;
        cursor += scene.frames;
        const fitH = scene.aspect > 1.05 ? Math.round(1080 / scene.aspect) : H;
        const top = scene.aspect > 1.05 ? Math.round(photoCenterY - fitH / 2) : 0;
        return (
          <Sequence key={scene.photo} from={from} durationInFrames={scene.frames}>
            <AbsoluteFill style={{backgroundColor: props.brand.primary}}>
              <FittedPhoto scene={scene} frames={scene.frames}
                           centerY={photoCenterY} index={i} />
              <RoomCallout
                design={props.design}
                room={scene.room}
                feature={scene.voWords && scene.voWords.length ? '' : scene.feature}
                indexLabel={`${String(i + 1).padStart(2, '0')} / ${String(props.scenes.length).padStart(2, '0')}`}
                brand={props.brand}
                photoTop={top}
                photoBottom={scene.aspect > 1.05 ? top + fitH : H - 560}
              />
              <FactPins
                pins={scene.pins || []}
                addressChip={props.addressChip}
                brand={props.brand}
                design={props.design}
              />
              {scene.voWords && scene.voWords.length ? (
                <KineticCaption
                  words={scene.voWords}
                  brand={props.brand}
                  design={props.design}
                  top={(scene.aspect > 1.05 ? top + fitH : H - 560) + 60}
                />
              ) : null}
              {scene.vo ? <Audio src={staticFile(scene.vo)} /> : null}
            </AbsoluteFill>
          </Sequence>
        );
      })}
      <Sequence from={cursor} durationInFrames={props.endcard.frames}>
        <Endcard
          design={props.design}
          brand={props.brand}
          subline={props.subline}
          compliance={props.compliance}
          vo={props.endcard.vo}
          voWords={props.endcard.voWords}
        />
      </Sequence>
    </AbsoluteFill>
  );
};

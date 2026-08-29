import React from 'react';
import {Composition} from 'remotion';
import {propsSchema, VideoProps} from './shared';
import {Walkthrough, walkthroughDuration} from './Walkthrough';
import {SalesBrief, salesBriefDuration} from './SalesBrief';
import {Teaser, teaserDuration} from './Teaser';

// 1080x1920 @ 30fps — IG Reels/Story per channel-specs.md.
// Three products from one props file (video_props.py v2):
//   Walkthrough — narrated room-by-room digital walkthrough (flagship)
//   SalesBrief  — typography-led digital sales brief
//   Teaser      — 10s hook cut
// Durations derive from the scene/VO data, never hardcoded.

const DEFAULTS: VideoProps = {
  brand: {
    primary: '#051221', secondary: '#24384c', accent: '#a88c60',
    textOnDark: '#ffffff', logoDark: 'job/logo-dark.png', name: 'Agent Name',
  },
  headline: 'The Lakefront Craftsman',
  subline: 'Shorewood Lake',
  hook: 'Seven rooms on the water',
  community: 'A wooded lakefront lot on Shorewood Lake',
  scenes: [{
    photo: 'job/s1.jpg', width: 1290, height: 955, aspect: 1.3508,
    room: 'The Arrival', feature: 'Timber portico at dusk',
    vo: null, voDurationS: 0, frames: 120,
  }],
  briefCards: [{photo: 'job/s1.jpg', width: 1290, height: 955,
                aspect: 1.3508, line: 'A modern craftsman on the water'}],
  endcard: {vo: null, voDurationS: 0, frames: 150},
  audio: {bed: null, bedVolume: 0.16, bedVolumeSolo: 0.3},
  compliance: {
    license: 'Lic. #000000 (Demo)',
    disclosure: 'Shore & Co. Realty | Fictional demo brokerage.',
    fairHousing: 'Equal Housing Opportunity.',
  },
  warnings: [],
};

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="Walkthrough"
        component={Walkthrough}
        schema={propsSchema}
        width={1080} height={1920} fps={30}
        durationInFrames={walkthroughDuration(DEFAULTS)}
        calculateMetadata={({props}) => ({durationInFrames: walkthroughDuration(props)})}
        defaultProps={DEFAULTS}
      />
      <Composition
        id="SalesBrief"
        component={SalesBrief}
        schema={propsSchema}
        width={1080} height={1920} fps={30}
        durationInFrames={salesBriefDuration(DEFAULTS)}
        calculateMetadata={({props}) => ({durationInFrames: salesBriefDuration(props)})}
        defaultProps={DEFAULTS}
      />
      <Composition
        id="Teaser"
        component={Teaser}
        schema={propsSchema}
        width={1080} height={1920} fps={30}
        durationInFrames={teaserDuration(DEFAULTS)}
        calculateMetadata={({props}) => ({durationInFrames: teaserDuration(props)})}
        defaultProps={DEFAULTS}
      />
    </>
  );
};

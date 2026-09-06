import React from 'react';
import {interpolate,useCurrentFrame,useVideoConfig} from 'remotion';
import {CampaignProps,CampaignScene} from './types';

export const EditorialScene:React.FC<{scene:CampaignScene;brand:CampaignProps['brand']}> = ({scene,brand}) => {
 const f=useCurrentFrame();const {height:h,width:w}=useVideoConfig();const v=h>w;const park=scene.type==='park';
 return <div style={{position:'absolute',inset:0,background:brand.dark,color:brand.paper}}>
  <svg viewBox="0 0 1000 700" style={{position:'absolute',width:v?1100:1300,height:900,top:v?400:10,right:v?-30:-10,opacity:.45}}>
   {[0,1,2,3,4,5,6].map(i=><path key={i} d={`M -100 ${620-i*55} C 160 ${160+i*25} 400 ${750-i*85} 700 ${200+i*25} S 1150 ${350+i*35} 1200 100`} fill="none" stroke={brand.paper} strokeWidth={2} strokeDasharray="1500" strokeDashoffset={interpolate(f,[0,80],[1500,0],{extrapolateRight:'clamp'})}/>)}
   {park&&[0,1,2].map(i=><g key={i} transform={`translate(${230+i*180},${230-i*40})`}><path d="M0 230 L65 100 L25 100 L80 0 L135 100 L95 100 L160 230Z" fill={brand.paper} opacity={.3}/><path d="M80 210v70" stroke={brand.paper} strokeWidth="8"/></g>)}
  </svg>
  <div style={{position:'absolute',left:84,top:v?155:115,right:v?84:1020}}>
   <div style={{fontSize:25,letterSpacing:3,textTransform:'uppercase',marginBottom:28,color:'#f29296'}}>{scene.label}</div>
   <div style={{fontSize:v?85:78,lineHeight:1.03,fontWeight:700,letterSpacing:-3,whiteSpace:'pre-line'}}>{scene.headline}</div>
  </div>
  <div style={{position:'absolute',left:84,top:v?1190:705,fontSize:park?112:48,fontWeight:700,letterSpacing:-3}}>{scene.bigText}</div>
  <div style={{position:'absolute',left:84,top:v?1350:855,fontSize:24,color:'#ccc'}}>{scene.detail}<br/><span style={{fontSize:20}}>Original illustration · Not location footage</span></div>
 </div>;
};

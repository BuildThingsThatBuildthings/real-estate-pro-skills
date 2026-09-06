import React from 'react';
import {interpolate,useCurrentFrame,useVideoConfig} from 'remotion';
import {CampaignProps,CampaignScene} from './types';

export const MapScene:React.FC<{scene:CampaignScene;brand:CampaignProps['brand'];map:CampaignProps['map']}> = ({scene,brand,map}) => {
 const f=useCurrentFrame();const {width:w,height:h}=useVideoConfig();const v=h>w;
 return <div style={{position:'absolute',inset:0,background:brand.paper}}>
  <div style={{position:'absolute',left:84,top:v?150:100,right:80}}>
   <div style={{fontSize:26,letterSpacing:3,color:brand.red,textTransform:'uppercase',marginBottom:22}}>{scene.label}</div>
   <div style={{fontSize:v?82:80,fontWeight:700,lineHeight:1.02,letterSpacing:-3,whiteSpace:'pre-line'}}>{scene.headline}</div>
  </div>
  <svg viewBox="0 0 1000 650" style={{position:'absolute',left:v?20:650,top:v?530:110,width:v?1040:1190,height:v?720:720}}>
   <rect width="1000" height="650" rx="18" fill="#e8ebe3"/>
   {(map?.roads||[]).map((r,i)=><polyline key={i} points={r.map(p=>p.join(',')).join(' ')} fill="none" stroke="#fff" strokeWidth={5}/>) }
   {(map?.markers||[]).map((m,i)=><g key={m.label} opacity={interpolate(f,[i*14,i*14+20],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}>
    <circle cx={m.x} cy={m.y} r={26} fill={brand.red} opacity={.12}/><circle cx={m.x} cy={m.y} r={10} fill={brand.red}/>
    <rect x={Math.min(m.x+20,620)} y={m.y-26} width={330} height={58} rx={9} fill={brand.dark}/><text x={Math.min(m.x+35,635)} y={m.y+10} fontSize={25} fill="white" fontFamily="Inter">{m.label}</text>
   </g>)}
   <text x="35" y="615" fontSize="18" fill="#555">N ↑ · Location overview · No route or travel time implied</text>
  </svg>
  <div style={{position:'absolute',left:84,right:84,top:v?1310:820,fontSize:v?30:25,lineHeight:1.4}}>{map?.caption}<br/><span style={{fontSize:21,color:'#666'}}>{map?.attribution||'Original location diagram · Not to scale'}</span></div>
 </div>;
};

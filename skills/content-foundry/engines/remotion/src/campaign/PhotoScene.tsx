import React from 'react';
import {Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {CampaignProps, CampaignScene} from './types';

export const PhotoScene:React.FC<{scene:CampaignScene;brand:CampaignProps['brand'];index:number}> = ({scene,brand,index}) => {
 const f=useCurrentFrame(); const {width:w,height:h}=useVideoConfig(); const vertical=h>w;
 const fade=interpolate(f,[0,12],[0,1],{extrapolateRight:'clamp'});
 const motion=interpolate(f,[0,scene.frames],[1,1.055],{extrapolateRight:'clamp'});
 const top=vertical?480:0; const ph=vertical?760:h;
 return <div style={{position:'absolute',inset:0,opacity:fade}}>
  <div style={{position:'absolute',left:vertical?0:0,top,width:w,height:ph,overflow:'hidden',background:brand.dark}}>
   <Img src={staticFile(scene.photo!)} style={{width:'100%',height:'100%',objectFit:'contain',scale:motion,translate:`${interpolate(f,[0,scene.frames],[index%2?-12:12,index%2?12:-12])}px 0px`}}/>
  </div>
  {!vertical&&<div style={{position:'absolute',inset:0,background:'linear-gradient(90deg,rgba(0,0,0,.7),transparent 58%),linear-gradient(0deg,rgba(0,0,0,.85),transparent 38%)'}}/>}
  <div style={{position:'absolute',left:vertical?84:110,top:vertical?152:120,right:vertical?84:980}}>
   <div style={{fontSize:vertical?26:25,fontWeight:600,letterSpacing:3,textTransform:'uppercase',color:vertical?brand.red:'#fff',marginBottom:22}}>{scene.label}</div>
   <div style={{fontSize:vertical?80:76,lineHeight:1.01,letterSpacing:-3.5,fontWeight:700,whiteSpace:'pre-line',color:vertical?brand.dark:'white',translate:`0 ${interpolate(f,[0,18],[18,0],{extrapolateRight:'clamp'})}px`}}>{scene.headline}</div>
  </div>
  {vertical&&<div style={{position:'absolute',left:84,right:84,top:1250,display:'flex',alignItems:'center',gap:18}}><div style={{width:36,height:4,background:brand.red}}/><div style={{fontSize:25,letterSpacing:2,color:'#606060'}}>{String(index+1).padStart(2,'0')} / A CLOSER LOOK</div></div>}
  {scene.note&&<div style={{position:'absolute',bottom:vertical?370:150,left:84,fontSize:22,color:vertical?brand.dark:'white'}}>{scene.note}</div>}
 </div>;
};

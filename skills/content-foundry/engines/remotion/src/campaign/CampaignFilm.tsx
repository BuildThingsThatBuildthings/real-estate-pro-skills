import React from 'react';
import {AbsoluteFill,Audio,Img,Sequence,staticFile,useCurrentFrame,useVideoConfig,interpolate} from 'remotion';
import {CampaignProps} from './types';
import {PhotoScene} from './PhotoScene';
import {MapScene} from './MapScene';
import {EditorialScene} from './EditorialScene';

export const CampaignFilm:React.FC<CampaignProps> = p => {
 const f=useCurrentFrame(); const {fps,height:h,width:w,durationInFrames:d}=useVideoConfig();const v=h>w; let start=0;
 let sceneEnd=0; const currentScene=p.scenes.find(s=>{sceneEnd+=s.frames;return f<sceneEnd;}); const darkScene=!currentScene?.photo && currentScene?.type!=='map';
 const cap=p.captions.find(c=>f/fps>=c.start&&f/fps<c.end);
 return <AbsoluteFill style={{background:p.brand.paper,color:p.brand.dark,fontFamily:'Inter, sans-serif'}}>
  <style>{`@font-face{font-family:Inter;src:url('${staticFile(p.brand.font)}') format('woff2');font-weight:100 900}`}</style>
  {p.scenes.map((s,i)=>{const from=start;start+=s.frames;return <Sequence from={from} durationInFrames={s.frames} key={i} name={s.label}>
   {s.photo?<PhotoScene scene={s} brand={p.brand} index={i}/>:s.type==='map'?<MapScene scene={s} brand={p.brand} map={p.map}/>:<EditorialScene scene={s} brand={p.brand}/>}
  </Sequence>})}
  <div style={{position:'absolute',left:0,top:0,height:8,width:w*f/d,background:p.brand.red}}/>
  <div style={{position:'absolute',top:v?66:42,left:84,fontSize:23,letterSpacing:3,fontWeight:650,color:v&&!darkScene?p.brand.dark:'white',background:v?'transparent':'rgba(0,0,0,.4)',padding:v?0:'8px 15px'}}>{p.brand.name.toUpperCase()}</div>
  {cap&&<div style={{position:'absolute',left:v?84:270,right:v?84:270,bottom:v?388:155,display:'flex',justifyContent:'center'}}><div style={{background:'rgba(15,15,15,.92)',color:'white',padding:'16px 24px',fontSize:v?42:39,lineHeight:1.2,textAlign:'center',borderRadius:6}}>{cap.text}</div></div>}
  <div style={{position:'absolute',boxSizing:'border-box',left:0,right:0,bottom:v?170:0,height:v?174:118,background:p.brand.paper,borderTop:`4px solid ${p.brand.red}`,padding:v?'26px 84px':'20px 84px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
   <div><div style={{fontSize:v?29:28,fontWeight:700}}>{p.brand.agent}, REALTOR®</div><div style={{fontSize:v?23:24,marginTop:7}}>C {p.brand.phone} · O {p.brand.officePhone}</div><div style={{fontSize:21,marginTop:5}}>{p.brand.website} · {p.brand.licenseLabel||'License #'}{p.brand.license}</div></div>
   <div style={{textAlign:'center'}}><Img src={staticFile(p.brand.logo)} style={{width:v?245:330,height:55,objectFit:'contain'}}/><div style={{fontSize:19,marginTop:8}}>{p.brand.brokerage}</div></div>
  </div>
  {p.audio&&<Audio src={staticFile(p.audio)}/>}
  {p.music&&<Audio src={staticFile(p.music)} loop volume={frame=>Math.max(0,interpolate(frame,[0,45,d-90,d],[0,.095,.095,0],{extrapolateRight:'clamp'}))}/>}
 </AbsoluteFill>;
};

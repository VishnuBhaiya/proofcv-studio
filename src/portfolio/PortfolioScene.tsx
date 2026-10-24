import { useEffect, useRef, useState } from 'react';
import type { Project, PublicSite } from './types';

/** A self-contained CSS 3D composition: no remote assets, canvas or fake portrait. */
export default function PortfolioScene({site,projects,onProject}:{site:PublicSite;projects:Project[];onProject:(id:string)=>void}) {
 const [index,setIndex]=useState(0);
 const [moving,setMoving]=useState(()=>!window.matchMedia('(prefers-reduced-motion: reduce)').matches);
 const frame=useRef<HTMLDivElement>(null);
 const project=projects[index%Math.max(1,projects.length)];
 const image=site.assets.find(a=>a.project_id===project?.id&&a.mime.startsWith('image/'));
 useEffect(()=>{setIndex(0);},[projects.map(p=>p.id).join('|')]);
 useEffect(()=>{
  const query=window.matchMedia('(prefers-reduced-motion: reduce)');
  const change=()=>{if(query.matches)setMoving(false);};
  query.addEventListener('change',change);return()=>query.removeEventListener('change',change);
 },[]);
 function reset(){frame.current?.style.setProperty('--scene-x','0deg');frame.current?.style.setProperty('--scene-y','0deg');}
 useEffect(()=>{if(!moving)reset();},[moving]);
 return <aside className={`pf-scene ${moving?'is-moving':'is-still'}`} aria-label="Interactive project orbit">
  <div className="pf-scene-top"><span><i/> THE PROJECT ORBIT</span><button type="button" onClick={()=>setMoving(!moving)} aria-pressed={moving} aria-label={moving?'Pause 3D motion':'Enable 3D motion'}>{moving?'Ⅱ':'▷'} <span>{moving?'Pause motion':'Enable motion'}</span></button></div>
  <div className="pf-scene-space" ref={frame} onPointerMove={event=>{
   if(!moving||event.pointerType==='touch')return;
   const box=event.currentTarget.getBoundingClientRect();
   event.currentTarget.style.setProperty('--scene-x',`${((event.clientY-box.top)/box.height-.5)*-12}deg`);
   event.currentTarget.style.setProperty('--scene-y',`${((event.clientX-box.left)/box.width-.5)*16}deg`);
  }} onPointerLeave={reset}>
   <div className="pf-scene-grid" aria-hidden="true"/>
   <div className="pf-sculpture" aria-hidden="true"><div className="pf-orb-shadow"/><div className="pf-orbit pf-orbit-one"/><div className="pf-orbit pf-orbit-two"/><div className="pf-orbit pf-orbit-three"/><div className="pf-sphere"><div className="pf-sphere-grid"/><span>✦</span></div><div className="pf-orbit-satellite"/><div className="pf-scene-spark spark-one">+</div><div className="pf-scene-spark spark-two">+</div></div>
   <div className="pf-scene-coordinate" aria-hidden="true">IDEAS → WORK → IMPACT</div>
   <div className="pf-scene-label"><span>{String(site.projects.length).padStart(2,'0')}</span><small>projects.<br/>one story.</small></div>
   {project&&<button className={`pf-floating-project ${image?'has-image':''}`} type="button" onClick={()=>onProject(project.id)} aria-label={`Open case study: ${project.title}`}>
    {image?<img src={image.url} alt=""/>:<span className="pf-floating-symbol" aria-hidden="true">↗</span>}
    <span><small>EXPLORE THE SELECTED WORK</small><strong>{project.title}</strong><em>{project.technologies.split(',').slice(0,3).join(' · ')||'Contribution & context'}</em></span><b aria-hidden="true">↗</b>
   </button>}
  </div>
  <div className="pf-scene-bottom"><span>Not just a résumé.<br/><strong>A world of work.</strong></span><div className="pf-orbit-controls" aria-label="Browse project spotlight"><button type="button" disabled={projects.length<2} aria-label="Previous spotlight project" onClick={()=>setIndex(v=>(v-1+projects.length)%projects.length)}>←</button><span aria-live="polite">{projects.length?String(index%projects.length+1).padStart(2,'0'):'00'} / {String(projects.length).padStart(2,'0')}</span><button type="button" disabled={projects.length<2} aria-label="Next spotlight project" onClick={()=>setIndex(v=>(v+1)%projects.length)}>→</button></div></div>
 </aside>;
}

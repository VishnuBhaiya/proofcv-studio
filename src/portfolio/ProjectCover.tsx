import { useEffect,useRef,useState } from 'react';
import type { Project } from './types';
import { coverScene,EXHIBIT_LABELS } from './projectVisuals';
export { coverKind,coverScene,coverSeed } from './projectVisuals';

export default function ProjectCover({project,index,onOpen}:{project:Project;index:number;onOpen:()=>void}){
 const canvas=useRef<HTMLCanvasElement>(null),button=useRef<HTMLButtonElement>(null),[failed,setFailed]=useState(false);
 const scene=coverScene(project);
 useEffect(()=>{
  setFailed(false);
  let cancelled=false,started=false,dispose:(()=>void)|undefined;
  const start=()=>{if(started||cancelled)return;started=true;import('./projectCoverRenderer').then(mod=>{if(!cancelled&&canvas.current)dispose=mod.mountProjectCover(canvas.current,project,()=>{if(!cancelled)setFailed(true);});}).catch(()=>{if(!cancelled)setFailed(true);});};
  const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting))start();},{rootMargin:'160px'});if(button.current)observer.observe(button.current);
  return()=>{cancelled=true;observer.disconnect();dispose?.();};
 },[project.id,project.title,project.technologies]);
 return <button ref={button} type="button" className={`pf-project-world-cover scene-${scene}`} onClick={onOpen} aria-label={`Enter the 3D project world: ${project.title}`}>
  <canvas ref={canvas} aria-hidden="true"/>
  <span className="pf-world-cover-top"><span>3D WORLD / {EXHIBIT_LABELS[scene]}</span><b>{String(index+1).padStart(2,'0')}</b></span>
  {failed&&<span className="pf-world-cover-fallback">3D preview unavailable on this device.<small>Open the project world for its text and case-study fallback.</small></span>}
  <span className="pf-world-cover-bottom"><span>{project.technologies.split(',').slice(0,3).join(' / ')||'Explore the project context'}<small>Illustrative 3D scene · not project evidence</small></span><span className="pf-world-cover-enter">Enter the world <b>↗</b></span></span>
 </button>;
}

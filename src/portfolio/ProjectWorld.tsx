import { useEffect,useRef,useState } from 'react';
import type { Project,PublicSite,RoleView } from './types';
import { createWorld,type WorldEngine,type ExhibitionQuality } from './worldEngine';
import { projectShots } from './projectEnvironments';
import { coverScene,EXHIBIT_LABELS } from './projectVisuals';
import { exhibitEvidence } from './exhibitionEvidence';
import { projectTour,tourChapterAt,TOUR_SECONDS } from './projectTour';
import { recordSceneTour,sceneRecordingSupported } from './sceneRecorder';
import { createTourVoice } from './tourVoice';
import './projectTour.css';
import SceneFullscreen from './SceneFullscreen';

export default function ProjectWorld({project,site,view,quality,onClose,onCaseStudy}:{project:Project;site:PublicSite;view:RoleView;quality:ExhibitionQuality;onClose:()=>void;onCaseStudy:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null),stage=useRef<HTMLElement>(null),host=useRef<HTMLDivElement>(null),engine=useRef<WorldEngine|null>(null),close=useRef(onClose),alive=useRef(true);
 close.current=onClose;
 const [failed,setFailed]=useState(false),[shot,setShot]=useState(0),[notes,setNotes]=useState(false),[motion,setMotion]=useState(()=>!window.matchMedia('(prefers-reduced-motion: reduce)').matches);
 const [playing,setPlaying]=useState(false),[elapsed,setElapsed]=useState(0),[recording,setRecording]=useState(false),[recordAvailable,setRecordAvailable]=useState(false),[saved,setSaved]=useState<{url:string;bytes:number}|null>(null),[error,setError]=useState('');
 const playback=useRef({active:false,time:0,last:0,chapter:0}),recorder=useRef<ReturnType<typeof recordSceneTour>|null>(null),savedUrl=useRef('');
 const voice=useRef<ReturnType<typeof createTourVoice>|null>(null),voiceEnabled=useRef(true),narrated=useRef(false);
 const [voiceOn,setVoiceOn]=useState(true),[voiceAvailable,setVoiceAvailable]=useState(false),[voiceError,setVoiceError]=useState('');
 const frame=useRef<(canvas:HTMLCanvasElement)=>void>(()=>{}),manual=useRef<()=>void>(()=>{});
 const kind=coverScene(project),shots=projectShots(kind),evidence=exhibitEvidence(site,project,view),chapters=projectTour(project),chapter=chapters[tourChapterAt(elapsed)];
 function narrate(index:number){if(narrated.current&&voiceEnabled.current)voice.current?.speak(chapters[index].title,chapters[index].text);}
 function pause(){voice.current?.stop();playback.current.active=false;playback.current.last=0;setPlaying(false);setMotion(false);engine.current?.motion(false);if(recorder.current){recorder.current.stop();recorder.current=null;setRecording(false);}}
 manual.current=()=>{pause();setShot(-1);};
 frame.current=canvas=>{
  const p=playback.current;if(!p.active)return;
  const now=performance.now();p.time=Math.min(TOUR_SECONDS,p.time+(p.last?Math.min(.15,(now-p.last)/1000):0));p.last=now;
  const index=tourChapterAt(p.time);if(index!==p.chapter){p.chapter=index;setShot(index);engine.current?.focus(index);narrate(index);}
  if(Math.abs(p.time-elapsed)>.2||p.time===TOUR_SECONDS)setElapsed(p.time);
  try{recorder.current?.capture(canvas,p.time);}catch{setError('Recording stopped because this browser could not capture the scene.');pause();}
  if(p.time>=TOUR_SECONDS)pause();
 };
 useEffect(()=>{
  alive.current=true;setRecordAvailable(sceneRecordingSupported());
  voice.current=createTourVoice(window.speechSynthesis,typeof SpeechSynthesisUtterance==='undefined'?undefined:SpeechSynthesisUtterance,()=>{if(alive.current)setVoiceError('Browser voice is unavailable. The tour captions and full project notes are still available.');});
  setVoiceAvailable(voice.current.supported);
  const el=dialog.current,previous=document.activeElement instanceof HTMLElement?document.activeElement:null;
  const overflow=document.body.style.overflow;document.body.style.overflow='hidden';el?.showModal();
  try{if(host.current)engine.current=createWorld(host.current,{project,projects:[],quality,motion,onSelect:setShot,onInteract:()=>manual.current(),onFrame:canvas=>frame.current(canvas),onEscape:()=>close.current(),onError:()=>{setFailed(true);manual.current();}});}catch{setFailed(true);}
  return()=>{alive.current=false;voice.current?.stop();voice.current=null;playback.current.active=false;recorder.current?.discard();recorder.current=null;if(savedUrl.current)URL.revokeObjectURL(savedUrl.current);engine.current?.dispose();engine.current=null;el?.close();document.body.style.overflow=overflow;if(previous?.isConnected)previous.focus({preventScroll:true});};
 },[project.id,quality]);
 useEffect(()=>{engine.current?.motion(motion);},[motion]);
 useEffect(()=>{const q=window.matchMedia('(prefers-reduced-motion: reduce)'),change=()=>{if(q.matches)manual.current();};q.addEventListener('change',change);const hide=()=>{if(document.hidden)manual.current();};document.addEventListener('visibilitychange',hide);return()=>{q.removeEventListener('change',change);document.removeEventListener('visibilitychange',hide);};},[]);
 function start(from=0,withVoice=true){const p=playback.current;p.time=from;p.last=0;p.chapter=tourChapterAt(from);p.active=true;narrated.current=withVoice;setVoiceError('');narrate(p.chapter);setElapsed(from);setShot(p.chapter);engine.current?.focus(p.chapter);setPlaying(true);setMotion(true);engine.current?.motion(true);}
 function toggleVoice(){voiceEnabled.current=!voiceEnabled.current;setVoiceOn(voiceEnabled.current);voice.current?.stop();if(playback.current.active)narrate(playback.current.chapter);}
 function choose(index:number){pause();setShot(index);setElapsed(index*12);engine.current?.focus(index);}
 function record(){
  pause();setError('');
  try{const next=recordSceneTour(project,site.person.name,site.source_revision,chapters);recorder.current=next;
   next.result.then(value=>{if(!alive.current){if(value.url)URL.revokeObjectURL(value.url);return;}if(!value.url)return;if(savedUrl.current)URL.revokeObjectURL(savedUrl.current);savedUrl.current=value.url;setSaved(value);setNotes(true);}).catch(e=>{if(alive.current)setError(String(e));});
   next.start();setRecording(true);start(0,false);
  }catch(e){setError(String(e));}
 }
 return <dialog ref={dialog} className={`pf-project-world scene-${kind}`} aria-labelledby="project-world-title" onCancel={e=>{e.preventDefault();onClose();}}>
  <header className="pf-project-world-header"><div><span>PROJECT WORLD / {EXHIBIT_LABELS[kind]}</span><h2 id="project-world-title">{project.title}</h2></div><div className="pf-project-world-header-actions"><button type="button" aria-expanded={notes} aria-controls="project-world-notes" onClick={()=>setNotes(!notes)}>{notes?'Hide project notes':'Project notes & evidence'}</button><button type="button" autoFocus onClick={onClose} aria-label="Return to the floating island">← Back to the island</button></div></header>
  <div className={`pf-project-world-body ${notes?'has-notes':''}`}><section ref={stage} className="pf-project-world-stage" aria-label="Cinematic project environment">
   <SceneFullscreen target={stage} label="project environment"/>
   {failed?<div className="pf-project-world-fallback"><h3>The story is still here.</h3><p>3D is unavailable on this device. Read the confirmed project and reviewed evidence instead.</p><button type="button" onClick={onCaseStudy}>Open the case study ↗</button></div>:<div className="pf-project-world-canvas" ref={host}/>}
   <div className="pf-scene-tour-controls"><span>GUIDED SCENE TOUR <small>Illustration · browser voice on Play · 36 seconds</small></span><div><button type="button" disabled={failed} aria-pressed={playing} onClick={()=>playing?pause():start(elapsed>=TOUR_SECONDS?0:elapsed)}>{playing?'Ⅱ Pause tour':'▷ Play guided tour'}</button><button type="button" aria-label="Tour voice" aria-pressed={voiceOn&&voiceAvailable} disabled={!voiceAvailable||recording} onClick={toggleVoice}>{voiceAvailable?(voiceOn?'Voice on':'Voice off'):'Voice unavailable'}</button>{recording?<button type="button" onClick={pause}>Stop recording</button>:<button type="button" disabled={failed||!recordAvailable} onClick={record}>Save silent WebM</button>}</div>{(error||voiceError)&&<p role="alert">{error||voiceError}</p>}</div>
   {playing&&<div className="pf-scene-caption" aria-label="Tour chapter"><span>0{tourChapterAt(elapsed)+1} / {chapter.title}</span><p>{chapter.text.length>235?chapter.text.slice(0,232)+'…':chapter.text}</p><progress value={elapsed} max={TOUR_SECONDS} aria-label="Guided tour progress"/></div>}
   <nav className="pf-project-world-shots" aria-label="Cinematic camera views">{shots.map((s,i)=><button type="button" key={s.label} aria-pressed={shot===i} disabled={failed} onClick={()=>choose(i)}><span>0{i+1}</span>{s.label}</button>)}</nav>
   <div className="pf-project-world-tools"><span>{recording?'● Recording local illustrated walkthrough':playing?Math.floor(elapsed)+'s / 36s · guided scene walkthrough':'Two fingers to orbit · Pinch to zoom'}</span><div><button type="button" aria-label="Reset project camera" disabled={failed} onClick={()=>choose(0)}>Reset view</button><button type="button" aria-pressed={motion} disabled={failed} onClick={()=>{if(motion)pause();else{setMotion(true);engine.current?.motion(true);}}}>{motion?'Pause motion':'Enable motion'}</button></div></div>
  </section><aside hidden={!notes} id="project-world-notes" className="pf-project-world-story"><span className="pf-kicker">THE PROJECT, IN CONTEXT</span><p className="pf-project-world-description">{project.description}</p><div className="pf-project-world-tech">{project.technologies.split(',').map(t=>t.trim()).filter(Boolean).map(t=><span key={t}>{t}</span>)}</div><button type="button" className="pf-project-world-case" onClick={onCaseStudy}>Open the real case study ↗</button><p className="pf-project-world-note">This 3D environment is an original illustration—not a running model, real workplace or proof of results.</p>
   {saved&&<section className="pf-recorded-tour"><strong>Your recorded 3D walkthrough</strong><video src={saved.url} controls playsInline preload="metadata" aria-label="Recorded illustrative 3D scene tour"/><a href={saved.url} download={project.id+'-illustrative-tour.webm'}>Download WebM · {(saved.bytes/1048576).toFixed(1)} MB ↓</a><p>Silent illustrative video with source text. Not an actual project recording. Nothing was uploaded or added to your approved website.</p></section>}
   <details className="pf-project-world-sources"><summary>Inspect the confirmed source</summary><small>Source revision {site.source_revision}</small>{evidence.source?<blockquote>{evidence.source}</blockquote>:<p>No separate excerpt was disclosed for this project.</p>}</details><div className="pf-project-world-evidence"><strong>{evidence.assets.length} reviewed visual{evidence.assets.length===1?'':'s'}</strong><p>{evidence.assets.length?'The case study contains owner-reviewed media and source-linked explanations.':'No visual evidence was disclosed. The confirmed text is available without invented screenshots or results.'}</p></div></aside></div>
  <footer><span>ILLUSTRATIVE 3D ENVIRONMENT · NOT PROJECT EVIDENCE</span><button type="button" onClick={onCaseStudy}>Read the real case study ↗</button><span>Escape or Back returns to the island</span></footer>
 </dialog>;
}

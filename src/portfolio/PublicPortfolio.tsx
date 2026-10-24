import { useEffect, useRef, useState } from 'react';
import type { PublicSite } from './types';
import ProjectCover from './ProjectCover';
import MediaEvidence from './MediaEvidence';
import { mediaBadge } from './mediaPolicy';
import { isDemoPortfolio,profileEntries } from './projectTour';
import { connectedReaderUrl,ownerChatTarget } from './readerLink';
import './resumeOverview.css';
import PortfolioWorld from './PortfolioWorld';
import ProjectWorld from './ProjectWorld';
import type { ExhibitionQuality } from './worldEngine';
import './portfolio.css';
import './website-refresh.css';
import './immersive.css';
import './world.css';
import './covers.css';
import './exhibition.css';
import './projectWorld.css';
import './maxScene.css';

function meaningful(value:string) { return value && !['none','no','n/a'].includes(value.trim().toLowerCase()); }
function short(value:string) { return value.length > 210 ? value.slice(0,207).replace(/\s+\S*$/,'') + '…' : value; }

function AvatarGuide({site,suspended=false}:{site:PublicSite;suspended?:boolean}) {
 const [open,setOpen]=useState(false); const audio=useRef<HTMLAudioElement>(null);
 if(site.avatar==='none'||suspended) return null;
 return <aside className={`pf-guide pf-guide-${site.avatar}`} aria-label="AI virtual portfolio guide"><button className="pf-guide-toggle" onClick={()=>{if(open)audio.current?.pause();setOpen(!open);}} aria-expanded={open} aria-controls="pf-guide-body"><span className="pf-avatar" aria-hidden="true"><i/><i/><b>✦</b></span><span><strong>{site.avatar==='leaf'?'Sage':'Orbit'}</strong><small>AI portfolio guide · not the candidate</small></span><span>{open?'−':'+'}</span></button>{open&&<div id="pf-guide-body" className="pf-guide-body"><p>I’m a guide to {site.person.name.split(/\s+/)[0]}’s professional story—not the candidate. Choose where you’d like to start.</p><nav aria-label="Guided portfolio tour"><a href="#work" onClick={()=>{audio.current?.pause();setOpen(false);}}>01 · Explore the projects ↗</a><a href="#experience" onClick={()=>{audio.current?.pause();setOpen(false);}}>02 · Understand the experience ↗</a><a href="#ask" onClick={()=>{audio.current?.pause();setOpen(false);}}>03 · Ask about the approved sources ↗</a></nav>{site.narration?.url?<><span className="pf-kicker">THE APPROVED AUDIO INTRODUCTION</span><audio ref={audio} src={site.narration.url} controls preload="none"/><details><summary>Tour transcript</summary><p>{site.narration.script}</p></details></>:<p className="pf-note">No narrated tour was approved for this version. The text tour above is available without audio.</p>}<small>I cannot verify skills, speak for the candidate or make commitments.</small></div>}</aside>;
}

function RecruiterChat({site,onProject}:{site:PublicSite;onProject:(id:string)=>void}) {
 const ownerChat=ownerChatTarget(site,window.location);
 const readerConnected=!!site.id && window.location.port==='8001' && window.location.pathname.startsWith('/site/'+site.id+'/');
 const connected=readerConnected||!!ownerChat;
 const readerUrl=connectedReaderUrl(site);
 const [question,setQuestion]=useState('');const [busy,setBusy]=useState(false);const [answer,setAnswer]=useState('');const [error,setError]=useState('');const [sources,setSources]=useState<{id:string;text:string}[]>([]);const [project,setProject]=useState('');
 const request=useRef<AbortController|null>(null);
 useEffect(()=>()=>{request.current?.abort();},[site.id,site.owner_chat?.snapshot_id]);
 async function ask(event:React.FormEvent){event.preventDefault();if(!connected||request.current||!question.trim())return;const controller=new AbortController();request.current=controller;setBusy(true);setError('');setAnswer('');setSources([]);setProject('');try{const response=await fetch(ownerChat?.url||`/site/${site.id}/chat`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',signal:controller.signal,body:JSON.stringify(ownerChat?{question,snapshot_id:ownerChat.snapshot_id}:{question})});const value=await response.json();if(!response.ok)throw new Error(value.error||'The guide could not answer. Please try again.');if(!controller.signal.aborted){setAnswer(value.answer);setSources(value.sources);setProject(site.projects.some(p=>p.id===value.project_id)?value.project_id:'');}}catch(e){if(!controller.signal.aborted)setError(String(e));}finally{if(request.current===controller)request.current=null;if(!controller.signal.aborted)setBusy(false);}}
 return <section className="pf-chat" id="ask">
  <div><span className="pf-kicker">04 / A CONVERSATION WITH CONTEXT</span><h2>Go beyond<br/><em>the overview.</em></h2><p>Ask about the work, experience or contribution. The AI guide answers from the approved portfolio and shows its sources.</p>
   {connected&&<div className="pf-chat-suggestions" aria-label="Suggested recruiter questions">{['Which projects are most relevant?','What did the candidate personally contribute?','Summarise the confirmed work experience.'].map(q=><button key={q} type="button" disabled={busy} onClick={()=>{setQuestion(q);document.getElementById('pf-question')?.focus();}}>{q} ↗</button>)}</div>}
   <p className="pf-note">The guide is not the candidate. It cannot promise availability, certify skills or access private records.</p>
  </div>
  <div>{connected?<>{ownerChat&&<p className="pf-note pf-chat-context"><strong>Live AI · ask here in the preview.</strong> Answers use your saved, approved portfolio{ownerChat.approved_at?' from '+new Date(ownerChat.approved_at).toLocaleDateString():''}, not private draft changes. Approve an updated version to include new edits.</p>}<form onSubmit={ask}><label htmlFor="pf-question">What would you like to understand?</label><textarea id="pf-question" value={question} maxLength={1200} disabled={busy} onChange={e=>setQuestion(e.target.value)} placeholder="Ask about a project, responsibility or technical approach…"/><button disabled={busy||!question.trim()}>{busy?'Reading the approved sources…':'Ask the live portfolio guide ↗'}</button></form><p className="pf-note"><i className="pf-dot"/> {ownerChat?'Connected in this preview':'Connected to the local reader'} · questions are sent to Gemini. Conversations are not saved here; request budgets apply.</p></>:<div className="pf-guide-connection"><span className="pf-kicker">ASK THE APPROVED PORTFOLIO</span><h3>Your live guide opens on the recruiter website.</h3>{readerUrl?<><a className="pf-primary" href={readerUrl} target="_blank" rel="noopener noreferrer">Open live AI guide ↗</a><p className="pf-note">Opens the saved, approved recruiter version in a new tab. Unapproved draft changes are not sent to the AI.</p></>:<><p>Approve and connect a version once to enable questions in both websites.</p><details><summary>How to connect the AI guide</summary><ol><li>In Portfolio Studio, review and approve the website.</li><li>Choose “Open recruiter website” for that approved version, then reload this preview.</li><li>The preview and recruiter website both have their own live question form.</li></ol></details></>}<p className="pf-note">All project stories and reviewed media remain available here without AI.</p></div>}
   {error&&<p role="alert" className="pf-error">{error}</p>}{answer&&<div className="pf-answer" aria-live="polite"><span className="pf-kicker">FROM THE APPROVED PORTFOLIO</span><p>{answer}</p>{sources.length>0&&<details><summary>Read the source excerpts ({sources.length})</summary>{sources.map(s=><blockquote key={s.id}>{s.text}</blockquote>)}</details>}{project&&<button onClick={()=>onProject(project)}>Explore the referenced project ↗</button>}</div>}
  </div>
 </section>;
}

export default function PublicPortfolio({site}:{site:PublicSite}) {
 const [viewId,setViewId]=useState('general');const [theme,setTheme]=useState(site.theme);const [expanded,setExpanded]=useState<string[]>([]); const [skill,setSkill]=useState('');
 const [section,setSection]=useState('');
 const [worldActive,setWorldActive]=useState(true);
 const [worldProjectId,setWorldProjectId]=useState<string|null>(null),[worldQuality,setWorldQuality]=useState<ExhibitionQuality>('balanced');
 const worldProject=site.projects.find(p=>p.id===worldProjectId);
 function openWorld(id:string,quality:ExhibitionQuality='balanced'){setWorldQuality(quality);setWorldProjectId(id);}
 useEffect(()=>{const active=new Map<string,number>();const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting)active.set(entry.target.id,entry.intersectionRatio);else active.delete(entry.target.id);}setSection([...active].sort((a,b)=>b[1]-a[1])[0]?.[0]||'');},{rootMargin:'-15% 0px -55% 0px',threshold:[0,.1,.5]});for(const id of ['profile-intro','work','experience','about','ask']){const el=document.getElementById(id);if(el)observer.observe(el);}return()=>observer.disconnect();},[]);
 useEffect(()=>{setTheme(site.theme);setViewId('general');},[site.theme,site.source_revision]);
 const view=site.views.find(v=>v.id===viewId)||site.views[0];
 const ordered=[...view.project_ids.map(id=>site.projects.find(p=>p.id===id)).filter((p):p is PublicSite['projects'][number]=>!!p),...site.projects.filter(p=>!view.project_ids.includes(p.id))];
 const initials=site.person.name.trim().split(/\s+/).map(w=>w[0]).slice(0,2).join('');
 const featuredCount=view.project_ids.length;
 const demo=isDemoPortfolio(site.person.name),education=profileEntries(site.person.education),employment=profileEntries(site.person.experience);
 function focusProject(id:string){setExpanded(v=>v.includes(id)?v:[...v,id]);requestAnimationFrame(()=>document.getElementById('project-'+id)?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'}));}
 function focusSkill(value:string){setSkill(value);const project=ordered.find(p=>(p.technologies+' '+p.description).toLowerCase().includes(value.toLowerCase()));if(project)focusProject(project.id);}
 return <div className={`pf-site pf-${theme}`} id="top"><a className="pf-skip" href="#pf-main">Skip to content</a>

  <header className="pf-nav">
   <a href="#top" className="pf-identity"><b>{initials}</b><span>{site.person.name}<small>{demo?<span className="pf-demo-label">DEMO CV</span>:'Professional portfolio'}</small></span></a>
   <nav aria-label="Portfolio">{[['profile-intro','Résumé'],['work','Work'],['experience','Experience'],['about','About'],['ask','Ask the guide']].map(([id,label])=><a key={id} href={'#'+id} aria-current={section===id?'location':undefined}>{label}</a>)}</nav>
   <label className="pf-theme-label"><span>Appearance</span><select aria-label="Portfolio theme" value={theme} onChange={e=>setTheme(e.target.value as PublicSite['theme'])}><option value="editorial">Editorial</option><option value="technical">Technical</option><option value="minimal">Minimal</option></select></label>
  </header>
  <main id="pf-main">
   <PortfolioWorld site={site} projects={ordered} view={view} onViewChange={id=>{setViewId(id);setSkill('');}} onProject={focusProject} onActiveChange={setWorldActive} onProjectWorld={openWorld} sceneOpen={!!worldProject}/>
   <section className="pf-hero" id="profile-intro">
    <div className="pf-hero-copy"><span className="pf-kicker"><i className="pf-dot"/> A PROFESSIONAL STORY. IN ANOTHER DIMENSION.</span><h1>{site.person.name.trim().split(/\s+/).map((word,index)=><span className="pf-name-word" key={index}>{word}{index===site.person.name.trim().split(/\s+/).length-1&&<b>.</b>} </span>)}</h1><p className="pf-headline">{site.headline||site.person.goal}</p><div className="pf-bio-block"><p className="pf-bio">{short(site.bio||'Explore my confirmed experience and selected projects below.')}</p>{site.bio.length>210&&<details className="pf-full-story"><summary>Read the full introduction <span>↗</span></summary><p className="pf-lines">{site.bio}</p></details>}</div><div className="pf-hero-actions"><a className="pf-primary" href="#work">Explore the work <span>↗</span></a>{site.cv_url?<a className="pf-secondary" href={site.cv_url} download>Download CV ↓</a>:<a className="pf-secondary" href="#experience">My experience →</a>}</div><div className="pf-hero-footnote"><span>{site.person.location?'↗ '+site.person.location:'A professional story, in context'}</span><span>AI-assisted · owner-reviewed</span></div></div>
    <aside className="pf-profile-facts" aria-label="CV at a glance"><span className="pf-kicker">AT A GLANCE</span><dl><div><dt>EDUCATION</dt><dd>{education[0]?.split('\n')[0]||'Not listed'}</dd></div><div><dt>EXPERIENCE</dt><dd>{employment[0]?.split('\n')[0]||'No employment experience listed'}</dd></div><div><dt>WORK & TOOLKIT</dt><dd>{site.projects.length} projects · {site.person.skills.length} profile-listed skills</dd></div></dl><a href="#about">Education, achievements & skills ↓</a></aside>
   </section>
   <section className="pf-role" aria-label="Role-specific portfolio views"><div><span className="pf-kicker">THE ROLE LENS</span><p>Same person.<br/><em>A different focus.</em></p></div><div className="pf-role-options">{site.views.map(v=><button key={v.id} aria-pressed={v.id===view.id} onClick={()=>{setViewId(v.id);setSkill('');}}><span>{v.id==='general'?'The full picture':v.title}</span><span aria-hidden="true">{v.id===view.id?'↗':'→'}</span></button>)}</div><details><summary>Why this perspective?</summary><p>{view.rationale}</p><small>Only emphasis changes. All confirmed projects and experience remain accessible.</small></details></section>
   <section id="work" className="pf-work"><div className="pf-section-heading"><div><span className="pf-kicker">01 / SELECTED WORK</span><h2>The work behind<br/><em>the words.</em></h2></div><div><p>Follow the idea, understand the contribution, and inspect the evidence.</p><span className="pf-work-count">{featuredCount} featured · {site.projects.length} in the full library</span></div></div>
    <div className="pf-skills" aria-label="Skills in this view">{view.skills.map(s=><button key={s} aria-pressed={skill===s} onClick={()=>focusSkill(s)}>{s}<span aria-hidden="true"> ↗</span></button>)}</div>
    {skill&&<p className="pf-note" role="status">{ordered.some(p=>(p.technologies+' '+p.description).toLowerCase().includes(skill.toLowerCase()))?`Opened project text mentioning ${skill}.`:`${skill} is listed in the confirmed profile; no project text explicitly mentions it.`} A listing or visual is not independent verification of proficiency.</p>}
    <div className="pf-project-grid">{ordered.map((p,index)=>{
     const assets=site.assets.filter(a=>a.project_id===p.id), isOpen=expanded.includes(p.id), featured=view.project_ids.includes(p.id);
     return <article className={`pf-project ${featured?'pf-featured':''} ${isOpen?'is-open':''} ${index===0?'pf-lead-project':''} ${index%3===0?'pf-wide-project':''}`} id={'project-'+p.id} key={p.id}>
      <div className="pf-project-top"><span>{String(index+1).padStart(2,'0')} / {featured?'IN THIS PERSPECTIVE':'MORE FROM THE PROFILE'}</span><span>{assets.length?`${assets.length} reviewed visual${assets.length===1?'':'s'}`:'Text-first case study'}</span></div>
      <ProjectCover project={p} index={index} onOpen={()=>openWorld(p.id)}/>
      <div className="pf-project-copy"><h3>{p.title}</h3><button type="button" className="pf-library-world-link" onClick={()=>openWorld(p.id)}>Explore the 3D project world ↗</button><p className="pf-lines">{isOpen?p.description:short(p.description)}</p><div className="pf-tech-chips">{p.technologies.split(',').map(t=>t.trim()).filter(Boolean).map(t=><span key={t}>{t}</span>)}</div><button className="pf-case-button" aria-expanded={isOpen} aria-controls={'case-'+p.id} onClick={()=>setExpanded(v=>isOpen?v.filter(id=>id!==p.id):[...v,p.id])}>{isOpen?'Close the story −':'Explore the project +'}<span className="pf-read-label">{assets.some(a=>a.mime.startsWith('video/'))?mediaBadge(assets.find(a=>a.mime.startsWith('video/'))!):assets.length?'Reviewed visual notes':'Contribution & context'}</span></button>
       {isOpen&&<div id={'case-'+p.id} className="pf-case"><div className="pf-case-intro"><span className="pf-kicker">THE CONTRIBUTION, IN CONTEXT</span><p>Project text is candidate-confirmed, not independently verified. Visuals explain what can be seen; contribution and outcome claims link back to confirmed sources.</p></div>{assets.length?assets.map(a=><MediaEvidence key={a.id} asset={a} sources={site.sources}/>):<p className="pf-note">No visual material was selected for this project. The full confirmed project description appears above; no demonstration or results have been invented.</p>}</div>}
      </div>
     </article>;
    })}</div>
   </section>
   <section id="experience" className="pf-career"><div><span className="pf-kicker">02 / EXPERIENCE</span><h2>More than<br/><em>a title.</em></h2><p className="pf-section-aside">The responsibilities, work and context behind the profile. Available in every role view.</p></div><div className="pf-timeline">{meaningful(site.person.experience)?site.person.experience.split(/\n\s*\n/).map((part,index)=>{const [heading,...body]=part.split('\n');return <div className="pf-career-entry" key={index}><span className="pf-timeline-index">{String(index+1).padStart(2,'0')}</span>{body.length?<><h3>{heading}</h3><p className="pf-lines">{body.join('\n')}</p></>:<p className="pf-lines">{part}</p>}</div>;}):<p>No employment experience is listed in this approved profile.</p>}</div></section>
   <section id="about" className="pf-about"><div><span className="pf-kicker">03 / FOUNDATIONS</span><h2>Always learning.<br/><em>Always building.</em></h2><p className="pf-section-aside">Education, achievements and the full set of profile-listed skills.</p></div><div className="pf-foundations"><section><span className="pf-kicker">EDUCATION</span>{site.person.education.split(/\n\s*\n/).map((entry,i)=><p className="pf-lines" key={i}>{entry}</p>)}</section>{meaningful(site.person.achievements)&&<section><span className="pf-kicker">ACHIEVEMENTS</span><p className="pf-lines">{site.person.achievements}</p></section>}<section><span className="pf-kicker">THE FULL TOOLKIT</span><div className="pf-toolkit">{site.person.skills.map(s=><span key={s}>{s}</span>)}</div></section></div></section>
   <RecruiterChat site={site} onProject={focusProject}/>
  </main>
  <footer className="pf-footer" id="contact"><div className="pf-footer-top"><div><span className="pf-kicker">CONTINUE THE CONVERSATION</span><h2>A next chapter<br/><em>starts with hello.</em></h2></div><a className="pf-back-top" href="#top" aria-label="Back to top">↑</a></div><div className="pf-contact-links">{site.person.links.map(l=><a key={l.label} href={l.url} target="_blank" rel="noopener noreferrer">{l.label} ↗</a>)}{site.person.email&&<a href={'mailto:'+site.person.email}>{site.person.email} ↗</a>}{site.person.phone&&<span>{site.person.phone}</span>}{site.cv_url&&<a href={site.cv_url} download>Download CV ↓</a>}{!site.person.links.length&&!site.person.email&&!site.person.phone&&<span>No contact details were selected for public disclosure.</span>}</div><div className="pf-footer-meta"><span>{site.person.name} / Built with ProofCV Showcase</span><span>AI-assisted · owner-reviewed · source revision {site.source_revision}{site.approved_at?' · '+new Date(site.approved_at).toLocaleDateString(): ' · unapproved preview'}</span></div></footer><AvatarGuide site={site} suspended={worldActive||!!worldProject}/>{worldProject&&<ProjectWorld project={worldProject} site={site} view={view} quality={worldQuality} onClose={()=>setWorldProjectId(null)} onCaseStudy={()=>{setWorldProjectId(null);focusProject(worldProject.id);}}/>
 }
 </div>;
}

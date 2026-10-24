import { useEffect, useId, useRef, useState } from 'react';
import type { Asset, Hotspot } from './types';
import { activeChapterIndex, formatMediaTime, mediaPolicy, normaliseChapters } from './mediaPolicy';
import './mediaEvidence.css';

function SourceNotes({region,sources}:{region?:Hotspot;sources:Record<string,string>}) {
 const ids=[...new Set(region?.source_ids||[])].filter(id=>sources[id]);
 return ids.length?<details className="pf-media-sources"><summary>Inspect confirmed source excerpts ({ids.length})</summary>{ids.map(id=><blockquote key={id}>{sources[id]}</blockquote>)}</details>:<p className="pf-media-small">No extra source excerpt is linked to this observation. A visual alone does not establish the candidate’s contribution.</p>;
}

function EvidenceBody({asset,sources}:{asset:Asset;sources:Record<string,string>}) {
 const analysis=asset.analysis!;
 const [selected,setSelected]=useState(0),[tab,setTab]=useState<'observation'|'contribution'|'limits'>('observation');
 const [currentTime,setCurrentTime]=useState(0),[duration,setDuration]=useState(asset.duration),[ready,setReady]=useState(false),[failed,setFailed]=useState(false),[notice,setNotice]=useState('');
 const video=useRef<HTMLVideoElement>(null),pendingSeek=useRef<number|null>(null),tabRefs=useRef<(HTMLButtonElement|null)[]>([]);
 const id=useId(),policy=mediaPolicy(asset),chapters=normaliseChapters(analysis.chapters,duration),active=activeChapterIndex(chapters,currentTime);
 const hotspots=analysis.hotspots||[],region=hotspots[selected];
 useEffect(()=>{setSelected(0);setCurrentTime(0);setDuration(asset.duration);setReady(false);setFailed(false);setNotice('');pendingSeek.current=null;},[asset.id,asset.url,asset.duration]);
 async function seek(time:number){
  const player=video.current;if(!player)return;
  if(player.readyState===0){pendingSeek.current=time;player.load();return;}
  player.currentTime=Math.min(time,Number.isFinite(player.duration)?Math.max(0,player.duration-.01):time);
  setCurrentTime(player.currentTime);player.focus();
  try{await player.play();setNotice('');}catch{setNotice('Chapter selected. Press Play in the video controls to start.');}
 }
 const tabs=[{id:'observation',label:'What it shows'},{id:'contribution',label:'Contribution'},{id:'limits',label:'Limits & context'}] as const;
 function switchTab(index:number){const next=(index+tabs.length)%tabs.length;setTab(tabs[next].id);tabRefs.current[next]?.focus();}
 const text=tab==='observation'?(region?.visible||analysis.description||'No additional visual observation was supplied.')
  :tab==='contribution'?(region?.contribution||'See the confirmed project description above for the candidate’s contribution. This media does not independently establish authorship.')
  :(region?.outcome||policy.explanation);
 return <div className="pf-media-body">
  <div className={`pf-media-stage ${policy.video?'is-video':'is-image'}`}>
   {policy.video?<>
    <video ref={video} src={asset.url} controls preload="metadata" playsInline aria-label={analysis.caption||'Reviewed project video'}
     onLoadedMetadata={()=>{const player=video.current;if(!player)return;setReady(true);if(Number.isFinite(player.duration)&&player.duration>0)setDuration(player.duration);if(pendingSeek.current!==null){const at=pendingSeek.current;pendingSeek.current=null;void seek(at);}}}
     onTimeUpdate={()=>setCurrentTime(video.current?.currentTime||0)} onSeeked={()=>setCurrentTime(video.current?.currentTime||0)}
     onError={()=>{setFailed(true);setReady(false);setNotice('');}}/>
    {!ready&&!failed&&<p className="pf-media-loading" role="status">Loading video details…</p>}
    {failed&&<div className="pf-media-unavailable" role="status"><strong>This video could not be played.</strong><p>The reviewed explanation and chapter notes remain below.</p>{asset.url&&<a href={asset.url} download>Download the original clip ↗</a>}<button type="button" onClick={()=>{setFailed(false);video.current?.load();}}>Retry loading</button></div>}
   </>:<div className="pf-image-wrap"><img src={asset.url} alt={analysis.alt||analysis.caption} loading="lazy" onError={()=>setFailed(true)}/>{!failed&&hotspots.map((h,index)=><button type="button" key={h.id} className={`pf-hotspot ${index===selected?'selected':''}`} aria-label={`Explore ${h.title}`} aria-pressed={index===selected} style={{left:h.rect[0]*100+'%',top:h.rect[1]*100+'%',width:h.rect[2]*100+'%',height:h.rect[3]*100+'%'}} onClick={()=>{setSelected(index);setTab('observation');}}><span>{index+1}</span></button>)}{failed&&<p role="status">Image unavailable. The reviewed explanation remains below.</p>}</div>}
  </div>
  {policy.video&&<div className="pf-media-transport-meta"><span>▶ {formatMediaTime(currentTime)} <span aria-hidden="true">/</span> {formatMediaTime(duration)}</span><span>{analysis.transcript?.trim()?'Reviewed transcript available':'No speech transcript supplied'}</span></div>}
  {notice&&<p className="pf-media-small" role="status">{notice}</p>}
  {policy.video&&chapters.length>0&&<section className="pf-media-chapter-section" aria-label="Video chapters"><div className="pf-media-section-label"><span>CHAPTERS</span><small>Select a chapter to play from that point</small></div><div className="pf-media-chapter-list">{chapters.map((chapter,index)=><button type="button" key={chapter.time} onClick={()=>void seek(chapter.time)} aria-current={index===active?'step':undefined} disabled={failed}><span>{formatMediaTime(chapter.time)}</span><strong>{chapter.title}</strong><small>{chapter.description}</small></button>)}</div></section>}
  <div className="pf-media-notes">
   <h4>{analysis.caption||policy.label}</h4>
   {hotspots.length>0&&<div className="pf-media-regions" aria-label="Annotated image regions">{hotspots.map((h,index)=><button type="button" key={h.id} onClick={()=>{setSelected(index);setTab('observation');}} aria-pressed={selected===index}>{String(index+1).padStart(2,'0')} · {h.title}</button>)}</div>}
   {region&&<p className="pf-media-region-title">{region.title}</p>}
   <div className="pf-media-note-tabs" role="tablist" aria-label="Understand this media">{tabs.map((item,index)=><button key={item.id} ref={el=>{tabRefs.current[index]=el;}} type="button" id={id+'-tab-'+item.id} role="tab" aria-selected={tab===item.id} aria-controls={id+'-notes'} tabIndex={tab===item.id?0:-1} onClick={()=>setTab(item.id)} onKeyDown={event=>{if(['ArrowRight','ArrowLeft','Home','End'].includes(event.key)){event.preventDefault();switchTab(event.key==='Home'?0:event.key==='End'?tabs.length-1:index+(event.key==='ArrowRight'?1:-1));}}}>{item.label}</button>)}</div>
   <div className="pf-media-note-panel" id={id+'-notes'} role="tabpanel" aria-labelledby={id+'-tab-'+tab} tabIndex={0}><p className="pf-lines">{text}</p>{tab==='limits'&&<><p className="pf-media-small">{policy.explanation}</p>{(analysis.warnings||[]).length>0&&<ul>{analysis.warnings.map((warning,i)=><li key={i}>{warning}</li>)}</ul>}</>}{tab==='contribution'&&<SourceNotes region={region} sources={sources}/>}</div>
   {policy.video&&<details className="pf-media-transcript"><summary>{analysis.transcript?.trim()?'Read the reviewed transcript':'Transcript & accessibility notes'}</summary><p className="pf-lines">{analysis.transcript?.trim()||'No speech transcript was supplied for this clip. The reviewed descriptions and chapter notes above provide its text explanation; they are not invented speech or timed captions.'}</p></details>}
  </div>
 </div>;
}

export default function MediaEvidence({asset,sources}:{asset:Asset;sources:Record<string,string>}) {
 const [open,setOpen]=useState(false),policy=mediaPolicy(asset);
 if(policy.kind==='unreviewed')return <section className="pf-media-evidence pf-media-unreviewed"><p>{policy.label}</p><small>{policy.explanation}</small></section>;
 if(policy.kind==='illustrative')return <details className="pf-media-evidence pf-media-reference" open={open} onToggle={event=>setOpen(event.currentTarget.open)}><summary><span><span className="pf-media-eyebrow">ILLUSTRATIVE REFERENCE · NOT PROJECT EVIDENCE</span><strong>{asset.analysis?.caption||policy.label}</strong><small>{policy.video?formatMediaTime(asset.duration)+' clip':'Annotated illustration'} · optional background material</small></span><span className="pf-media-expand" aria-hidden="true">{open?'−':'+'}</span></summary><p className="pf-media-reference-note">{policy.explanation}</p>{open&&<EvidenceBody asset={asset} sources={sources}/>}</details>;
 return <section className="pf-media-evidence" aria-label={asset.analysis?.caption||policy.label}><div className="pf-media-evidence-header"><span className="pf-media-eyebrow">{policy.label}</span><span>{policy.video?formatMediaTime(asset.duration):'Annotated image'} · owner-reviewed</span></div><EvidenceBody asset={asset} sources={sources}/></section>;
}

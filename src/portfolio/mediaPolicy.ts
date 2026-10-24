import type { Asset, Analysis } from './types';

export type MediaPolicy = {
 kind:'illustrative'|'reviewed'|'unreviewed';
 video:boolean;
 label:string;
 explanation:string;
};

/** Classify only explicit labels, never infer that a reviewed upload is authentic. */
export function mediaPolicy(asset:Asset):MediaPolicy {
 const video=asset.mime.startsWith('video/');
 const analysis=asset.analysis;
 if(!analysis)return {kind:'unreviewed',video,label:'Awaiting media review',explanation:'This upload has no accepted explanation and is not presented as reviewed evidence.'};
 const labels=[asset.name,analysis.caption,analysis.alt,analysis.description,...(analysis.warnings||[])].filter(Boolean).join(' ');
 const illustrative=/\b(synthetic|fictional|illustrat(?:ive|ion|ed)|simulated|evaluation diagram)\b|not (?:a |an )?(?:real|actual|product) (?:screenshot|recording|demo)|not project evidence/i.test(labels);
 return illustrative
  ? {kind:'illustrative',video,label:video?'Illustrative reference clip':'Illustrative reference',explanation:'A labelled illustration, not a recording of the candidate’s actual project or proof of its results. The confirmed project text remains the source for contribution claims.'}
  : {kind:'reviewed',video,label:video?'Reviewed project video':'Reviewed visual material',explanation:'The owner accepted this explanation. Review is not independent verification of authorship, skills or results.'};
}

export function mediaBadge(asset:Asset):string {
 const policy=mediaPolicy(asset);
 return policy.kind==='illustrative'?(policy.video?'Reference clip':'Reference illustration'):policy.kind==='unreviewed'?'Unreviewed upload':policy.video?'Reviewed video':'Reviewed image';
}

export function formatMediaTime(seconds:number):string {
 const total=Number.isFinite(seconds)&&seconds>0?Math.floor(seconds):0;
 const hours=Math.floor(total/3600),minutes=Math.floor(total%3600/60),rest=String(total%60).padStart(2,'0');
 return hours?`${hours}:${String(minutes).padStart(2,'0')}:${rest}`:`${minutes}:${rest}`;
}

/** Defensive reader normalization for older exports. It does not invent chapters. */
export function normaliseChapters(chapters:Analysis['chapters']|undefined,duration:number):Analysis['chapters'] {
 const limit=Number.isFinite(duration)&&duration>0?duration:Infinity;
 const sorted=(chapters||[]).filter(c=>Number.isFinite(c.time)&&c.time>=0&&c.time<limit&&typeof c.title==='string'&&c.title.trim()).map(c=>({...c,title:c.title.trim(),description:typeof c.description==='string'?c.description:''})).sort((a,b)=>a.time-b.time);
 return sorted.filter((c,i)=>i===0||c.time!==sorted[i-1].time).slice(0,6);
}

export function activeChapterIndex(chapters:Analysis['chapters'],time:number):number {
 if(!Number.isFinite(time)||time<0)return -1;
 let result=-1;
 for(let i=0;i<chapters.length;i++){if(chapters[i].time>time)break;result=i;}
 return result;
}

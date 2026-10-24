import type { Portfolio, Pending } from './types';

export const STEPS = [
    {id:'content', title:'Your story', description:'Shape the introduction', number:'01'},
    {id:'media', title:'Show the work', description:'Review visual evidence', number:'02'},
    {id:'design', title:'Make it yours', description:'Style, guide & narration', number:'03'},
    {id:'preview', title:'See the website', description:'Explore before sharing', number:'04'},
    {id:'publish', title:'Review & export', description:'Choose what leaves', number:'05'},
] as const;
export type Step = typeof STEPS[number]['id'];
export function isStep(value:unknown):value is Step { return STEPS.some(s=>s.id===value); }
export function proposalStep(kind:Pending['kind']):Step { return kind==='site'?'content':kind==='analysis'?'media':'design'; }
export function afterOperation(operation:string, choice:unknown, kind:Pending['kind']|undefined, current:Step):Step {
    if(operation==='portfolio-init') return 'content';
    if(operation==='portfolio-propose'||operation==='portfolio-edit-site') return 'content';
    if(operation==='portfolio-analyse'||operation==='portfolio-edit-analysis') return 'media';
    if(operation==='portfolio-narrate') return 'design';
    if(operation==='portfolio-approve') return 'publish';
    if(operation==='portfolio-save'&&current==='design') return 'preview';
    if(operation==='portfolio-save'&&current==='media') return 'design';
    if(operation==='portfolio-review' && choice==='accept') {
        if(kind==='site') return 'media';
        if(kind==='narration') return 'preview';
        return 'media'; // More assets may need review/disclosure. Never auto-publish.
    }
    return current;
}
export function preferredStep(p:Portfolio, remembered:unknown):Step {
    if(p.pending)return proposalStep(p.pending.kind);
    return isStep(remembered)?remembered:'content';
}
export function hasStory(p:Portfolio):boolean { return p.events.some(e=>e.kind==='accepted'&&e.proposal_kind==='site'); }
export function progress(p:Portfolio) {
    return {reviewed:p.assets.filter(a=>a.analysis).length, disclosed:p.assets.filter(a=>a.published&&a.analysis).length,
        awaiting:p.assets.filter(a=>!a.analysis).length, roles:p.views.filter(v=>v.id!=='general').length,
        story:hasStory(p), snapshots:p.snapshots.length};
}

/** Only the most recently issued request may replace the visible saved state. */
export function requestSequence(){let latest=0;return {begin:()=>++latest,isCurrent:(id:number)=>id===latest,invalidate:()=>{latest++;}};}
export function afterVisualReview(p:Portfolio):Step{return p.assets.some(a=>!a.analysis&&a.id!==p.pending?.asset_id)?'media':'design';}

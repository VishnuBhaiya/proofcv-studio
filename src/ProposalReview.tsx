import { useState } from 'react';
import type { Profile, ProfileProposal } from './api';
import './proposal-review.css';

const labels: Record<string,string> = {name:'Name',email:'Email',phone:'Phone',goal:'Target roles',education:'Education',experience:'Experience',achievements:'Achievements',skills:'Skills',summary_facts:'Summary facts',location:'Location',linkedin:'LinkedIn',github:'GitHub',portfolio:'Portfolio'};
function TextValue({value, changed=false}:{value:unknown;changed?:boolean}) {
    if (Array.isArray(value)) return value.length ? <ul className={changed ? 'review-changed' : ''}>{value.map((v,i)=><li key={i}>{String(v)}</li>)}</ul> : <p className="review-empty">Nothing added yet</p>;
    return <p className={changed ? 'review-changed' : ''}>{String(value || 'Nothing added yet')}</p>;
}
export default function ProposalReview({proposal,profile,busy,error,dirty,review}:{proposal:ProfileProposal;profile:Profile;busy:boolean;error?:string;dirty?:boolean;review:(choice:string,patch?:Partial<Profile>,projectSkills?:{project_index:number;skills:string[]})=>void}) {
    const [patch,setPatch]=useState<Partial<Profile>>(()=>structuredClone(proposal.patch));
    const [editing,setEditing]=useState(false);
    const [chosen,setChosen]=useState<string[]>([]);
    const [destination,setDestination]=useState('skills');
    const [target,setTarget]=useState('');
    const availableProjects=patch.projects || profile.projects;
    const projects=patch.projects;
    const invalid=projects?.some(p=>!p.title.trim() || !p.description.trim());
    function projectField(index:number,key:'title'|'description'|'technologies',value:string) {
        setPatch(previous=>({...previous,projects:previous.projects!.map((p,i)=>i===index?{...p,[key]:value}:p)}));
    }
    return <section className="profile-proposal readable-review" aria-label="Proposed profile changes">
        <h3>How does this sound?</h3><p>Review the suggested wording before adding it to your profile.</p>
        <blockquote>{proposal.source}</blockquote>
        {proposal.warnings?.map((warning,i)=><p role="note" key={i}>{warning}</p>)}
        {dirty && <p>Your form has unsaved edits. Accept saves those edits too; the suggested fields shown here replace any edits to the same fields. Use Edit suggestion to adjust them first.</p>}
        {Object.entries(patch).map(([field,value])=>field==='projects' ? <div key={field}>
            {projects!.map((project,i)=>{
                const before=profile.projects[i];
                const changed=!before || Object.keys(project).some(k=>project[k as keyof typeof project]!==before[k as keyof typeof project]);
                if(!changed && !editing) return null;
                return <article className="review-project" key={i}><h4>{project.title || 'New project'}</h4>
                    {(['title','description','technologies'] as const).map(key=>{
                        const label={title:'Project name',description:'Your contribution and results',technologies:'Tools used'}[key];
                        const different=before?.[key]!==project[key];
                        return <div className="review-field" key={key}><strong>{label}</strong>
                            {editing ? <label><span className="review-empty">Suggested wording</span><textarea aria-label={label+' for project '+(i+1)} rows={key==='description'?5:2} value={project[key]} disabled={busy} onChange={e=>projectField(i,key,e.target.value)}/></label> :
                            <><div className="review-before"><small>Current</small><TextValue value={before?.[key]}/></div><div className="review-after"><small>{different?'Suggested change':'Unchanged'}</small><TextValue value={project[key]} changed={different}/></div></>}
                        </div>;
                    })}
                </article>;
            })}
            {!editing && projects!.every((p,i)=>JSON.stringify(p)===JSON.stringify(profile.projects[i])) && <p>Project details are unchanged.</p>}
            {profile.projects.length>projects!.length && <p role="alert">{profile.projects.length-projects!.length} project(s) will be removed if you accept.</p>}
        </div> : <div className="review-field" key={field}><h4>{labels[field] || field}</h4>
            {editing ? <label>{Array.isArray(value)?'One item per line':'Suggested wording'}<textarea rows={3} disabled={busy} value={Array.isArray(value)?value.join('\n'):String(value || '')} onChange={e=>setPatch(previous=>({...previous,[field]:Array.isArray(value)?e.target.value.split('\n'):e.target.value}))}/></label> :
            <><div className="review-before"><small>Current</small><TextValue value={profile[field as keyof Profile]}/></div><div className="review-after"><small>Suggested</small><TextValue value={value} changed={JSON.stringify(value)!==JSON.stringify(profile[field as keyof Profile])}/></div></>}
        </div>)}
        {!!proposal.skill_options?.length && <div className="review-skills"><strong>Have you also used any of these?</strong><p>Select only skills you can confirm.</p>{proposal.skill_options.map(skill=><label key={skill}><input type="checkbox" checked={chosen.includes(skill)} disabled={busy} onChange={e=>setChosen(items=>e.target.checked?[...items,skill]:items.filter(x=>x!==skill))}/>{skill}</label>)}</div>}
        {invalid && <p role="alert">Each project needs a name and description. Choose Edit suggestion to complete them.</p>}
        {error && <p role="alert" className="live-error">{error}</p>}
        {chosen.length>0 && <p>Accept will also add {chosen.join(', ')} to your profile skills.</p>}
        {chosen.length>0 && <fieldset className="review-skill-destination" disabled={busy}><legend>Where did you use these skills?</legend>
            <label><input type="radio" name={'destination-'+proposal.id} checked={destination==='skills'} onChange={()=>setDestination('skills')}/>Add to skills only</label>
            <label><input type="radio" name={'destination-'+proposal.id} checked={destination==='project'} disabled={!availableProjects.length} onChange={()=>setDestination('project')}/>Add to skills and a project’s technologies</label>
            {destination==='project' && <><label>Choose the project<select value={target} onChange={e=>setTarget(e.target.value)}><option value="">Select a project</option>{availableProjects.map((p,i)=><option key={i} value={i}>{p.title || 'Project '+(i+1)}</option>)}</select></label><p>Selecting a project confirms you used {chosen.join(', ')} in that project. Existing tools are kept; duplicates are removed.</p></>}
        </fieldset>}
        <div className="overview-actions"><button className="button dark" disabled={busy || invalid || (chosen.length>0 && destination==='project' && target==='')} onClick={()=>{
            const clean={...patch};
            for(const key of ['skills','summary_facts'] as const) if(clean[key]) clean[key]=clean[key]!.map(s=>s.trim()).filter(Boolean);
            if(chosen.length) clean.skills=[...new Set([...(clean.skills || profile.skills),...chosen])];
            review('accept',clean,chosen.length>0 && destination==='project' ? {project_index:Number(target),skills:chosen} : undefined);
        }}>Accept & fill profile</button><button className="button subtle" disabled={busy} onClick={()=>setEditing(value=>!value)}>{editing?'Preview changes':'Edit suggestion'}</button><button className="text-button" disabled={busy} onClick={()=>review('dismiss')}>Dismiss suggestion</button></div>
        <small>You can edit this wording. Accepting it does not confirm the whole profile.</small>
    </section>;
}

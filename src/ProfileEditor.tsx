import { useEffect, useState } from 'react';
import type { Profile } from './api';
import { splitEducationEntries } from './education';
import './profile-editor.css';

type Props = { profile: Profile; busy: boolean; dirty: boolean; confirmed: boolean; canUndo: boolean; patch: (patch: Partial<Profile>) => void; undo: () => void; ask: (message: string) => void };
const groups = [
    { pattern: /\bai\b|artificial|machine learning|vision/i, skills: ['NumPy', 'Pandas', 'PyTorch', 'TensorFlow', 'scikit-learn', 'OpenCV', 'Jupyter', 'Model evaluation'] },
    { pattern: /comput|software|\bit\b|web|api/i, skills: ['Git', 'SQL', 'Testing', 'REST APIs', 'JavaScript', 'TypeScript', 'React', 'Linux'] },
    { pattern: /data|statistic|analyst/i, skills: ['SQL', 'Python', 'R', 'Power BI', 'Tableau', 'Statistics', 'Data visualisation'] },
    { pattern: /business|commerce|account|finance/i, skills: ['Excel', 'Financial modelling', 'Power BI', 'Business analysis', 'CRM'] },
    { pattern: /design|creative|ux/i, skills: ['Figma', 'Prototyping', 'User research', 'Accessibility', 'Design systems'] },
    { pattern: /marketing|media|communication/i, skills: ['SEO', 'Google Analytics', 'Copywriting', 'Content strategy', 'Canva'] },
    { pattern: /cyber|security/i, skills: ['Networking', 'Wireshark', 'Linux', 'SIEM', 'Threat modelling'] },
    { pattern: /cloud|devops/i, skills: ['Docker', 'AWS', 'Azure', 'CI/CD', 'Terraform', 'Kubernetes'] },
    { pattern: /robot|drone|electronic|engineer/i, skills: ['Python', 'C++', 'Sensors', 'CAD', 'Embedded systems'] },
    { pattern: /management/i, skills: ['Agile', 'Scrum', 'Jira', 'Project planning', 'Risk management'] },
];

function Entries({ kind, value, change }: { kind: 'education' | 'experience'; value: string; change: (v: string) => void }) {
    const labels = kind === 'education' ? ['Degree', 'University', 'Start date', 'End / expected date', 'Study status'] : ['Role', 'Company', 'Start date', 'End date', 'Responsibilities'];
    const entries = kind === 'education' ? splitEducationEntries(value) : value ? value.split('\n\n') : [];
    return <div>{entries.map((entry, i) => {
        const structured = entry.startsWith(labels[0] + ': ');
        const parts = Object.fromEntries(entry.split('\n').map(line => { const n = line.indexOf(': '); return [line.slice(0,n), line.slice(n+2)]; }));
        const replace = (v: string) => change(entries.map((e,k) => k === i ? v : e).join('\n\n'));
        return <div className="pe-entry" key={i}><strong>{kind === 'education' ? 'Education' : 'Experience'} {i+1}</strong>{structured ? <div className="pe-fields">{labels.map(label => <label key={label}>{label}{label === 'Study status' ? <select value={parts[label] || ''} onChange={e => replace(labels.map(l => l + ': ' + (l === label ? e.target.value : parts[l] || '')).join('\n'))}><option value="">Select status</option><option>Currently studying</option><option>Completed</option><option>Paused</option></select> : <input value={parts[label] || ''} onChange={e => replace(labels.map(l => l + ': ' + (l === label ? e.target.value : parts[l] || '')).join('\n'))}/>}</label>)}</div> : <label>Existing details<textarea rows={3} value={entry} onChange={e => replace(e.target.value)}/></label>}<button type="button" className="text-button" onClick={() => change(entries.filter((_,k) => k!==i).join('\n\n'))}>Remove entry</button></div>;
    })}<button type="button" className="button subtle" onClick={() => change([...entries.filter(e => e.toLowerCase() !== 'none'), labels.map(l => l + ': ').join('\n')].join('\n\n'))}>＋ Add {kind}</button>{kind === 'experience' && <button type="button" className="text-button" onClick={() => change('None')}>I have no work experience</button>}</div>;
}

export default function ProfileEditor({ profile: p, busy, dirty, confirmed, canUndo, patch, undo, ask }: Props) {
    const [highlight, setHighlight] = useState<string[]>([]);
    const [previous, setPrevious] = useState(p);
    useEffect(() => {
        const changed = Object.keys(p).filter(k => JSON.stringify(p[k as keyof Profile]) !== JSON.stringify(previous[k as keyof Profile]));
        setPrevious(p); setHighlight(changed);
        const sections = changed.map(k => document.getElementById('pe-' + (['name','email','phone','goal','location','linkedin','github','portfolio'].includes(k) ? 'personal' : k === 'summary_facts' ? 'achievements' : k))).filter(Boolean);
        sections.forEach(el => el!.classList.add('pe-flash'));
        const timer = setTimeout(() => { setHighlight([]); sections.forEach(el => el!.classList.remove('pe-flash')); }, 2200);
        return () => clearTimeout(timer);
    }, [p]);
    const context = [p.education, p.goal, ...p.projects.map(x => x.title + ' ' + x.description)].join(' ');
    const relevant = groups.filter(g => g.pattern.test(context));
    const suggestions = [...new Set(relevant.flatMap(g => g.skills))].filter(s => !p.skills.some(x => x.toLowerCase() === s.toLowerCase()));
    const completion = [
        {id:'personal', label:'Personal details', ok:!!p.name.trim() && /.+@.+\..+/.test(p.email) && p.phone.replace(/\D/g,'').length >= 6 && !!p.goal.trim()},
        {id:'education', label:'Education', ok:!!p.education.trim() && !/^Degree: \s*\n/.test(p.education)},
        {id:'skills', label:'Skills', ok:p.skills.some(s=>s.trim())},
        {id:'projects', label:'Projects', ok:p.projects.length>0 && p.projects.every(x=>x.title.trim() && x.description.trim())},
        {id:'experience', label:'Experience', ok:!!p.experience.trim() && !/^Role: \s*\n/.test(p.experience)},
        {id:'achievements', label:'Achievements', ok:!!p.achievements.trim()},
    ];
    const jump = (id: string) => { const el = document.getElementById('pe-'+id) as HTMLDetailsElement; if (el) {el.open=true;el.scrollIntoView({behavior:'smooth',block:'center'});} };
    const field = (key: keyof Profile, label: string) => <label className={highlight.includes(key) ? 'pe-flash' : ''}>{label}<input value={String(p[key] || '')} onChange={e=>patch({[key]:e.target.value})}/></label>;
    return <div className="profile-editor">
        <div className="pe-progress"><div><strong>{completion.filter(x=>x.ok).length} of 6 sections ready</strong><span role="status">{dirty ? 'Unsaved changes' : confirmed ? 'Saved · Confirmed' : 'Saved · Review and confirm'}</span></div><progress max={6} value={completion.filter(x=>x.ok).length}/><div className="pe-jumps">{completion.map(x=><button type="button" key={x.id} onClick={()=>jump(x.id)}>{x.ok ? '✓' : '○'} {x.label}</button>)}</div><button type="button" className="text-button" disabled={busy || dirty || !canUndo} onClick={undo}>↶ Undo last saved profile change</button></div>
        <fieldset disabled={busy}>
        <details id="pe-personal" open><summary>01 · Personal details</summary><div className="pe-fields">{field('name','Full name')}{field('email','Email')}{field('phone','Phone')}{field('goal','Target roles')}{field('location','Location (optional)')}{field('linkedin','LinkedIn (optional)')}{field('github','GitHub (optional)')}{field('portfolio','Portfolio (optional)')}</div><small>Leave optional fields blank to omit them from your CV.</small></details>
        <details id="pe-education" open><summary>02 · Education</summary><Entries kind="education" value={p.education} change={education=>patch({education})}/></details>
        <details id="pe-skills" open><summary>03 · Skills</summary><label>Skills you have used · one per line<textarea value={p.skills.join('\n')} onChange={e=>patch({skills:e.target.value.split('\n')})}/></label><div className="pe-suggestions"><strong>Explore related skills</strong><p>{relevant.length ? 'Based on your education, target role and projects.' : 'Add your education or target role for personalised suggestions.'} Choose only skills you have used.</p><div>{suggestions.map(s=><button type="button" key={s} onClick={()=>patch({skills:[...p.skills,s]})}>＋ {s}</button>)}</div>{relevant.length>0 && !suggestions.length && <p>All suggestions are already in your list. You can still add another skill above.</p>}</div></details>
        <details id="pe-projects" open><summary>04 · Projects & your contribution</summary>{p.projects.map((project,i)=><div className="pe-entry" key={i}>{(['title','description','technologies'] as const).map(key=><label key={key}>{key === 'description' ? 'Your contribution and results' : key}<textarea rows={key==='description'?3:1} value={project[key]} onChange={e=>patch({projects:p.projects.map((x,j)=>j===i?{...x,[key]:e.target.value}:x)})}/></label>)}<small>Describe what you personally built, which tools you used and what you tested or achieved.</small><div className="pe-actions"><button type="button" className="button subtle" disabled={dirty} onClick={()=>ask('Help me improve project '+(i+1)+': '+project.title+'. Could you ask me a few questions to help me describe my work better?')}>Interview me about this project</button><button type="button" className="text-button" onClick={()=>patch({projects:p.projects.filter((_,j)=>j!==i)})}>Remove project</button></div>{dirty && <small>Save your changes to start the project interview.</small>}</div>)}<button type="button" className="button subtle" onClick={()=>patch({projects:[...p.projects,{title:'',description:'',technologies:''}]})}>＋ Add project</button></details>
        <details id="pe-experience"><summary>05 · Experience</summary><Entries kind="experience" value={p.experience} change={experience=>patch({experience})}/></details>
        <details id="pe-achievements"><summary>06 · Achievements & summary facts</summary><label>Achievements<textarea value={p.achievements} onChange={e=>patch({achievements:e.target.value})}/></label><button type="button" className="text-button" onClick={()=>patch({achievements:'None'})}>No achievements to include</button><label>Additional confirmed facts · one per line<textarea value={p.summary_facts.join('\n')} onChange={e=>patch({summary_facts:e.target.value.split('\n')})}/></label></details>
        </fieldset>
    </div>;
}

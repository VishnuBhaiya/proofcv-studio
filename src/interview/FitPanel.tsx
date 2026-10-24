import { RequirementStatus } from './types';

type Evidence = { source: string; label: string; text: string; similarity: number };
type Requirement = { id: string; text: string; source: string; level: 'required' | 'preferred' | 'responsibility'; category: string; status: RequirementStatus; similarity: number; keywords_found: string[]; keywords_missing: string[]; evidence: Evidence[] };
export type Fit = { job: { document_id: string; title: string }; embedding_backend: string; evidence_count: number; counts: Record<RequirementStatus, number>; requirements: Requirement[]; review_status: string };
const GROUPS: { status: RequirementStatus; title: string; hint: string }[] = [
    { status: 'strong', title: 'Strengths to highlight', hint: 'Backed directly by your confirmed facts.' },
    { status: 'partial', title: 'Partly covered', hint: 'Related evidence exists. Be ready to explain the link.' },
    { status: 'gap', title: 'Gaps to prepare for', hint: 'No supporting fact found. Prepare an honest answer.' },
    { status: 'verify', title: 'Check yourself', hint: 'Degrees and years of experience are never judged automatically.' },
];

// Your fit tab: how the job's requirements line up with the confirmed profile.
export default function FitPanel({ fit }: { fit: Fit | null }) {
    if (!fit) return <p className="live-progress"><span className="live-dot" /> Comparing the job’s requirements with your confirmed facts…</p>;
    return <div className="ic-fit">
        <div className="ic-fit-counts">{GROUPS.map(g => <div key={g.status} className={`ic-fit-count ${g.status}`}><strong>{fit.counts[g.status]}</strong><span>{g.title}</span></div>)}</div>
        <div className="ic-fit-groups">{GROUPS.map(g => fit.counts[g.status] > 0 && <section className={`coach-group ${g.status}`} key={g.status}>
            <h4>{g.title}</h4><p className="coach-hint">{g.hint}</p>
            {fit.requirements.filter(r => r.status === g.status).map(r => <details className="coach-req" key={r.id}>
                <summary><span className={`coach-level ${r.level}`}>{r.level}</span>{r.text}</summary>
                <p className="coach-quote">Job ad: “{r.source}”</p>
                {r.keywords_found.length > 0 && <p className="coach-keywords">Found: {r.keywords_found.join(', ')}</p>}
                {r.evidence.length ? <ul>{r.evidence.map((e, i) => <li key={i}><strong>{e.label}</strong> · {e.text} <small>(similarity {e.similarity.toFixed(2)})</small></li>)}</ul> : <p className="coach-keywords">No supporting fact in your confirmed profile.</p>}
            </details>)}
        </section>)}</div>
        <p className="coach-method">Matched locally against your {fit.evidence_count} confirmed facts with exact keywords and MiniLM similarity.{fit.review_status.startsWith('draft') ? ' The requirement map is a draft awaiting review.' : ''}</p>
    </div>;
}

import { useEffect, useState } from 'react';
import { Check, Mic, Presentation, Target, UserRound } from 'lucide-react';
import { api, Workspace } from '../api';
import './interview.css';

type Readiness = { workspace_id: string; profile_confirmed: boolean; matched_jobs: { document_id: string; title: string; score: number }[]; target_job: { document_id: string; title: string } | null; rounds: string[] };

const ROUND_INFO: Record<string, { title: string; detail: string }> = {
    self_introduction: { title: 'Self-introduction', detail: '30-second, 90-second and 2-minute versions, with a short slide deck to rehearse.' },
    behavioural: { title: 'Behavioural', detail: 'STAR answers on teamwork, conflict and failure, checked against your confirmed facts.' },
    technical: { title: 'Technical', detail: 'Questions drawn from the target job’s own requirements.' },
    motivation_fit: { title: 'Motivation & fit', detail: 'Why this role, and how to answer honestly about requirements you don’t meet yet.' },
};

export default function InterviewCoach({ workspace, go }: { workspace: Workspace; go: (page: 'profile' | 'jobs') => void }) {
    const [status, setStatus] = useState<Readiness | null>(null);
    const [error, setError] = useState('');
    useEffect(() => {
        setError('');
        api<Readiness>(`/interview/${workspace.id}/status`).then(setStatus).catch(e => setError(e.message));
    }, [workspace.id, workspace.revision, workspace.confirmed_revision, workspace.retrieval, workspace.draft?.job.document_id]);
    if (error) return <div className="page-content"><p className="live-error" role="alert">{error}</p></div>;
    if (!status) return <div className="page-content"><p className="live-progress"><span className="live-dot" /> Loading Interview Coach…</p></div>;
    const ready = status.profile_confirmed && !!status.target_job;
    return <div className="page-content interview-coach">
        <div className="page-heading"><div><h2>Prepare for the interview.</h2><p>Practise out loud for the job you chose, using only facts from your confirmed profile.</p></div></div>
        <section className="coach-readiness" aria-label="Interview Coach readiness">
            <div className={status.profile_confirmed ? 'done' : ''}><UserRound size={18} /><div><strong>Confirmed profile</strong><span>{status.profile_confirmed ? 'Ready' : 'Confirm your profile first'}</span></div>{status.profile_confirmed ? <Check size={16} /> : <button className="text-button" onClick={() => go('profile')}>Open profile</button>}</div>
            <div className={status.target_job ? 'done' : ''}><Target size={18} /><div><strong>Target job</strong><span>{status.target_job ? status.target_job.title : status.matched_jobs.length ? 'Choose one of your top matches' : 'Find your job matches first'}</span></div>{status.target_job ? <Check size={16} /> : <button className="text-button" onClick={() => go('jobs')}>Discover jobs</button>}</div>
        </section>
        {status.matched_jobs.length > 0 && <p className="coach-matches">Your top matches: {status.matched_jobs.map(j => j.title).join(' · ')}</p>}
        <div className="section-heading"><h2>Interview rounds</h2><span>{ready ? 'Coming next' : 'Unlocks when both steps above are done'}</span></div>
        <div className="coach-rounds">{status.rounds.map(id => <article className="coach-round" key={id}>{id === 'self_introduction' ? <Presentation size={20} /> : <Mic size={20} />}<h3>{ROUND_INFO[id]?.title ?? id}</h3><p>{ROUND_INFO[id]?.detail}</p><span className="coach-badge">Not built yet</span></article>)}</div>
    </div>;
}

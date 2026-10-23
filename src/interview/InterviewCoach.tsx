import { useEffect, useState } from 'react';
import { Check, Mic, Presentation, Target, UserRound } from 'lucide-react';
import { api, Workspace } from '../api';
import AnswerRecorder from './AnswerRecorder';
import './interview.css';

type Evidence = { source: string; label: string; text: string; similarity: number };
type Requirement = { id: string; text: string; source: string; level: 'required' | 'preferred' | 'responsibility'; category: string; status: 'strong' | 'partial' | 'gap' | 'verify'; similarity: number; keywords_found: string[]; keywords_missing: string[]; evidence: Evidence[] };
type Fit = { job: { document_id: string; title: string }; embedding_backend: string; evidence_count: number; counts: Record<Requirement['status'], number>; requirements: Requirement[]; review_status: string };
const GROUPS: { status: Requirement['status']; title: string; hint: string }[] = [
    { status: 'strong', title: 'Strengths to highlight', hint: 'Backed directly by your confirmed facts.' },
    { status: 'partial', title: 'Partly covered', hint: 'Related evidence exists. Be ready to explain the link.' },
    { status: 'gap', title: 'Gaps to prepare for', hint: 'No supporting fact found. Prepare an honest answer.' },
    { status: 'verify', title: 'Check yourself', hint: 'Degrees and years of experience are never judged automatically.' },
];
type Question = { id: string; round: string; text: string; reason: string; seconds?: number; requirement?: { id: string; text: string; status: Requirement['status'] } };
type Questions = { job: { document_id: string; title: string }; review_status: string; rounds: Record<string, Question[]> };
type Readiness = {workspace_id: string; profile_confirmed: boolean; matched_jobs: { document_id: string; title: string; score: number }[]; target_job: { document_id: string; title: string } | null; rounds: string[] };

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
    const [jobId, setJobId] = useState('');
    const [fit, setFit] = useState<Fit | null>(null);
    const [fitError, setFitError] = useState('');
    const [questions, setQuestions] = useState<Questions | null>(null);
    const [practising, setPractising] = useState('');
    useEffect(() => {
        setFit(null);
        setQuestions(null);
        setFitError('');
        if (!status?.profile_confirmed || !status.target_job) return;
        const query = jobId ? `?job=${encodeURIComponent(jobId)}` : '';
        api<Fit>(`/interview/${workspace.id}/fit${query}`).then(setFit).catch(e => setFitError(e.message));
        api<Questions>(`/interview/${workspace.id}/questions${query}`).then(setQuestions).catch(e => setFitError(e.message));
    }, [status, jobId, workspace.id]);
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
        {ready && <section className="coach-fit" aria-label="Strengths and gaps">
            <div className="section-heading"><h2>Your fit for this job</h2>
                <label className="coach-job-select">Prepare for<select value={jobId || status.target_job!.document_id} onChange={e => setJobId(e.target.value)}>{[status.target_job!, ...status.matched_jobs.filter(j => j.document_id !== status.target_job!.document_id)].map(j => <option key={j.document_id} value={j.document_id}>{j.title}</option>)}</select></label></div>
            {fitError && <p className="live-error" role="alert">{fitError}</p>}
            {!fit && !fitError && <p className="live-progress"><span className="live-dot" /> Comparing the job’s requirements with your confirmed facts…</p>}
            {fit && <>
                <p className="coach-method">Each requirement is matched locally against your {fit.evidence_count} confirmed facts using exact keywords and MiniLM similarity. No Gemini call is made.{fit.review_status.startsWith('draft') && <> <strong>Requirement map is a draft awaiting review.</strong></>}</p>
                <div className="coach-counts">{GROUPS.map(g => <span key={g.status} className={`coach-count ${g.status}`}><strong>{fit.counts[g.status]}</strong>{g.title}</span>)}</div>
                {GROUPS.map(g => fit.counts[g.status] > 0 && <div className={`coach-group ${g.status}`} key={g.status}><h3>{g.title}</h3><p className="coach-hint">{g.hint}</p>
                    {fit.requirements.filter(r => r.status === g.status).map(r => <details className="coach-req" key={r.id}>
                        <summary><span className={`coach-level ${r.level}`}>{r.level}</span>{r.text}</summary>
                        <p className="coach-quote">Job ad: “{r.source}”</p>
                        {r.keywords_found.length > 0 && <p className="coach-keywords">Found: {r.keywords_found.join(', ')}</p>}
                        {r.evidence.length ? <ul>{r.evidence.map((e, i) => <li key={i}><strong>{e.label}</strong> · {e.text} <small>(similarity {e.similarity.toFixed(2)})</small></li>)}</ul> : <p className="coach-keywords">No supporting fact in your confirmed profile.</p>}
                    </details>)}
                </div>)}
            </>}
        </section>}
        <div className="section-heading"><h2>Interview rounds</h2><span>{!ready ? 'Unlocks when both steps above are done' : questions ? `${Object.values(questions.rounds).flat().length} questions picked for ${questions.job.title}` : 'Picking questions…'}</span></div>
        {questions?.review_status.startsWith('draft') && <p className="coach-method">Questions are picked locally from a question bank that is still a draft awaiting review. Spoken practice gives delivery feedback and a fact check for every answer, a STAR check for behavioural answers and key-point coverage for technical answers.</p>}
        <div className="coach-rounds">{status.rounds.map(id => <article className="coach-round" key={id}>{id === 'self_introduction' ? <Presentation size={20} /> : <Mic size={20} />}<h3>{ROUND_INFO[id]?.title ?? id}</h3><p>{ROUND_INFO[id]?.detail}</p>
            {questions ? <ol className="coach-questions">{(questions.rounds[id] || []).map((q, i) => { const key = `${q.id}-${i}`; return <li key={key}>{q.text}<small className={q.requirement ? `coach-why ${q.requirement.status}` : 'coach-why'}>{q.reason}</small>
                {practising === key ? <AnswerRecorder workspaceId={workspace.id} questionId={q.id} questionText={q.text} /> : <button type="button" className="text-button coach-practise" onClick={() => setPractising(key)}><Mic size={14} />Practise</button>}</li>; })}</ol> : <span className="coach-badge">{ready ? 'Loading…' : 'Locked'}</span>}
        </article>)}</div>
    </div>;
}

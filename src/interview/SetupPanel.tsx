import { useEffect, useState } from 'react';
import { ArrowRight, BookOpen, Briefcase, CalendarDays, Check, ListChecks, Star } from 'lucide-react';
import { api } from '../api';
import { Fit } from './FitPanel';

export type JobOption = { document_id: string; title: string; location: string | null; focus: string | null; match_score: number | null; cv_target: boolean };
export type Setup = { job: string; interview_date: string; learn_skills: string[]; stage: string; daily_minutes: number; notes: string; saved_at?: string };
export type Status = { profile_confirmed: boolean; target_job: { document_id: string; title: string } | null; jobs: JobOption[]; setup: Setup | null };
type Learnable = { id: string; text: string; level: string; status: 'gap' | 'partial' };

// Matches setup.STAGES, setup.DAILY_MINUTES and plan.MAX_DAYS on the server.
const STAGES: [string, string][] = [['screening', 'Phone or video screening'], ['technical', 'Technical interview'], ['panel', 'Panel interview'], ['final', 'Final interview']];
const DAILY: [number, string][] = [[30, '30 min'], [60, '1 hour'], [120, '2 hours'], [180, '3 hours or more']];
const MAX_DAYS = 60;
const SHOWN_SKILLS = 8;
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export const jobLabel = (j: JobOption) => `${j.title}${j.focus ? ` · ${j.focus}` : ''}`;
const daysUntil = (value: string) => Math.round((new Date(`${value}T00:00`).getTime() - new Date(new Date().toDateString()).getTime()) / 86_400_000);

// First screen of Interview Coach: which job, when, what to learn, and a few details for the plan.
export default function SetupPanel({ workspaceId, status, onSaved, onCancel }: {
    workspaceId: string; status: Status; onSaved: (status: Status) => void; onCancel?: () => void }) {
    const saved = status.setup;
    const [job, setJob] = useState(saved?.job || status.target_job?.document_id || status.jobs[0]?.document_id || '');
    const [date, setDate] = useState(saved?.interview_date || '');
    const [fit, setFit] = useState<(Fit & { to_learn: Learnable[] }) | null>(null);
    const [learn, setLearn] = useState<boolean | null>(saved ? saved.learn_skills.length > 0 : null);
    const [skills, setSkills] = useState<string[]>(saved?.learn_skills || []);
    const [stage, setStage] = useState(saved?.stage || '');
    const [daily, setDaily] = useState<number | null>(saved?.daily_minutes ?? null);
    const [notes, setNotes] = useState(saved?.notes || '');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    useEffect(() => {
        setFit(null);
        api<Fit & { to_learn: Learnable[] }>(`/interview/${workspaceId}/fit?job=${encodeURIComponent(job)}`).then(result => {
            setFit(result);
            // Keep earlier picks that still apply to this job; otherwise suggest every required skill that is missing.
            setSkills(current => {
                const kept = current.filter(id => result.to_learn.some(s => s.id === id));
                return kept.length ? kept : result.to_learn.filter(s => s.level === 'required' && s.status === 'gap').map(s => s.id);
            });
        }).catch(e => setError(e.message));
    }, [workspaceId, job]);

    const today = new Date();
    const last = new Date(today.getFullYear(), today.getMonth(), today.getDate() + MAX_DAYS);
    const chosen = status.jobs.find(j => j.document_id === job);
    // The CV's job first, then the user's top matches, then every other job.
    const orderedJobs = [...status.jobs].sort((a, b) => Number(b.cv_target) - Number(a.cv_target) || Number(b.match_score != null) - Number(a.match_score != null));
    const learnable = fit?.to_learn.slice(0, SHOWN_SKILLS) || [];
    const ready = job && date && stage && daily && (learn !== null || (fit && !fit.to_learn.length));
    async function start() {
        setBusy(true);
        setError('');
        try {
            onSaved(await api<Status>(`/interview/${workspaceId}/setup`, { job, interview_date: date, learn_skills: learn ? skills : [], stage, daily_minutes: daily, notes }));
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Could not save your setup.');
        } finally {
            setBusy(false);
        }
    }
    const toggle = (id: string) => setSkills(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);

    return <div className="ic-setup-flow">
        <header className="ic-setup-head">
            <span className="ic-eyebrow-dark">Interview Coach</span>
            <h2>{saved ? 'Change your interview setup' : 'Let’s set up your interview preparation'}</h2>
            <p>Tell the coach which job you are preparing for and when. It uses your confirmed CV and this job to build your questions and your plan.</p>
        </header>

        <section className="ic-setup-card">
            <h3><span>1</span><Briefcase size={18} />Which job are you preparing for?</h3>
            <p>You can pick any job in the list, not only the one your CV is tailored to.</p>
            <div className="ic-job-cards" role="radiogroup" aria-label="Job to prepare for">{orderedJobs.map(j =>
                <button type="button" role="radio" key={j.document_id} aria-checked={job === j.document_id} onClick={() => setJob(j.document_id)}
                    className={`ic-job-card ${j.cv_target ? 'cv' : ''} ${job === j.document_id ? 'on' : ''}`}>
                    {j.cv_target && <span className="ic-job-badge"><Star size={12} />Your CV is tailored to this job</span>}
                    {!j.cv_target && j.match_score != null && <span className="ic-job-badge match">One of your top matches</span>}
                    <strong>{j.title}</strong>
                    <small>{[j.focus, j.location].filter(Boolean).join(' · ')}</small>
                    {job === j.document_id && <Check size={18} className="ic-job-check" />}
                </button>)}</div>
            {chosen && <div className="ic-setup-fit">
                {fit ? <span>For <strong>{jobLabel(chosen)}</strong>, your profile shows <strong>{fit.counts.strong}</strong> of its requirements clearly, <strong>{fit.counts.partial}</strong> partly and <strong>{fit.counts.gap}</strong> not yet.</span>
                    : <span className="live-progress"><span className="live-dot" /> Comparing this job with your profile…</span>}
            </div>}
        </section>

        <section className="ic-setup-card">
            <h3><span>2</span><CalendarDays size={18} />When is your interview?</h3>
            <div className="ic-setup-row">
                <input type="date" value={date} min={iso(today)} max={iso(last)} onChange={e => setDate(e.target.value)} aria-label="Interview date" />
                {date && <span className="ic-chip">{daysUntil(date) === 0 ? 'Today' : daysUntil(date) === 1 ? 'Tomorrow' : `In ${daysUntil(date)} days`}</span>}
            </div>
        </section>

        <section className="ic-setup-card">
            <h3><span>3</span><BookOpen size={18} />Skills this job needs that your CV does not show</h3>
            {!fit ? <p className="live-progress"><span className="live-dot" /> Looking for gaps…</p> : !fit.to_learn.length ? <p>Your CV already shows every technical skill this job lists.</p> : <>
                <ul className="ic-learn-list">{learnable.map(s => <li key={s.id}>
                    <span>{s.text}</span>
                    <small className={`ic-chip ${s.level === 'required' ? 'warn' : ''}`}>{s.level === 'required' ? 'Required' : s.level === 'preferred' ? 'Preferred' : 'Part of the job'} · {s.status === 'gap' ? 'not in your CV' : 'only partly in your CV'}</small>
                </li>)}</ul>
                {fit.to_learn.length > SHOWN_SKILLS && <p className="coach-method">Showing the {SHOWN_SKILLS} most important of {fit.to_learn.length}.</p>}
                <p className="ic-setup-question">Do you also want to learn some of these before the interview?</p>
                <div className="ic-choice" role="radiogroup" aria-label="Learn missing skills">
                    <button type="button" role="radio" aria-checked={learn === true} className={learn === true ? 'on' : ''} onClick={() => setLearn(true)}>Yes, add them to my plan</button>
                    <button type="button" role="radio" aria-checked={learn === false} className={learn === false ? 'on' : ''} onClick={() => setLearn(false)}>No, focus on what I already know</button>
                </div>
                {learn && <fieldset className="ic-learn-pick"><legend>Which ones?</legend>{learnable.map(s => <label key={s.id}>
                    <input type="checkbox" checked={skills.includes(s.id)} onChange={() => toggle(s.id)} />{s.text}</label>)}</fieldset>}
            </>}
        </section>

        <section className="ic-setup-card">
            <h3><span>4</span><ListChecks size={18} />A few details for your plan</h3>
            <p className="ic-setup-question">What kind of interview is it?</p>
            <div className="ic-choice" role="radiogroup" aria-label="Interview stage">{STAGES.map(([id, label]) =>
                <button type="button" role="radio" key={id} aria-checked={stage === id} className={stage === id ? 'on' : ''} onClick={() => setStage(id)}>{label}</button>)}</div>
            <p className="ic-setup-question">How much time can you practise each day?</p>
            <div className="ic-choice" role="radiogroup" aria-label="Daily practice time">{DAILY.map(([minutes, label]) =>
                <button type="button" role="radio" key={minutes} aria-checked={daily === minutes} className={daily === minutes ? 'on' : ''} onClick={() => setDaily(minutes)}>{label}</button>)}</div>
            <label className="ic-setup-notes">Anything else the coach should know? <small>(optional)</small>
                <textarea rows={3} maxLength={500} value={notes} onChange={e => setNotes(e.target.value)} placeholder="For example: the company name, who is interviewing you, or a topic they said they will ask about." />
            </label>
        </section>

        {error && <p className="live-error" role="alert">{error}</p>}
        <div className="ic-setup-start">
            <p>{ready ? 'Next: the coach starts your preparation for this job.' : 'Choose a job, a date, the interview type and your daily time to continue.'}</p>
            <div>
                {onCancel && <button type="button" className="button subtle" onClick={onCancel}>Cancel</button>}
                <button type="button" className="button dark ic-start" disabled={!ready || busy} onClick={() => void start()}>{busy ? 'Saving…' : saved ? 'Save and continue' : 'Start preparing'}<ArrowRight size={17} /></button>
            </div>
        </div>
    </div>;
}

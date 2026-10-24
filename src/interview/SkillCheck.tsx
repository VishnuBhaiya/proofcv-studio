import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, ClipboardCheck, RotateCcw } from 'lucide-react';
import { api } from '../api';
import AnswerRecorder from './AnswerRecorder';
import { Bubble, ScoreRing } from './ui';

type CheckQuestion = { id: string; text: string; topic: string; compulsory: boolean; learning: boolean; requirement: { id: string; text: string; level: string; status: string } };
type Topic = { position: number; topic: string; question: string; requirement: CheckQuestion['requirement']; compulsory: boolean; answered: boolean;
    level: 'strong' | 'developing' | 'weak' | 'not_assessed'; knowledge?: number; score?: number; covered?: string[]; partial?: string[]; missed?: string[] };
type Evaluation = { answered: number; total: number; compulsory_done: number; knowledge: number | null; score: number | null; finished: boolean;
    strong: Topic[]; developing: Topic[]; weak: Topic[]; not_assessed: Topic[]; communication: { delivery: number | null; flags: number }; learn_skills: string[]; method: string };
export type Check = { id: string; job: { document_id: string; title: string }; questions: CheckQuestion[]; answers: Record<string, unknown>;
    finished_at: string | null; compulsory: number; evaluation: Evaluation };

const cap = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
const TECHNICAL_SECONDS = 75; // Matches ROUND_TARGET_SECONDS['technical'] on the server.
const GROUPS: [('weak' | 'developing' | 'strong'), string, string][] = [
    ['weak', 'Weak: study these first', 'Under 40% of the key points covered.'],
    ['developing', 'Developing: strengthen these', '40–69% of the key points covered.'],
    ['strong', 'Strong: keep these fresh', '70% or more of the key points covered.'],
];

function Results({ check, retake, onDone, busy }: { check: Check; retake: () => void; onDone: () => void; busy: boolean }) {
    const e = check.evaluation;
    return <div className="ic-check">
        <section className="ic-check-head">
            <ScoreRing value={e.knowledge} size={104} label="key points covered" />
            <div>
                <span className="ic-eyebrow-dark">Skill check results · {check.job.title}</span>
                <h2>{e.weak.length ? `${e.weak.length} weak topic${e.weak.length === 1 ? '' : 's'} to work on` : e.developing.length ? 'No weak topics, a few to strengthen' : 'Strong across every topic you answered'}</h2>
                <p>You answered {e.answered} of {e.total} questions: {e.strong.length} strong, {e.developing.length} developing, {e.weak.length} weak.
                    {e.communication.delivery != null && ` Delivery averaged ${e.communication.delivery}/100.`}
                    {e.communication.flags > 0 && ` ${e.communication.flags} detail${e.communication.flags === 1 ? ' was' : 's were'} not backed by your profile.`}</p>
            </div>
        </section>
        {GROUPS.map(([level, title, hint]) => e[level].length > 0 && <section key={level} className={`ic-check-group ${level}`}>
            <h3>{title}</h3><p className="coach-method">{hint}</p>
            <ul>{e[level].map(t => <li key={t.position}>
                <div className="ic-check-topic"><strong>{cap(t.topic)}</strong><span className="ic-pill small" style={{ ['--tone' as string]: `var(--ic-${level === 'strong' ? 'good' : level === 'developing' ? 'fair' : 'poor'})` }}>{t.knowledge}%</span></div>
                <small>{t.question} · tests “{t.requirement.text}”</small>
                {level !== 'strong' && (t.missed!.length + t.partial!.length > 0) && <div className="ic-study">
                    <span>Study:</span><ul>{t.missed!.map(k => <li key={k}>{k}</li>)}{t.partial!.map(k => <li key={k} className="partial">{k} <em>(you touched on this)</em></li>)}</ul>
                </div>}
            </li>)}</ul>
        </section>)}
        {e.learn_skills.length > 0 && <section className="ic-check-group learn"><h3>Skills you chose to learn</h3>
            <ul>{e.learn_skills.map(s => <li key={s}><strong>{s}</strong></li>)}</ul></section>}
        {e.not_assessed.length > 0 && <p className="coach-method">Not assessed (skipped): {e.not_assessed.map(t => cap(t.topic)).join('; ')}.</p>}
        <p className="coach-method">{e.method} Everything was analysed on this computer.</p>
        <div className="ic-setup-start">
            <p>Your plan will use these results: weak topics first, then developing ones.</p>
            <div>
                <button type="button" className="button subtle" disabled={busy} onClick={retake}><RotateCcw size={15} />Retake skill check</button>
                <button type="button" className="button dark ic-start" onClick={onDone}>Continue<ArrowRight size={17} /></button>
            </div>
        </div>
    </div>;
}

// The ten-question technical skill check after setup: four compulsory questions, then results by topic.
export default function SkillCheck({ workspaceId, jobId, jobTitle, onDone, onChange }: {
    workspaceId: string; jobId: string; jobTitle: string; onDone: () => void; onChange?: (check: Check | null) => void }) {
    const [check, setCheck] = useState<Check | null | undefined>(undefined);
    const [index, setIndex] = useState(0);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const update = (next: Check | null) => { setCheck(next); onChange?.(next); };
    const load = () => api<{ session: Check | null }>(`/interview/${workspaceId}/skill-check?job=${encodeURIComponent(jobId)}`).then(r => update(r.session)).catch(e => setError(e.message));
    useEffect(() => { void load(); }, [workspaceId, jobId]);
    useEffect(() => { // Resume at the first unanswered question.
        if (check && !check.finished_at) setIndex(i => i || Math.max(0, check.questions.findIndex((_, p) => !(String(p) in check.answers))));
    }, [check?.id]);
    async function post(path: string, body: Record<string, unknown>) {
        setBusy(true);
        setError('');
        try { const next = await api<Check>(`/interview/${workspaceId}/${path}`, body); update(next); setIndex(0); }
        catch (e) { setError(e instanceof Error ? e.message : 'Something went wrong.'); }
        finally { setBusy(false); }
    }
    const begin = (restart = false) => post('skill-check', { job: jobId, restart });

    if (error && check === undefined) return <p className="live-error" role="alert">{error}</p>;
    if (check === undefined) return <p className="live-progress"><span className="live-dot" /> Loading your skill check…</p>;
    if (check?.finished_at) return <Results check={check} retake={() => void begin(true)} onDone={onDone} busy={busy} />;
    if (!check) return <section className="ic-check-intro">
        <ClipboardCheck size={30} />
        <span className="ic-eyebrow-dark">Step 2 · Skill check</span>
        <h2>10 technical questions for {jobTitle}</h2>
        <p>Answer out loud, as you would in the interview. The <strong>first 4 are compulsory</strong>: they cover the job’s most important skills, and the coach needs them to see where you stand. The other 6 are optional, but each one you answer makes your plan more precise.</p>
        <p>There is no feedback between questions. At the end you get your strong, developing and weak topics, with exactly what to study. It is all analysed on this computer, without Gemini.</p>
        {error && <p className="live-error" role="alert">{error}</p>}
        <button type="button" className="button dark ic-check-begin" disabled={busy} onClick={() => void begin()}>{busy ? 'Choosing questions…' : 'Begin skill check'}<ArrowRight size={17} /></button>
    </section>;

    const question = check.questions[index];
    const answered = (p: number) => String(p) in check.answers;
    const done = check.evaluation.compulsory_done;
    const firstOpenCompulsory = check.questions.findIndex((q, p) => q.compulsory && !answered(p));
    const reachable = (p: number) => firstOpenCompulsory < 0 || p <= firstOpenCompulsory;
    const blocked = question.compulsory && !answered(index);
    return <div className="ic-check">
        <div className="ic-check-progress" aria-label="Questions">{check.questions.map((q, p) =>
            <button type="button" key={p} disabled={!reachable(p)} aria-current={p === index ? 'step' : undefined} onClick={() => setIndex(p)}
                className={`${answered(p) ? 'done' : ''} ${q.compulsory ? 'must' : ''} ${p === index ? 'current' : ''}`} title={`${q.compulsory ? 'Compulsory' : 'Optional'}: ${q.topic}`}>{p + 1}</button>)}
            <span>{done} of {check.compulsory} compulsory · {check.evaluation.answered} of {check.questions.length} answered</span>
        </div>
        <div className="ic-stage-bar">
            <span>Question {index + 1} of {check.questions.length} · {question.compulsory ? 'compulsory' : 'optional'} · aim for about {TECHNICAL_SECONDS} seconds</span>
        </div>
        <div className="ic-thread">
            <Bubble who="interviewer" meta={<>Topic: {question.topic} · tests “{question.requirement.text}”{question.learning ? ' · a skill you chose to learn' : ''}</>}>
                <span className="ic-question">{question.text}</span>
            </Bubble>
            <AnswerRecorder key={`${check.id}-${index}`} workspaceId={workspaceId} questionId={question.id} questionText={question.text} jobId={jobId}
                requirementId={question.requirement.id} extra={{ diagnostic: check.id, diagnostic_position: index }} hideFeedback onResult={() => void load()} targetSeconds={TECHNICAL_SECONDS} />
        </div>
        {error && <p className="live-error" role="alert">{error}</p>}
        <div className="ic-stage-nav">
            <button type="button" className="button subtle" disabled={index === 0} onClick={() => setIndex(index - 1)}><ArrowLeft size={15} />Previous</button>
            {index < check.questions.length - 1 && <button type="button" className="button subtle" disabled={blocked} onClick={() => setIndex(index + 1)}>
                {blocked ? 'Answer this compulsory question first' : answered(index) ? 'Next question' : 'Skip this question'}<ArrowRight size={15} /></button>}
            <button type="button" className="button dark" disabled={done < check.compulsory || busy} onClick={() => void post(`skill-check/${check.id}/finish`, {})}>
                {done < check.compulsory ? `Answer the ${check.compulsory} compulsory questions first (${done} of ${check.compulsory})` : 'Finish and see my results'}</button>
        </div>
    </div>;
}


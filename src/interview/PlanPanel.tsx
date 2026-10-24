import { useState } from 'react';
import { BookOpen, Check, Circle, ClipboardList, FileText, Flag, Mic, Sparkles, Target } from 'lucide-react';
import { api } from '../api';
import AnswerRecorder from './AnswerRecorder';

type Level = 'strong' | 'developing' | 'weak' | 'not_assessed' | 'to_learn';
type Point = { text: string; covered: boolean };
type Task = { kind: 'study' | 'test' | 'mock' | 'focus' | 'cheatsheet' | 'warmup'; key: string; text: string; done: boolean; topic_id?: string; topic?: string;
    question_id?: string | null; question?: string | null; key_points?: Point[]; level?: Level; before?: number | null; after?: number | null };
type Day = { date: string; label: string; kind: 'study' | 'test' | 'mock' | 'focus' | 'interview'; title: string; note: string; tasks: Task[]; done: number; total: number;
    tip?: string; mock_next_steps?: string[] };
type TopicRow = { id: string; topic: string; requirement: { text: string }; learning: boolean; start: Level; start_knowledge: number | null; level: Level; knowledge: number | null };
export type Plan = { job: { document_id: string; title?: string }; status: 'active' | 'interview_today' | 'passed' | 'needs_setup' | 'needs_check'; interview_date: string | null;
    today?: string; days_left?: number; per_day?: number; topics?: TopicRow[]; days?: Day[] };

const LEVEL: Record<Level, [string, string]> = {
    strong: ['Strong', 'good'], developing: ['Developing', 'fair'], weak: ['Weak', 'poor'], not_assessed: ['Not assessed', 'none'], to_learn: ['To learn', 'none'],
};
const KIND_ICON = { study: BookOpen, test: ClipboardList, mock: Flag, focus: Target, interview: Sparkles };
const TECHNICAL_SECONDS = 75; // Matches ROUND_TARGET_SECONDS['technical'] on the server.
const cap = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
export const longDate = (value: string) => new Date(`${value}T00:00`).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
export const countdown = (plan: Plan) => plan.status === 'interview_today' ? 'Interview today' : plan.days_left === 1 ? 'Interview tomorrow' : `Interview in ${plan.days_left} days`;

function LevelChip({ level, value }: { level: Level; value?: number | null }) {
    const [label, tone] = LEVEL[level];
    return <span className={`ic-level tone-${tone}`}>{label}{value != null ? ` · ${value}%` : ''}</span>;
}

// Plan tab: the adaptive day-by-day plan from the skill check to the interview.
export default function PlanPanel({ workspaceId, plan, setPlan, onAnswered, practise, startMock, openReports }: {
    workspaceId: string; plan: Plan | null; setPlan: (plan: Plan) => void; onAnswered: () => void; practise: (questionId: string) => void;
    startMock: () => void; openReports: () => void }) {
    const [open, setOpen] = useState<string | null>(null); // The task whose question is open for an answer.
    const [error, setError] = useState('');
    if (!plan || !plan.days) return <p className="live-progress"><span className="live-dot" /> Loading your plan…</p>;
    if (plan.status === 'passed') return <section className="ic-plan-setup"><h3>Your interview date has passed</h3><p>Use Edit setup to choose a new date, and the plan will start again from your latest results.</p></section>;
    async function tick(day: Day, task: Task) {
        setError('');
        try { setPlan(await api<Plan>(`/interview/${workspaceId}/plan/tick`, { date: day.date, key: task.key, done: !task.done })); }
        catch (e) { setError(e instanceof Error ? e.message : 'Could not save that.'); }
    }
    const today = plan.days.find(d => d.date === plan.today) || plan.days.find(d => d.date > plan.today!) || plan.days[plan.days.length - 1];
    const later = plan.days.filter(d => d.date > today.date);
    const earlier = plan.days.filter(d => d.date < today.date);
    const topics = plan.topics || [];
    const count = (level: Level, key: 'start' | 'level') => topics.filter(t => t[key] === level).length;
    const recorder = (task: Task) => open === task.key && task.question_id && <div className="ic-plan-answer">
        <AnswerRecorder workspaceId={workspaceId} questionId={task.question_id} questionText={task.question || task.text} jobId={plan.job.document_id}
            onResult={onAnswered} targetSeconds={TECHNICAL_SECONDS} />
    </div>;
    const KindIcon = KIND_ICON[today.kind];

    return <div className="ic-plan">
        <section className="ic-plan-head">
            <div>
                <span className="ic-eyebrow-dark">{plan.job.title}</span>
                <h3>{countdown(plan)}</h3>
                <p>{longDate(plan.interview_date!)} · {plan.per_day} topic{plan.per_day === 1 ? '' : 's'} per study day</p>
            </div>
            <div className="ic-plan-shift">
                <span><strong>{count('weak', 'start')}</strong> weak at the skill check</span>
                <span><strong>{count('weak', 'level')}</strong> weak now</span>
                <span><strong>{count('strong', 'level')}</strong> strong now</span>
            </div>
        </section>
        {error && <p className="live-error" role="alert">{error}</p>}

        <section className={`ic-plan-today kind-${today.kind}`}>
            <div className="ic-plan-day-head">
                <KindIcon size={22} />
                <div><span className="ic-eyebrow-dark">{today.label || longDate(today.date)} · {longDate(today.date)}</span><h3>{today.title}</h3><p>{today.note}</p></div>
                <span className={`ic-plan-done ${today.done === today.total ? 'all' : ''}`}>{today.done} of {today.total} done</span>
            </div>
            {today.tip && <p className="ic-plan-tip">{today.tip}</p>}
            {today.mock_next_steps && <div className="ic-plan-steps"><strong>From your mock interview report</strong><ul>{today.mock_next_steps.map(s => <li key={s}>{s}</li>)}</ul></div>}
            <ol className="ic-plan-tasks">{today.tasks.map(task => <li key={task.key} className={task.done ? 'done' : ''}>
                <div className="ic-plan-task-row">
                    {task.done ? <Check size={18} className="ic-plan-tick" /> : <Circle size={18} className="ic-plan-tick" />}
                    <div className="ic-plan-task">
                        {task.kind === 'study' || task.kind === 'focus' ? <>
                            <strong>{cap(task.text)} {task.level && <LevelChip level={task.level} />}</strong>
                            {task.key_points && task.key_points.length > 0 ? <ul className="ic-points">{task.key_points.map(p => <li key={p.text} className={p.covered ? 'covered' : ''}>
                                {p.covered ? '✓' : '○'} {p.text}{p.covered && <em> (you covered this in the skill check)</em>}</li>)}</ul>
                                : <small>A skill you chose to learn: read up on it and make notes on how it relates to your projects.</small>}
                        </> : task.kind === 'test' ? <>
                            <strong>{task.text}</strong>
                            <small>{cap(task.topic || '')} · {task.before != null ? `${task.before}% of key points before` : 'not answered before'}{task.after != null && <b> → {task.after}% now</b>}</small>
                        </> : <strong>{task.text}</strong>}
                    </div>
                </div>
                <div className="ic-plan-actions">
                    {(task.kind === 'study' || task.kind === 'focus' || task.kind === 'cheatsheet') &&
                        <button type="button" className="ic-ghost" aria-pressed={task.done} onClick={() => void tick(today, task)}><Check size={14} />{task.done ? 'Done' : task.kind === 'cheatsheet' ? 'Mark as read' : 'Mark as studied'}</button>}
                    {(task.kind === 'study' || task.kind === 'test') && task.question_id &&
                        <button type="button" className="ic-ghost" onClick={() => setOpen(open === task.key ? null : task.key)}><Mic size={14} />{open === task.key ? 'Close' : task.kind === 'test' ? (task.done ? 'Answer again' : 'Answer') : 'Try the question'}</button>}
                    {task.kind === 'cheatsheet' && <button type="button" className="ic-ghost" onClick={openReports}><FileText size={14} />Open cheat sheet</button>}
                    {task.kind === 'mock' && <button type="button" className="ic-ghost" onClick={task.done ? openReports : startMock}><Flag size={14} />{task.done ? 'See the report' : 'Start the mock interview'}</button>}
                    {task.kind === 'warmup' && <button type="button" className="ic-ghost" onClick={() => practise(task.question_id!)}><Mic size={14} />Warm up</button>}
                </div>
                {recorder(task)}
            </li>)}</ol>
        </section>

        {topics.length > 0 && <section>
            <div className="ic-section-head"><h3>Your topics</h3></div>
            <ul className="ic-plan-topics">{topics.map(t => <li key={t.id}>
                <span>{cap(t.topic)}</span>
                <span className="ic-plan-move"><LevelChip level={t.start} value={t.start_knowledge} />{(t.level !== t.start || t.knowledge !== t.start_knowledge) && <>→<LevelChip level={t.level} value={t.knowledge} /></>}</span>
            </li>)}</ul>
        </section>}

        {later.length > 0 && <section>
            <div className="ic-section-head"><h3>Coming up</h3></div>
            <ol className="ic-plan-days">{later.map(day => <li key={day.date} className={`kind-${day.kind}`}>
                <span className="ic-plan-kind">{day.title}</span>
                <strong>{day.label || longDate(day.date)}</strong>{day.label && <small>{longDate(day.date)}</small>}
                <ul>{day.tasks.map(t => <li key={t.key}>{t.kind === 'test' ? cap(t.topic || t.text) : cap(t.text)}</li>)}</ul>
            </li>)}</ol>
            <p className="coach-method">Later days update from your answers: a topic you answer well moves down the list, a weak one comes back sooner. Today’s list stays fixed until tomorrow.</p>
        </section>}

        {earlier.length > 0 && <details className="ic-plan-earlier"><summary>Earlier days ({earlier.reduce((n, d) => n + d.done, 0)} of {earlier.reduce((n, d) => n + d.total, 0)} tasks done)</summary>
            <ul>{earlier.map(d => <li key={d.date}><span>{longDate(d.date)} · {d.title}</span><span>{d.done} of {d.total} done</span></li>)}</ul>
        </details>}
    </div>;
}

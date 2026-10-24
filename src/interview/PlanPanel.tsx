import { useState } from 'react';
import { BookOpen, Check, Circle, ClipboardList, ExternalLink, FileText, Flag, Mic, Sparkles, Target, X } from 'lucide-react';
import { api } from '../api';
import AnswerRecorder from './AnswerRecorder';

type Level = 'strong' | 'developing' | 'weak' | 'not_assessed' | 'to_learn';
type Point = { text: string; covered: boolean };
type Resource = { title: string; url: string; source: string };
type Task = { kind: 'study' | 'test' | 'mock' | 'focus' | 'cheatsheet' | 'warmup'; key: string; text: string; done: boolean; topic_id?: string; topic?: string;
    question_id?: string | null; question?: string | null; key_points?: Point[]; resources?: Resource[]; level?: Level; before?: number | null; after?: number | null };
type DayKind = 'study' | 'test' | 'mock' | 'focus' | 'interview';
type Day = { date: string; label: string; kind: DayKind; title: string; note: string; tasks: Task[]; done: number; total: number; tip?: string; mock_next_steps?: string[] };
type TopicRow = { id: string; topic: string; requirement: { text: string }; learning: boolean; start: Level; start_knowledge: number | null; level: Level; knowledge: number | null; resources?: Resource[] };
export type Plan = { job: { document_id: string; title?: string }; status: 'active' | 'interview_today' | 'passed' | 'needs_setup' | 'needs_check'; interview_date: string | null;
    today?: string; days_left?: number; per_day?: number; topics?: TopicRow[]; days?: Day[] };

const LEVEL: Record<Level, [string, string]> = {
    strong: ['Strong', 'good'], developing: ['Developing', 'fair'], weak: ['Weak', 'poor'], not_assessed: ['Not assessed', 'none'], to_learn: ['To learn', 'none'],
};
const KIND: Record<DayKind, { icon: typeof BookOpen; short: string }> = {
    study: { icon: BookOpen, short: 'Study' }, test: { icon: ClipboardList, short: 'Test' }, mock: { icon: Flag, short: 'Mock' },
    focus: { icon: Target, short: 'Focus' }, interview: { icon: Sparkles, short: 'Interview' },
};
const TECHNICAL_SECONDS = 75; // Matches ROUND_TARGET_SECONDS['technical'] on the server.
const cap = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;
// A short summary of what a day holds, shown on its calendar tile.
const contents = (day: Day) => day.kind === 'test' ? plural(day.tasks.filter(t => t.kind === 'test').length, 'question')
    : day.kind === 'study' ? plural(day.tasks.length, 'topic') : day.kind === 'focus' ? plural(day.tasks.filter(t => t.kind === 'focus').length, 'topic') : '';
const asDate = (value: string) => new Date(`${value}T00:00`);
export const longDate = (value: string) => asDate(value).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
export const countdown = (plan: Plan) => plan.status === 'interview_today' ? 'Interview today' : plan.days_left === 1 ? 'Interview tomorrow' : `Interview in ${plan.days_left} days`;

function LevelChip({ level, value }: { level: Level; value?: number | null }) {
    const [label, tone] = LEVEL[level];
    return <span className={`ic-level tone-${tone}`}>{label}{value != null ? ` · ${value}%` : ''}</span>;
}

function Resources({ links }: { links?: Resource[] }) {
    if (!links?.length) return null;
    return <div className="ic-resources"><span>Learn it (free):</span><ul>{links.map(l => <li key={l.url}>
        <a href={l.url} target="_blank" rel="noopener noreferrer">{l.title}<ExternalLink size={12} /></a> <small>{l.source}</small>
    </li>)}</ul></div>;
}

// One day of the plan, opened from the calendar: its tasks, with actions for today and earlier days.
// A test day's questions, asked one after another like the skill check, then each topic's knowledge before and after.
function TestRunner({ day, plan, workspaceId, onAnswered }: { day: Day; plan: Plan; workspaceId: string; onAnswered: () => void }) {
    const [running, setRunning] = useState(false);
    const questions = day.tasks.filter(t => t.kind === 'test');
    const answered = questions.filter(t => t.done).length;
    const current = questions.find(t => !t.done);
    if (!current) return <div className="ic-test-done">
        <strong><Check size={16} />Test complete: {plural(questions.length, 'question')} answered</strong>
        <ul>{questions.map(t => <li key={t.key}><span>{cap(t.topic || '')}</span>
            <span>{t.before != null ? `${t.before}%` : '–'} → <b>{t.after != null ? `${t.after}%` : '–'}</b> of key points</span></li>)}</ul>
        <small>Your next days use these results: topics you now know well move down the list.</small>
    </div>;
    if (!running) return <div className="ic-test-start">
        <div><strong>{plural(questions.length, 'question')}, out loud, one after another</strong>
            <small>{answered ? `${answered} of ${questions.length} answered so far. ` : ''}No feedback until the end, like the real interview.</small></div>
        <button type="button" className="button dark" onClick={() => setRunning(true)}><Mic size={15} />{answered ? 'Continue the test' : 'Start the test'}</button>
    </div>;
    const position = questions.indexOf(current);
    return <div className="ic-test-run">
        <div className="ic-test-progress">{questions.map((t, i) => <span key={t.key} className={t.done ? 'done' : i === position ? 'current' : ''}>{i + 1}</span>)}
            <small>Question {position + 1} of {questions.length} · {cap(current.topic || '')}</small></div>
        <p className="ic-question">{current.text}</p>
        <AnswerRecorder key={current.key} workspaceId={workspaceId} questionId={current.question_id!} questionText={current.text} jobId={plan.job.document_id}
            onResult={onAnswered} hideFeedback targetSeconds={TECHNICAL_SECONDS} />
    </div>;
}

function DayDetails({ day, plan, workspaceId, today, tick, onAnswered, practise, startMock, openReports, close }: {
    day: Day; plan: Plan; workspaceId: string; today: string; tick: (day: Day, task: Task) => void; onAnswered: () => void;
    practise: (questionId: string) => void; startMock: () => void; openReports: () => void; close: () => void }) {
    const [open, setOpen] = useState<string | null>(null); // The task whose question is open for an answer.
    const isToday = day.date === today;
    const future = day.date > today;
    const Icon = KIND[day.kind].icon;
    return <section className={`ic-plan-day kind-${day.kind}`} aria-label={`${day.title}, ${longDate(day.date)}`}>
        <div className="ic-plan-day-head">
            <Icon size={22} />
            <div><span className="ic-eyebrow-dark">{isToday ? 'Today · ' : day.label ? `${day.label} · ` : ''}{longDate(day.date)}</span>
                <h3>{day.title}{contents(day) && <small> · {contents(day)}</small>}</h3><p>{day.note}</p></div>
            {!future && <span className={`ic-plan-done ${day.done === day.total ? 'all' : ''}`}>{day.done} of {day.total} done</span>}
            <button type="button" className="icon-button ic-plan-close" aria-label="Close this day" onClick={close}><X size={18} /></button>
        </div>
        {future && <p className="ic-plan-ahead">{day.kind === 'test'
            ? `This test opens on ${asDate(day.date).toLocaleDateString(undefined, { weekday: 'long' })}. It will ask these ${plural(day.tasks.length, 'question')} on the topics you study before it; they may change if your answers improve.`
            : 'Coming up. You can read ahead now; questions open on the day, and the topics may change if your answers improve.'}</p>}
        {day.kind === 'test' && !future && <TestRunner day={day} plan={plan} workspaceId={workspaceId} onAnswered={onAnswered} />}
        {day.tip && <p className="ic-plan-tip">{day.tip}</p>}
        {day.mock_next_steps && <div className="ic-plan-steps"><strong>From your mock interview report</strong><ul>{day.mock_next_steps.map(s => <li key={s}>{s}</li>)}</ul></div>}
        <ol className="ic-plan-tasks">{day.tasks.map(task => <li key={task.key} className={task.done ? 'done' : ''}>
            <div className="ic-plan-task-row">
                {task.done ? <Check size={18} className="ic-plan-tick" /> : <Circle size={18} className="ic-plan-tick" />}
                <div className="ic-plan-task">
                    {task.kind === 'study' || task.kind === 'focus' ? <>
                        <strong>{cap(task.text)} {task.level && <LevelChip level={task.level} />}</strong>
                        {task.key_points && task.key_points.length > 0 ? <ul className="ic-points">{task.key_points.map(p => <li key={p.text} className={p.covered ? 'covered' : ''}>
                            {p.covered ? '✓' : '○'} {p.text}{p.covered && <em> (you covered this in the skill check)</em>}</li>)}</ul>
                            : <small>A skill you chose to learn: work through the material below and note how it connects to your projects.</small>}
                        <Resources links={task.resources} />
                    </> : task.kind === 'test' ? <>
                        <strong>{task.text}</strong>
                        <small>{cap(task.topic || '')} · {task.before != null ? `${task.before}% of key points before` : 'not answered before'}{task.after != null && <b> → {task.after}% now</b>}</small>
                    </> : <strong>{task.text}</strong>}
                </div>
            </div>
            {!future && <div className="ic-plan-actions">
                {(task.kind === 'study' || task.kind === 'focus' || task.kind === 'cheatsheet') &&
                    <button type="button" className="ic-ghost" aria-pressed={task.done} onClick={() => tick(day, task)}><Check size={14} />{task.done ? 'Done' : task.kind === 'cheatsheet' ? 'Mark as read' : 'Mark as studied'}</button>}
                {isToday && task.question_id && (task.kind === 'study' || (task.kind === 'test' && task.done)) &&
                    <button type="button" className="ic-ghost" onClick={() => setOpen(open === task.key ? null : task.key)}><Mic size={14} />{open === task.key ? 'Close' : task.kind === 'test' ? 'Answer again' : 'Try the question'}</button>}
                {task.kind === 'cheatsheet' && <button type="button" className="ic-ghost" onClick={openReports}><FileText size={14} />Open cheat sheet</button>}
                {task.kind === 'mock' && <button type="button" className="ic-ghost" onClick={task.done ? openReports : startMock}><Flag size={14} />{task.done ? 'See the report' : 'Start the mock interview'}</button>}
                {task.kind === 'warmup' && <button type="button" className="ic-ghost" onClick={() => practise(task.question_id!)}><Mic size={14} />Warm up</button>}
            </div>}
            {open === task.key && task.question_id && <div className="ic-plan-answer">
                <AnswerRecorder workspaceId={workspaceId} questionId={task.question_id} questionText={task.question || task.text} jobId={plan.job.document_id}
                    onResult={onAnswered} targetSeconds={TECHNICAL_SECONDS} />
            </div>}
        </li>)}</ol>
    </section>;
}

// Plan tab: a calendar from the skill check to the interview. Each day opens to show what to do.
export default function PlanPanel({ workspaceId, plan, setPlan, onAnswered, practise, startMock, openReports }: {
    workspaceId: string; plan: Plan | null; setPlan: (plan: Plan) => void; onAnswered: () => void; practise: (questionId: string) => void;
    startMock: () => void; openReports: () => void }) {
    const [selected, setSelected] = useState<string | null>(null);
    const [error, setError] = useState('');
    if (!plan || !plan.days) return <p className="live-progress"><span className="live-dot" /> Loading your plan…</p>;
    if (plan.status === 'passed') return <section className="ic-plan-setup"><h3>Your interview date has passed</h3><p>Use Edit setup to choose a new date, and the plan will start again from your latest results.</p></section>;
    async function tick(day: Day, task: Task) {
        setError('');
        try { setPlan(await api<Plan>(`/interview/${workspaceId}/plan/tick`, { date: day.date, key: task.key, done: !task.done })); }
        catch (e) { setError(e instanceof Error ? e.message : 'Could not save that.'); }
    }
    const today = plan.today!;
    const topics = plan.topics || [];
    const count = (level: Level, key: 'start' | 'level') => topics.filter(t => t[key] === level).length;
    const open = plan.days.find(d => d.date === selected);

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

        <section>
            <div className="ic-section-head"><h3>Your preparation calendar</h3>
                <p className="ic-plan-legend">{(Object.keys(KIND) as DayKind[]).map(k => <span key={k} className={`kind-${k}`}><i />{KIND[k].short}</span>)}</p></div>
            <ol className="ic-calendar">{plan.days.map(day => {
                const date = asDate(day.date);
                const finished = day.total > 0 && day.done === day.total;
                const Icon = KIND[day.kind].icon;
                return <li key={day.date}>
                    <button type="button" className={`ic-cal-day kind-${day.kind} ${day.date === today ? 'today' : ''} ${day.date < today ? 'past' : ''} ${finished ? 'finished' : ''} ${selected === day.date ? 'open' : ''}`}
                        aria-expanded={selected === day.date} aria-label={`${day.title}, ${longDate(day.date)}${day.date === today ? ', today' : ''}${finished ? ', done' : ''}`}
                        onClick={() => setSelected(selected === day.date ? null : day.date)}>
                        <span className="ic-cal-week">{day.date === today ? 'Today' : date.toLocaleDateString(undefined, { weekday: 'short' })}</span>
                        <span className="ic-cal-num">{date.getDate()}</span>
                        <span className="ic-cal-month">{date.toLocaleDateString(undefined, { month: 'short' })}</span>
                        <span className="ic-cal-kind"><Icon size={13} />{KIND[day.kind].short}</span>
                        {contents(day) && <span className="ic-cal-count">{contents(day)}</span>}
                        {finished ? <span className="ic-cal-status done"><Check size={14} /></span>
                            : day.date <= today && day.done > 0 ? <span className="ic-cal-status">{day.done}/{day.total}</span> : null}
                    </button>
                </li>;
            })}</ol>
            {!open && <p className="coach-method">Choose a day to see what to do. Today is highlighted; finished days get a tick.</p>}
            {open && <DayDetails key={open.date} day={open} plan={plan} workspaceId={workspaceId} today={today} tick={(d, t) => void tick(d, t)} onAnswered={onAnswered}
                practise={practise} startMock={startMock} openReports={openReports} close={() => setSelected(null)} />}
        </section>

        {topics.length > 0 && <section>
            <div className="ic-section-head"><h3>Your topics</h3></div>
            <ul className="ic-plan-topics">{topics.map(t => <li key={t.id}>
                <span>{cap(t.topic)}</span>
                <span className="ic-plan-move"><LevelChip level={t.start} value={t.start_knowledge} />{(t.level !== t.start || t.knowledge !== t.start_knowledge) && <>→<LevelChip level={t.level} value={t.knowledge} /></>}</span>
            </li>)}</ul>
            <p className="coach-method">Later days update from your answers: a topic you answer well moves down the list, a weak one comes back sooner. Today’s list stays fixed until tomorrow.</p>
        </section>}
    </div>;
}

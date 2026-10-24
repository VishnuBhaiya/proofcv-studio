import { useState } from 'react';
import { CalendarDays, Check, Circle, FileText, Flag, Mic } from 'lucide-react';
import { api } from '../api';
import { ROUND_INFO } from './types';

type Task = { kind: 'question' | 'mock' | 'cheatsheet'; question_id?: string; text: string; round?: string; reason?: string | null; done: boolean };
type Day = { date: string; label: string; tasks: Task[] };
export type Plan = { job: { document_id: string; title: string }; interview_date: string | null; today?: string; days_left?: number;
    status?: 'active' | 'interview_today' | 'passed'; counts?: { new: number; work: number; strong: number }; total?: number; days?: Day[]; unplanned?: string[] };

const NAMED = ['Today', 'Tomorrow', 'Interview day']; // Other days are labelled with the browser's own date format.
const MAX_DAYS = 60; // Matches plan.MAX_DAYS on the server.
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export const longDate = (value: string) => new Date(`${value}T00:00`).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
export const countdown = (plan: Plan) => plan.status === 'interview_today' ? 'Interview today' : plan.days_left === 1 ? 'Interview tomorrow' : `Interview in ${plan.days_left} days`;

function DatePicker({ value, onSave, onCancel, busy }: { value: string; onSave: (date: string) => void; onCancel?: () => void; busy: boolean }) {
    const [date, setDate] = useState(value);
    const today = new Date();
    const last = new Date(today.getFullYear(), today.getMonth(), today.getDate() + MAX_DAYS);
    return <form className="ic-plan-date" onSubmit={e => { e.preventDefault(); if (date) onSave(date); }}>
        <label>Interview date<input type="date" value={date} min={iso(today)} max={iso(last)} required onChange={e => setDate(e.target.value)} /></label>
        <button type="submit" className="button dark" disabled={!date || busy}>{busy ? 'Planning…' : value ? 'Update plan' : 'Make my plan'}</button>
        {onCancel && <button type="button" className="button subtle" onClick={onCancel}>Cancel</button>}
    </form>;
}

// Plan tab: a day-by-day countdown to the interview, ticked off automatically as the user practises.
export default function PlanPanel({ workspaceId, plan, setPlan, practise, startMock, openReports }: {
    workspaceId: string; plan: Plan | null; setPlan: (plan: Plan) => void; practise: (questionId: string) => void; startMock: () => void; openReports: () => void }) {
    const [editing, setEditing] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    if (!plan) return <p className="live-progress"><span className="live-dot" /> Loading your plan…</p>;
    async function save(date: string | null) {
        setBusy(true);
        setError('');
        try { setPlan(await api<Plan>(`/interview/${workspaceId}/plan`, { job: plan!.job.document_id, interview_date: date })); setEditing(false); }
        catch (e) { setError(e instanceof Error ? e.message : 'Could not save the date.'); }
        finally { setBusy(false); }
    }
    const errorLine = error && <p className="live-error" role="alert">{error}</p>;
    if (!plan.interview_date || plan.status === 'passed' || editing) return <section className="ic-plan-setup">
        <CalendarDays size={28} />
        <h3>{plan.status === 'passed' && !editing ? 'Your interview date has passed' : 'When is your interview?'}</h3>
        <p>Pick the date of your {plan.job.title} interview. The coach lays out a few questions a day, starting with the ones you have not practised and the
            ones that still need work, with a full mock interview the day before. Tasks tick off by themselves as you practise.</p>
        <DatePicker value={editing ? plan.interview_date || '' : ''} onSave={date => void save(date)} onCancel={editing ? () => setEditing(false) : undefined} busy={busy} />
        {errorLine}
    </section>;

    const [today, ...later] = plan.days || [];
    const done = today.tasks.filter(t => t.done).length;
    const counts = plan.counts!;
    const action = (task: Task) => task.kind === 'question' ? <button type="button" className="ic-ghost" onClick={() => practise(task.question_id!)}><Mic size={14} />Practise</button>
        : task.kind === 'mock' ? <button type="button" className="ic-ghost" onClick={startMock}><Flag size={14} />Start mock</button>
        : <button type="button" className="ic-ghost" onClick={openReports}><FileText size={14} />Open cheat sheet</button>;
    return <div className="ic-plan">
        <section className="ic-plan-head">
            <div>
                <span className="ic-eyebrow-dark">{plan.job.title}</span>
                <h3>{countdown(plan)}</h3>
                <p>{longDate(plan.interview_date)}</p>
            </div>
            <div className="ic-plan-head-actions">
                <button type="button" className="button subtle" onClick={() => setEditing(true)}>Change date</button>
                <button type="button" className="text-button" disabled={busy} onClick={() => void save(null)}>Remove plan</button>
            </div>
            <div className="ic-plan-progress" aria-label={`${counts.strong} strong, ${counts.work} need work, ${counts.new} not practised`}>
                <span className="strong" style={{ flex: counts.strong }} /><span className="work" style={{ flex: counts.work }} /><span className="new" style={{ flex: counts.new }} />
            </div>
            <p className="ic-plan-legend"><i className="strong" />{counts.strong} strong <i className="work" />{counts.work} need work <i className="new" />{counts.new} not practised · {plan.total} questions for this job</p>
        </section>
        {errorLine}
        <section className="ic-plan-today">
            <div className="ic-section-head"><h3>{today.label}</h3><span className={`ic-plan-done ${done === today.tasks.length ? 'all' : ''}`}>{done} of {today.tasks.length} done</span></div>
            <ol>{today.tasks.map((task, i) => <li key={i} className={task.done ? 'done' : ''}>
                {task.done ? <Check size={18} className="ic-plan-tick" /> : <Circle size={18} className="ic-plan-tick" />}
                <span className="ic-plan-task">
                    <strong>{task.text}</strong>
                    <small>{task.round ? ROUND_INFO[task.round]?.title : task.kind === 'mock' ? 'Mock interview' : 'Cheat sheet'}{task.reason ? ` · ${task.reason}` : ''}</small>
                </span>
                {!task.done && action(task)}
            </li>)}</ol>
            {done === today.tasks.length && today.tasks.length > 0 && <p className="coach-method">All done for today. Extra practice is welcome, but rest counts too.</p>}
        </section>
        {plan.unplanned && plan.unplanned.length > 0 && <p className="ic-plan-warning">
            Not enough days to cover everything: {plan.unplanned.length === 1 ? '1 question that still needs work is' : `${plan.unplanned.length} questions that still need work are`} not in the plan. The plan puts the ones you have never tried first.
        </p>}
        {later.length > 0 && <section>
            <div className="ic-section-head"><h3>Coming up</h3></div>
            <ol className="ic-plan-days">{later.map(day => <li key={day.date} className={day.label === 'Interview day' ? 'interview' : ''}>
                <strong>{NAMED.includes(day.label) ? day.label : longDate(day.date)}</strong>{NAMED.includes(day.label) && <small>{longDate(day.date)}</small>}
                <ul>{day.tasks.map((t, i) => <li key={i} className={t.kind}>{t.kind === 'question' ? t.text : t.kind === 'mock' ? 'Mock interview' : t.text}</li>)}</ul>
            </li>)}</ol>
            <p className="coach-method">Later days are recalculated from your real practice each time you open the plan; today’s list stays fixed until tomorrow.</p>
        </section>}
    </div>;
}

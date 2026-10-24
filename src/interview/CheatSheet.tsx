import { useEffect, useState } from 'react';
import { Download, FileText } from 'lucide-react';
import { api } from '../api';

type Part = { label: string; text: string; placeholder: boolean };
type Sheet = {
    job: { document_id: string; title: string }; practised: number; readiness: { overall: number; band: string; answered: number; total: number } | null;
    introduction: { source: string; text: string }; strengths: { requirement: string; evidence: string }[];
    stories: { question: string; score: number | null; source: string; parts: [string, string][] }[];
    gaps: { requirement: string; answer: Part[] }[]; questions_to_ask: string[]; reminders: string[]; note: string;
};

// Reports tab: the one-page sheet to read just before the interview, built from practice so far.
export default function CheatSheet({ workspaceId, jobId, practised }: { workspaceId: string; jobId: string; practised: number }) {
    const [sheet, setSheet] = useState<Sheet | null>(null);
    const [error, setError] = useState('');
    useEffect(() => {
        setSheet(null);
        api<Sheet>(`/interview/${workspaceId}/cheatsheet?job=${encodeURIComponent(jobId)}`).then(setSheet).catch(e => setError(e.message));
    }, [workspaceId, jobId, practised]);
    return <section>
        <div className="ic-section-head">
            <h3>Interview-day cheat sheet</h3>
            <a className="button dark" href={`/api/interview/${workspaceId}/cheatsheet.pdf?job=${encodeURIComponent(jobId)}`} download="interview-cheat-sheet.pdf"><Download size={15} />Download PDF</a>
        </div>
        {error ? <p className="live-error" role="alert">{error}</p> : !sheet ? <p className="live-progress"><span className="live-dot" /> Building your cheat sheet from your practice…</p> :
            <div className="ic-sheet">
                <div className="ic-sheet-col">
                    <h4>Your 30-second introduction</h4>
                    <p>{sheet.introduction.text}</p>
                    <small>{sheet.introduction.source}</small>
                    <h4>Top strengths</h4>
                    <ul>{sheet.strengths.map(s => <li key={s.requirement}><strong>{s.requirement}</strong><small>{s.evidence}</small></li>)}</ul>
                    <h4>Delivery reminders</h4>
                    <ul>{sheet.reminders.map(t => <li key={t}>{t}</li>)}</ul>
                </div>
                <div className="ic-sheet-col">
                    <h4>Best STAR stories</h4>
                    {sheet.stories.map(s => <div key={s.question} className="ic-sheet-story">
                        <strong>{s.question}{s.score != null && <span className="ic-sheet-score">{s.score}/100</span>}</strong>
                        <ul>{s.parts.map(([label, text], i) => <li key={i}><b>{label}:</b> {text}</li>)}</ul>
                        <small>{s.source}</small>
                    </div>)}
                    <h4>Honest answers for your gaps</h4>
                    {sheet.gaps.length ? sheet.gaps.map(g => <div key={g.requirement} className="ic-sheet-story">
                        <strong>{g.requirement}</strong>
                        <ul>{g.answer.map((p, i) => <li key={i} className={p.placeholder ? 'ic-sheet-prompt' : undefined}><b>{p.label}:</b> {p.text}</li>)}</ul>
                    </div>) : <p>No gaps found for this job.</p>}
                    <h4>Questions to ask them</h4>
                    <ul>{sheet.questions_to_ask.map(q => <li key={q}>{q}</li>)}</ul>
                </div>
                <p className="coach-method ic-sheet-note"><FileText size={13} /> {sheet.practised} questions practised{sheet.readiness ? ` · latest mock interview ${sheet.readiness.band === 'Incomplete' ? `unfinished (${sheet.readiness.answered} of ${sheet.readiness.total} answered)` : `${sheet.readiness.overall}/100 (${sheet.readiness.band})`}` : ''}. {sheet.note}</p>
            </div>}
    </section>;
}

import { useEffect, useState } from 'react';
import { ArrowRight, Download, Flag, RotateCcw, X } from 'lucide-react';
import { api } from '../api';
import AnswerRecorder from './AnswerRecorder';
import { speak } from './speech';
import { Question, ROUND_INFO } from './types';

type Session = { id: string; created_at: string; job: { document_id: string; title: string }; questions: Question[]; answers: Record<string, number> };
type Row = { position: number; question: string; round: string; answered: boolean; score?: number; components?: Record<string, number>; needs_work?: string[] };
type Report = { session_id: string; job: { title: string }; overall: number; band: string; answered: number; total: number; by_part: Record<string, number>;
    averages: { words_per_minute: number; fillers_per_minute: number; long_pauses: number }; strengths: string[]; weak_spots: string[]; next_steps: string[]; questions: Row[]; method: string };
const PART_LABEL: Record<string, string> = { delivery: 'Delivery', structure: 'STAR structure', content: 'Key points', honesty: 'Claims backed by profile' };

export default function MockInterview({ workspaceId, jobId, onExit }: { workspaceId: string; jobId: string; onExit: () => void }) {
    const [session, setSession] = useState<Session | null>(null);
    const [index, setIndex] = useState(0);
    const [answered, setAnswered] = useState<number[]>([]);
    const [report, setReport] = useState<Report | null>(null);
    const [readAloud, setReadAloud] = useState(true);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const [seconds, setSeconds] = useState(0);
    const question = session?.questions[index];
    useEffect(() => {
        if (!question || report) return;
        setSeconds(0);
        if (readAloud) speak(question.text);
        const timer = window.setInterval(() => setSeconds(s => s + 1), 1000);
        return () => window.clearInterval(timer);
    }, [session?.id, index, report]);

    async function start() {
        setBusy(true);
        setError('');
        try {
            setSession(await api<Session>(`/interview/${workspaceId}/mock`, { job: jobId }));
            setIndex(0);
            setAnswered([]);
            setReport(null);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Could not start the mock interview.');
        } finally {
            setBusy(false);
        }
    }

    async function finish() {
        setBusy(true);
        setError('');
        try {
            setReport(await api<Report>(`/interview/${workspaceId}/mock/${session!.id}/report`));
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Could not build the report.');
        } finally {
            setBusy(false);
        }
    }

    if (!session) return <section className="coach-mock">
        <div className="mock-head"><h3>Full mock interview</h3><button type="button" className="text-button" onClick={onExit}><X size={15} />Back to practice</button></div>
        <p>Five questions in a row, like a real interview: a 90-second introduction, two behavioural questions, one technical question and one about a gap in your profile. Feedback is held back until the end, then you get a readiness report you can download as a PDF.</p>
        <p className="coach-method">Takes about 7 minutes. Everything is analysed on this computer.</p>
        <label className="room-aloud"><input type="checkbox" checked={readAloud} onChange={e => setReadAloud(e.target.checked)} />Read each question aloud</label>
        <div className="mock-actions"><button type="button" className="button dark" disabled={busy} onClick={() => void start()}>Start the mock interview<ArrowRight size={15} /></button></div>
        {error && <p className="live-error" role="alert">{error}</p>}
    </section>;

    if (report) return <section className="coach-mock mock-report">
        <div className="mock-head"><h3>Interview readiness report</h3><button type="button" className="text-button" onClick={onExit}><X size={15} />Back to practice</button></div>
        <div className={`mock-score band-${report.band.replace(/\s+/g, '-').toLowerCase()}`}><strong>{report.overall}</strong><span>/100 · {report.band}</span></div>
        <p className="coach-method">{report.job.title} · {report.answered} of {report.total} questions answered</p>
        <div className="coach-metrics">{Object.entries(report.by_part).map(([k, v]) => <span key={k}><strong>{v}</strong> {PART_LABEL[k] ?? k}</span>)}</div>
        <p className="coach-method">Average pace {report.averages.words_per_minute} words/min · {report.averages.fillers_per_minute} filler words/min · {report.averages.long_pauses} long pauses</p>
        <div className="mock-lists">
            {report.strengths.length > 0 && <div><h4>Strengths</h4><ul>{report.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul></div>}
            {report.weak_spots.length > 0 && <div><h4>Weak spots</h4><ul>{report.weak_spots.map((s, i) => <li key={i}>{s}</li>)}</ul></div>}
            <div><h4>Next steps</h4><ul>{report.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul></div>
        </div>
        <table className="mock-table"><thead><tr><th>#</th><th>Question</th><th>Score</th><th>Main issue</th></tr></thead>
            <tbody>{report.questions.map(r => <tr key={r.position}><td>{r.position}</td><td>{r.question}</td><td>{r.answered ? r.score : '–'}</td><td>{!r.answered ? 'Not answered' : r.needs_work?.[0] ?? 'None'}</td></tr>)}</tbody></table>
        <details className="coach-method"><summary>How the score is calculated</summary><p>{report.method}</p></details>
        <div className="mock-actions">
            <a className="button dark" href={`/api/interview/${workspaceId}/mock/${report.session_id}/report.pdf`} download="interview-readiness-report.pdf"><Download size={15} />Download PDF report</a>
            <button type="button" className="button subtle" disabled={busy} onClick={() => void start()}><RotateCcw size={15} />New mock interview</button>
        </div>
    </section>;

    const last = index === session.questions.length - 1;
    return <section className="coach-mock">
        <div className="mock-head"><h3>Mock interview · Question {index + 1} of {session.questions.length}</h3><button type="button" className="text-button" onClick={onExit}><X size={15} />Leave</button></div>
        <div className="room-steps">{session.questions.map((q, i) => <span key={i} className={`room-step ${answered.includes(i) ? 'strong' : 'new'} ${i === index ? 'current' : ''}`}>{i + 1}</span>)}</div>
        <p className="room-meta">{ROUND_INFO[question!.round]?.title} · {seconds}s on this question{question!.seconds ? ` · aim for about ${question!.seconds} seconds` : ''}</p>
        <h2 className="room-question">{question!.text}</h2>
        <AnswerRecorder key={`${session.id}-${index}`} workspaceId={workspaceId} questionId={question!.id} questionText={question!.text} jobId={session.job.document_id}
            requirementId={question!.requirement?.id} hideFeedback extra={{ mock_session: session.id, mock_position: index }} onResult={() => setAnswered(a => [...new Set([...a, index])])} />
        <div className="room-nav">
            <span className="coach-method">{answered.length} of {session.questions.length} answered{answered.includes(index) ? ' · you can record this one again' : ''}</span>
            {last
                ? <button type="button" className="button dark" disabled={busy || !answered.length} onClick={() => void finish()}><Flag size={15} />Finish and see report</button>
                : <button type="button" className="button dark" onClick={() => setIndex(index + 1)}>{answered.includes(index) ? 'Next question' : 'Skip question'}<ArrowRight size={15} /></button>}
        </div>
        {error && <p className="live-error" role="alert">{error}</p>}
    </section>;
}

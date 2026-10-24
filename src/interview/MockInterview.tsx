import { useEffect, useState } from 'react';
import { ArrowRight, Flag, ListChecks, RotateCcw } from 'lucide-react';
import { api } from '../api';
import AnswerRecorder from './AnswerRecorder';
import ReportView from './ReportView';
import { speak } from './speech';
import { Question, Report, ROUND_INFO } from './types';
import { Bubble } from './ui';

type Session = { id: string; created_at: string; job: { document_id: string; title: string }; questions: Question[]; answers: Record<string, unknown> };

// Mock interview tab: five questions with one follow-up each, feedback held back for the report.
export default function MockInterview({ workspaceId, jobId, onFinished, openReports }: { workspaceId: string; jobId: string; onFinished: () => void; openReports: () => void }) {
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
            onFinished();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Could not build the report.');
        } finally {
            setBusy(false);
        }
    }

    if (!session) return <div className="ic-mock-intro">
        <div className="ic-mock-steps">
            {[['5 questions', 'A 90-second introduction, two behavioural, one technical and one about a gap in your profile.'],
              ['Follow-up questions', 'After each answer the interviewer cross-questions you once, like a real panel.'],
              ['Readiness report', 'Feedback is held back until the end, then you get a scored report and a PDF.']].map(([title, text], i) =>
                <div key={title}><span className="ic-step-number">{i + 1}</span><strong>{title}</strong><p>{text}</p></div>)}
        </div>
        <label className="ic-switch"><input type="checkbox" checked={readAloud} onChange={e => setReadAloud(e.target.checked)} /><span />Read questions aloud</label>
        <div className="ic-actions">
            <button type="button" className="button dark ic-big" disabled={busy} onClick={() => void start()}><Flag size={16} />Start the mock interview</button>
            <button type="button" className="button subtle" onClick={openReports}><ListChecks size={15} />See past reports</button>
        </div>
        <p className="coach-method">About 8 minutes. Everything is analysed on this computer.</p>
        {error && <p className="live-error" role="alert">{error}</p>}
    </div>;

    if (report) return <ReportView workspaceId={workspaceId} report={report} actions={<>
        <button type="button" className="button subtle" disabled={busy} onClick={() => void start()}><RotateCcw size={15} />New mock interview</button>
        <button type="button" className="button subtle" onClick={openReports}><ListChecks size={15} />All reports</button>
    </>} />;

    const last = index === session.questions.length - 1;
    return <div className="ic-mock">
        <div className="ic-mock-progress">
            {session.questions.map((q, i) => <span key={i} className={`ic-mock-step ${answered.includes(i) ? 'done' : ''} ${i === index ? 'current' : ''}`} title={ROUND_INFO[q.round]?.title}>{i + 1}</span>)}
            <span className="ic-mock-timer">{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}{question!.seconds ? ` · aim for ${question!.seconds}s` : ''}</span>
        </div>
        <div className="ic-thread">
            <Bubble who="interviewer" meta={`${ROUND_INFO[question!.round]?.title} · question ${index + 1} of ${session.questions.length}`}><span className="ic-question">{question!.text}</span></Bubble>
            <AnswerRecorder key={`${session.id}-${index}`} workspaceId={workspaceId} questionId={question!.id} questionText={question!.text} jobId={session.job.document_id}
                requirementId={question!.requirement?.id} hideFeedback readAloud={readAloud} extra={{ mock_session: session.id, mock_position: index }}
                onResult={() => setAnswered(a => [...new Set([...a, index])])} />
        </div>
        <div className="ic-stage-nav">
            <span className="coach-method">{answered.length} of {session.questions.length} answered</span>
            {last
                ? <button type="button" className="button dark" disabled={busy || !answered.length} onClick={() => void finish()}><Flag size={15} />Finish and see report</button>
                : <button type="button" className="button dark" onClick={() => setIndex(index + 1)}>{answered.includes(index) ? 'Next question' : 'Skip question'}<ArrowRight size={15} /></button>}
        </div>
        {error && <p className="live-error" role="alert">{error}</p>}
    </div>;
}

import { useState } from 'react';
import { ArrowLeft, Flag } from 'lucide-react';
import { api } from '../api';
import CheatSheet from './CheatSheet';
import EvaluationRecorder from './EvaluationRecorder';
import ReportView from './ReportView';
import { Overview, Questions, questionStatus, Report, ReportItem, ROUND_INFO, ROUNDS } from './types';
import { Bar, ScoreRing } from './ui';

// Reports tab: every mock interview's readiness report, the interview-day cheat sheet, and practice progress.
export default function ReportsPanel({ workspaceId, reports, questions, overview, startMock }: {
    workspaceId: string; reports: ReportItem[]; questions: Questions; overview: Overview; startMock: () => void }) {
    const [open, setOpen] = useState<Report | null>(null);
    const [error, setError] = useState('');
    async function view(id: string) {
        setError('');
        try { setOpen(await api<Report>(`/interview/${workspaceId}/mock/${id}/report`)); } catch (e) { setError(e instanceof Error ? e.message : 'Could not open the report.'); }
    }
    if (open) return <ReportView workspaceId={workspaceId} report={open} actions={<button type="button" className="button subtle" onClick={() => setOpen(null)}><ArrowLeft size={15} />All reports</button>} />;
    const finished = reports.filter(r => r.overall != null);
    return <div className="ic-reports">
        <section>
            <div className="ic-section-head"><h3>Mock interview reports</h3><button type="button" className="button dark" onClick={startMock}><Flag size={15} />New mock interview</button></div>
            {finished.length ? <ol className="ic-report-list">{finished.map(r => <li key={r.id}>
                <button type="button" onClick={() => void view(r.id)}>
                    <ScoreRing value={r.overall} size={64} />
                    <span className="ic-report-item">
                        <strong>{r.band}</strong>
                        <span>{r.job.title}</span>
                        <small>{new Date(r.created_at).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })} · {r.answered} of {r.total} answered{r.cross_questioning != null ? ` · follow-ups ${r.cross_questioning}` : ''}</small>
                    </span>
                    <span className="ic-open">Open report</span>
                </button>
            </li>)}</ol> : <div className="ic-empty"><Flag size={28} /><strong>No reports yet</strong><p>Finish a mock interview to get your first readiness report.</p><button type="button" className="button dark" onClick={startMock}>Start a mock interview</button></div>}
            {error && <p className="live-error" role="alert">{error}</p>}
        </section>
        <CheatSheet workspaceId={workspaceId} jobId={questions.job.document_id} practised={Object.keys(overview).length} />
        <section>
            <div className="ic-section-head"><h3>Practice progress</h3></div>
            <div className="ic-progress">{ROUNDS.map(r => {
                const items = questions.rounds[r] || [];
                const strong = items.filter(q => questionStatus(overview, q.id) === 'strong').length;
                const tried = items.filter(q => overview[q.id]).length;
                return <div key={r}><Bar label={ROUND_INFO[r].title} value={items.length ? Math.round(strong / items.length * 100) : 0} /><small>{strong} strong · {tried} practised · {items.length} questions</small></div>;
            })}</div>
        </section>
        <details className="ic-eval"><summary>Accuracy evaluation (for the project report)</summary><EvaluationRecorder workspaceId={workspaceId} /></details>
    </div>;
}

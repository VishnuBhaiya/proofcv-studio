import { ReactNode } from 'react';
import { Download } from 'lucide-react';
import { PART_LABEL, Report, tone } from './types';
import { Bar, ScoreRing } from './ui';

// A mock interview's readiness report, shown after the interview and from the Reports tab.
export default function ReportView({ workspaceId, report, actions }: { workspaceId: string; report: Report; actions?: ReactNode }) {
    const when = new Date(report.created_at).toLocaleString(undefined, { day: 'numeric', month: 'long', year: 'numeric', hour: 'numeric', minute: '2-digit' });
    return <div className="ic-report">
        <div className="ic-report-head">
            <ScoreRing value={report.overall} size={132} label={report.band} />
            <div className="ic-report-title">
                <span className="ic-eyebrow-dark">Interview readiness report</span>
                <h3>{report.job.title}</h3>
                <p>{when} · {report.answered} of {report.total} questions answered{report.cross_questioning != null ? ` · follow-ups ${report.cross_questioning}/100` : ''}</p>
                <div className="ic-report-actions">
                    <a className="button dark" href={`/api/interview/${workspaceId}/mock/${report.session_id}/report.pdf`} download="interview-readiness-report.pdf"><Download size={15} />Download PDF</a>
                    {actions}
                </div>
            </div>
            <div className="ic-bars">{Object.entries(report.by_part).map(([k, v]) => <Bar key={k} label={PART_LABEL[k] ?? k} value={v} />)}
                {report.cross_questioning != null && <Bar label="Follow-ups" value={report.cross_questioning} />}</div>
        </div>
        <div className="ic-report-lists">
            {report.strengths.length > 0 && <div className="ic-good"><h5>Strengths</h5><ul>{report.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul></div>}
            {report.weak_spots.length > 0 && <div className="ic-fix"><h5>Weak spots</h5><ul>{report.weak_spots.map((s, i) => <li key={i}>{s}</li>)}</ul></div>}
            <div className="ic-next"><h5>Next steps</h5><ul>{report.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul></div>
        </div>
        <p className="coach-method">Average pace {report.averages.words_per_minute} words/min · {report.averages.fillers_per_minute} filler words per minute · {report.averages.long_pauses} long pauses</p>
        <ol className="ic-report-questions">{report.questions.map(r => <li key={r.position}>
            <span className={`ic-pill tone-${r.answered ? tone(r.score) : 'none'}`}>{r.answered ? r.score : '–'}</span>
            <div>
                <strong>{r.question}</strong>
                <small>{!r.answered ? 'Not answered' : r.needs_work?.[0] ?? 'No issues found'}</small>
                {r.follow_up && <div className="ic-report-follow"><span className={`ic-pill small tone-${tone(r.follow_up.score)}`}>{r.follow_up.score}</span><span>Follow-up: {r.follow_up.question}</span></div>}
            </div>
        </li>)}</ol>
        <details className="coach-method"><summary>How the score is calculated</summary><p>{report.method}</p></details>
    </div>;
}

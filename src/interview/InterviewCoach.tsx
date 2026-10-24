import { useEffect, useState } from 'react';
import { CalendarDays, FileText, Flag, Mic, Pencil, Presentation, Target, UserRound } from 'lucide-react';
import { api, Workspace } from '../api';
import FitPanel, { Fit } from './FitPanel';
import InterviewRoom from './InterviewRoom';
import MockInterview from './MockInterview';
import PlanPanel, { countdown, Plan } from './PlanPanel';
import ReportsPanel from './ReportsPanel';
import SetupPanel, { jobLabel, Status } from './SetupPanel';
import SlideDeck from './SlideDeck';
import { configureSpeech, SpeechSettings } from './speech';
import { Overview, Questions, questionStatus, ReportItem } from './types';
import { ScoreRing } from './ui';
import './interview.css';

type Tab = 'practice' | 'plan' | 'mock' | 'reports' | 'fit' | 'deck';
const TABS: { id: Tab; label: string; icon: typeof Mic }[] = [
    { id: 'practice', label: 'Practice', icon: Mic }, { id: 'plan', label: 'Plan', icon: CalendarDays }, { id: 'mock', label: 'Mock interview', icon: Flag }, { id: 'reports', label: 'Reports', icon: FileText },
    { id: 'fit', label: 'Your fit', icon: Target }, { id: 'deck', label: 'Intro deck', icon: Presentation },
];

export default function InterviewCoach({ workspace, go }: { workspace: Workspace; go: (page: 'profile' | 'jobs') => void }) {
    const [status, setStatus] = useState<Status | null>(null);
    const [error, setError] = useState('');
    const [editing, setEditing] = useState(false);
    const [fit, setFit] = useState<Fit | null>(null);
    const [questions, setQuestions] = useState<Questions | null>(null);
    const [overview, setOverview] = useState<Overview>({});
    const [reports, setReports] = useState<ReportItem[]>([]);
    const [tab, setTab] = useState<Tab>('practice');
    const [plan, setPlan] = useState<Plan | null>(null);
    const [focus, setFocus] = useState<{ id: string } | null>(null);
    // The voice (Piper) and speech recognition (Accurate) are fixed; this only tells the page what is installed.
    useEffect(() => {
        api<SpeechSettings>(`/interview/${workspace.id}/speech`).then(s => configureSpeech(workspace.id, s)).catch(() => undefined);
    }, [workspace.id]);
    const jobId = status?.setup?.job || '';
    useEffect(() => {
        setError('');
        api<Status>(`/interview/${workspace.id}/status`).then(setStatus).catch(e => setError(e.message));
    }, [workspace.id, workspace.revision, workspace.confirmed_revision, workspace.retrieval, workspace.draft?.job.document_id]);
    const refresh = () => {
        api<Overview>(`/interview/${workspace.id}/attempts`).then(setOverview).catch(() => undefined);
        api<ReportItem[]>(`/interview/${workspace.id}/mock`).then(setReports).catch(() => undefined);
        if (jobId) api<Plan>(`/interview/${workspace.id}/plan?job=${encodeURIComponent(jobId)}`).then(setPlan).catch(() => undefined);
    };
    useEffect(() => {
        setFit(null);
        setQuestions(null);
        setPlan(null);
        if (!status?.profile_confirmed || !jobId) return;
        const query = `?job=${encodeURIComponent(jobId)}`;
        api<Fit>(`/interview/${workspace.id}/fit${query}`).then(setFit).catch(e => setError(e.message));
        api<Questions>(`/interview/${workspace.id}/questions${query}`).then(setQuestions).catch(e => setError(e.message));
        refresh();
    }, [status, jobId, workspace.id]);

    if (error) return <div className="page-content"><p className="live-error" role="alert">{error}</p></div>;
    if (!status) return <div className="page-content"><p className="live-progress"><span className="live-dot" /> Loading Interview Coach…</p></div>;
    if (!status.profile_confirmed) return <div className="page-content interview-coach">
        <section className="ic-setup">
            <span className="ic-eyebrow-dark">Interview Coach</span>
            <h2>One step before you practise</h2>
            <p>The coach builds every question and every example answer from your confirmed facts.</p>
            <div className="ic-setup-steps">
                <div><UserRound size={20} /><div><strong>Confirm your profile</strong><span>Review your facts and confirm them</span></div><button className="button dark" onClick={() => go('profile')}>Open profile</button></div>
            </div>
        </section>
    </div>;
    if (!status.setup || editing) return <div className="page-content interview-coach">
        <SetupPanel workspaceId={workspace.id} status={status} onSaved={next => { setStatus(next); setEditing(false); setTab('practice'); }}
            onCancel={status.setup ? () => setEditing(false) : undefined} />
    </div>;

    const current = status.jobs.find(j => j.document_id === jobId) || { document_id: jobId, title: jobId, location: null, focus: null, match_score: null, cv_target: false };
    const all = questions ? Object.values(questions.rounds).flat() : [];
    const practised = new Set(all.filter(q => overview[q.id]).map(q => q.id)).size;
    const strong = new Set(all.filter(q => questionStatus(overview, q.id) === 'strong').map(q => q.id)).size;
    const latest = reports.find(r => r.overall != null);
    return <div className="page-content interview-coach">
        <section className="ic-hero">
            <div className="ic-hero-main">
                <span className="ic-eyebrow">Interview Coach</span>
                <h2>Ready for <em>{jobLabel(current)}</em>?</h2>
                <p>Practise out loud, get scored on delivery, structure and evidence, and handle follow-up questions. Everything is analysed on this computer.</p>
                <div className="ic-hero-setup">
                    {plan?.interview_date && plan.status !== 'passed' && <button type="button" className="ic-countdown" onClick={() => setTab('plan')}><CalendarDays size={14} />{countdown(plan)}</button>}
                    <button type="button" className="ic-countdown" onClick={() => setEditing(true)}><Pencil size={14} />Edit setup</button>
                </div>
            </div>
            <div className="ic-hero-side">
                <ScoreRing value={latest?.overall} size={112} label={latest ? latest.band : 'No mock yet'} />
                <div className="ic-stats">
                    <div><strong>{practised}/{all.length || '–'}</strong><span>practised</span></div>
                    <div><strong>{strong}</strong><span>strong answers</span></div>
                    <div><strong>{reports.filter(r => r.overall != null).length}</strong><span>{reports.filter(r => r.overall != null).length === 1 ? 'mock interview' : 'mock interviews'}</span></div>
                </div>
            </div>
        </section>
        <nav className="ic-tabs" role="tablist" aria-label="Interview Coach">{TABS.map(t => <button type="button" role="tab" key={t.id} aria-selected={tab === t.id} className={tab === t.id ? 'active' : ''} onClick={() => setTab(t.id)}>
            <t.icon size={16} />{t.label}{t.id === 'reports' && reports.filter(r => r.overall != null).length > 0 && <span className="ic-count">{reports.filter(r => r.overall != null).length}</span>}
        </button>)}</nav>
        <div className="ic-panel">
            {!questions ? <p className="live-progress"><span className="live-dot" /> Picking questions for {current.title}…</p> : <>
                {tab === 'practice' && <InterviewRoom key={questions.job.document_id} workspaceId={workspace.id} questions={questions} overview={overview} onAnswered={refresh} focus={focus} />}
                {tab === 'plan' && <PlanPanel workspaceId={workspace.id} plan={plan} setPlan={setPlan} practise={id => { setFocus({ id }); setTab('practice'); }}
                    startMock={() => setTab('mock')} openReports={() => setTab('reports')} />}
                {tab === 'mock' && <MockInterview key={questions.job.document_id} workspaceId={workspace.id} jobId={questions.job.document_id} onFinished={refresh} openReports={() => setTab('reports')} />}
                {tab === 'reports' && <ReportsPanel workspaceId={workspace.id} reports={reports} questions={questions} overview={overview} startMock={() => setTab('mock')} />}
                {tab === 'fit' && <FitPanel fit={fit} />}
                {tab === 'deck' && <SlideDeck workspaceId={workspace.id} jobId={questions.job.document_id} />}
            </>}
        </div>
    </div>;
}

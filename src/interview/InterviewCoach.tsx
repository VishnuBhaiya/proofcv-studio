import { useEffect, useState } from 'react';
import { CalendarDays, Check, FileText, Flag, Mic, Presentation, Target, UserRound } from 'lucide-react';
import { api, Workspace } from '../api';
import FitPanel, { Fit } from './FitPanel';
import InterviewRoom from './InterviewRoom';
import MockInterview from './MockInterview';
import PlanPanel, { countdown, Plan } from './PlanPanel';
import ReportsPanel from './ReportsPanel';
import SlideDeck from './SlideDeck';
import { configureSpeech, setSpeechChoice, speechChoice, SpeechSettings, stopSpeaking } from './speech';
import { Overview, Questions, questionStatus, ReportItem } from './types';
import { ScoreRing } from './ui';
import './interview.css';

type Readiness = { workspace_id: string; profile_confirmed: boolean; matched_jobs: { document_id: string; title: string; score: number }[]; target_job: { document_id: string; title: string } | null; rounds: string[] };
type Tab = 'practice' | 'plan' | 'mock' | 'reports' | 'fit' | 'deck';
const TABS: { id: Tab; label: string; icon: typeof Mic }[] = [
    { id: 'practice', label: 'Practice', icon: Mic }, { id: 'plan', label: 'Plan', icon: CalendarDays }, { id: 'mock', label: 'Mock interview', icon: Flag }, { id: 'reports', label: 'Reports', icon: FileText },
    { id: 'fit', label: 'Your fit', icon: Target }, { id: 'deck', label: 'Intro deck', icon: Presentation },
];

export default function InterviewCoach({ workspace, go }: { workspace: Workspace; go: (page: 'profile' | 'jobs') => void }) {
    const [status, setStatus] = useState<Readiness | null>(null);
    const [error, setError] = useState('');
    const [jobId, setJobId] = useState('');
    const [fit, setFit] = useState<Fit | null>(null);
    const [questions, setQuestions] = useState<Questions | null>(null);
    const [overview, setOverview] = useState<Overview>({});
    const [reports, setReports] = useState<ReportItem[]>([]);
    const [tab, setTab] = useState<Tab>('practice');
    const [speech, setSpeech] = useState<SpeechSettings | null>(null);
    const [plan, setPlan] = useState<Plan | null>(null);
    const [focus, setFocus] = useState<{ id: string } | null>(null);
    const [, setChoiceVersion] = useState(0);
    useEffect(() => {
        api<SpeechSettings>(`/interview/${workspace.id}/speech`).then(s => { configureSpeech(workspace.id, s); setSpeech(s); }).catch(() => undefined);
    }, [workspace.id]);
    const choose = (update: Parameters<typeof setSpeechChoice>[0]) => { stopSpeaking(); setSpeechChoice(update); setChoiceVersion(v => v + 1); };
    useEffect(() => {
        setError('');
        api<Readiness>(`/interview/${workspace.id}/status`).then(setStatus).catch(e => setError(e.message));
    }, [workspace.id, workspace.revision, workspace.confirmed_revision, workspace.retrieval, workspace.draft?.job.document_id]);
    const refresh = () => {
        api<Overview>(`/interview/${workspace.id}/attempts`).then(setOverview).catch(() => undefined);
        api<ReportItem[]>(`/interview/${workspace.id}/mock`).then(setReports).catch(() => undefined);
        api<Plan>(`/interview/${workspace.id}/plan${jobId ? `?job=${encodeURIComponent(jobId)}` : ''}`).then(setPlan).catch(() => undefined);
    };
    useEffect(() => {
        setFit(null);
        setQuestions(null);
        setPlan(null);
        if (!status?.profile_confirmed || !status.target_job) return;
        const query = jobId ? `?job=${encodeURIComponent(jobId)}` : '';
        api<Fit>(`/interview/${workspace.id}/fit${query}`).then(setFit).catch(e => setError(e.message));
        api<Questions>(`/interview/${workspace.id}/questions${query}`).then(setQuestions).catch(e => setError(e.message));
        refresh();
    }, [status, jobId, workspace.id]);

    if (error) return <div className="page-content"><p className="live-error" role="alert">{error}</p></div>;
    if (!status) return <div className="page-content"><p className="live-progress"><span className="live-dot" /> Loading Interview Coach…</p></div>;
    if (!status.profile_confirmed || !status.target_job) return <div className="page-content interview-coach">
        <section className="ic-setup">
            <span className="ic-eyebrow-dark">Interview Coach</span>
            <h2>Two steps before you practise</h2>
            <p>The coach builds every question and every example answer from your confirmed facts and the job you chose.</p>
            <div className="ic-setup-steps">
                <div className={status.profile_confirmed ? 'done' : ''}><UserRound size={20} /><div><strong>Confirm your profile</strong><span>{status.profile_confirmed ? 'Done' : 'Review your facts and confirm them'}</span></div>{status.profile_confirmed ? <Check size={18} /> : <button className="button dark" onClick={() => go('profile')}>Open profile</button>}</div>
                <div className={status.target_job ? 'done' : ''}><Target size={20} /><div><strong>Choose a target job</strong><span>{status.target_job ? status.target_job.title : 'Pick one of your top matches'}</span></div>{status.target_job ? <Check size={18} /> : <button className="button dark" disabled={!status.profile_confirmed} onClick={() => go('jobs')}>Discover jobs</button>}</div>
            </div>
        </section>
    </div>;

    const jobs = [status.target_job, ...status.matched_jobs.filter(j => j.document_id !== status.target_job!.document_id)];
    const current = jobs.find(j => j.document_id === (jobId || status.target_job!.document_id))!;
    const all = questions ? Object.values(questions.rounds).flat() : [];
    const practised = new Set(all.filter(q => overview[q.id]).map(q => q.id)).size;
    const strong = new Set(all.filter(q => questionStatus(overview, q.id) === 'strong').map(q => q.id)).size;
    const latest = reports.find(r => r.overall != null);
    return <div className="page-content interview-coach">
        <section className="ic-hero">
            <div className="ic-hero-main">
                <span className="ic-eyebrow">Interview Coach</span>
                <h2>Ready for <em>{current.title}</em>?</h2>
                <p>Practise out loud, get scored on delivery, structure and evidence, and handle follow-up questions. Everything is analysed on this computer.</p>
                <label className="ic-job">Preparing for
                    <select value={current.document_id} onChange={e => setJobId(e.target.value)}>{jobs.map(j => <option key={j.document_id} value={j.document_id}>{j.title}</option>)}</select>
                </label>
                {plan?.interview_date && plan.status !== 'passed' && <button type="button" className="ic-countdown" onClick={() => setTab('plan')}><CalendarDays size={14} />{countdown(plan)}</button>}
                {speech && <div className="ic-speech-options">
                    <label className="ic-job">Voice
                        <select value={speechChoice().voice} onChange={e => choose({ voice: e.target.value as 'natural' | 'browser' })}>
                            {speech.voice.available && <option value="natural">{speech.voice.label}</option>}
                            <option value="browser">Browser voice</option>
                        </select>
                    </label>
                    <label className="ic-job">Speech recognition
                        <select value={speechChoice().recognition ?? ''} onChange={e => choose({ recognition: e.target.value })}>
                            {speech.recognition.options.filter(o => o.installed).map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
                        </select>
                    </label>
                </div>}
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

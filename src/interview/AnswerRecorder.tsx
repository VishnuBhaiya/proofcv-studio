import { useEffect, useRef, useState } from 'react';
import { Mic, Square, Volume2 } from 'lucide-react';
import { api } from '../api';
import { speak, SpeechState, stopSpeaking } from './speech';
import { PART_LABEL } from './types';
import LiveMeter from './LiveMeter';
import { Bar, Bubble, ScoreRing } from './ui';

type Delivery = { word_count: number; speaking_seconds: number; words_per_minute: number; pauses: { after: string; seconds: number }[]; long_pauses: number; fillers: { word: string; start: number }[]; fillers_per_minute: number; thinking_seconds: number; duration: number; notes: string[] };
type StarLabel = 'situation' | 'task' | 'action' | 'result' | 'other';
type Star = { sentences: { text: string; label: StarLabel; confidence: number; uncertain: boolean }[]; present: Record<Exclude<StarLabel, 'other'>, boolean>; notes: string[]; model: { trained_on: { stories: number; sentences: number } } };
type Content = { key_points: { text: string; status: 'covered' | 'partial' | 'missed'; similarity: number; quote: string | null }[]; score: number; notes: string[] };
type Claim = { text: string; status: 'supported' | 'weak' | 'unmatched'; similarity: number; support: { label: string; text: string } | null; flags: { type: string; value: string; message: string }[] };
type FactCheck = { claims: Claim[]; notes: string[] };
type Change = { metric: string; label: string; before: number; after: number; direction: 'better' | 'worse' | 'same' };
type Progress = { attempt: number; needs_work: string[]; changes: Change[] };
type ExampleAnswer = { kind: string; parts: { label: string; text: string; source: string | null; placeholder: boolean }[]; text: string; note: string };
type SlideCoverage = { slides: { title: string; status: 'covered' | 'partial' | 'missed'; quote: string | null }[]; covered: number; total: number; notes: string[] };
type FollowUp = { question: string; why: string; kind: string; key_point: string | null; depth: number };
type Answer = { question_id: string; round: string; transcript: string; model: string; target_seconds: number | null; delivery: Delivery; star?: Star; content?: Content;
    fact_check?: FactCheck; progress: Progress; example_answer?: ExampleAnswer; slide_coverage?: SlideCoverage; follow_up?: FollowUp | null; score: { overall: number; components: Record<string, number> } };
const STAR_PARTS: [Exclude<StarLabel, 'other'>, string][] = [['situation', 'Situation'], ['task', 'Task'], ['action', 'Action'], ['result', 'Result']];
const POINT_MARK = { covered: '✓', partial: '~', missed: '✗' };
const CLAIM_LABEL = { supported: 'Matches your profile', weak: 'Loosely matches', unmatched: 'Not in your profile' };
const ARROW = { better: '↑', worse: '↓', same: '=' };
const MAX_SECONDS = 300;
const FOLLOW_UP_SECONDS = 45; // Matches followup.FOLLOW_UP_SECONDS on the server.
const show = (metric: string, value: number) => metric === 'key_points' ? `${Math.round(value * 100)}%` : metric === 'length_gap' ? `${value}%` : String(value);

function toBase64(blob: Blob) {
    return new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
        reader.onerror = () => reject(new Error('Could not read the recording.'));
        reader.readAsDataURL(blob);
    });
}

export function SpeakButton({ text, label }: { text: string; label: string }) {
    const [state, setState] = useState<SpeechState>('idle');
    useEffect(() => () => { if (state === 'speaking') stopSpeaking(); }, [state]);
    return <span className="coach-speak">
        <button type="button" className="ic-ghost" aria-pressed={state === 'speaking'} onClick={() => {
            if (state === 'speaking') { stopSpeaking(); setState('idle'); } else speak(text, setState);
        }}>{state === 'speaking' ? <><Square size={13} />Speaking… (stop)</> : <><Volume2 size={15} />{label}</>}</button>
        {state === 'failed' && <small role="status">No sound played. Check your volume, or open the app in Chrome.</small>}
    </span>;
}

function praise(answer: Answer) {
    const c = answer.score.components;
    const d = answer.delivery;
    const good: string[] = [];
    if (c.delivery >= 80) good.push(`Clear delivery: ${d.words_per_minute} words/min with ${d.fillers.length} filler word${d.fillers.length === 1 ? '' : 's'}.`);
    if ((c.length ?? 0) >= 80) good.push('A good length for this question.');
    if ((c.structure ?? 0) >= 100) good.push('All four STAR parts were there.');
    if (answer.content && (c.content ?? 0) >= 80) good.push(`Covered ${answer.content.key_points.filter(k => k.status === 'covered').length} of ${answer.content.key_points.length} key points.`);
    if (answer.fact_check?.claims.length && (c.honesty ?? 0) >= 100) good.push('Everything you claimed is backed by your profile.');
    return good;
}

function Details({ answer }: { answer: Answer }) {
    const tabs = [
        ['transcript', 'Transcript & delivery'],
        ...(answer.star ? [['star', 'STAR structure']] : []),
        ...(answer.content ? [['content', 'Key points']] : []),
        ...(answer.slide_coverage ? [['slides', 'Slides covered']] : []),
        ...(answer.fact_check?.claims.length ? [['facts', 'Fact check']] : []),
        ...(answer.example_answer ? [['example', 'Example answer']] : []),
    ] as [string, string][];
    // Closed until asked for, so the interviewer's follow-up stays in view under the score.
    const [tab, setTab] = useState('');
    const d = answer.delivery;
    return <div className="ic-details">
        <div className="ic-detail-tabs" role="tablist" aria-label="Answer details"><span>Details:</span>{tabs.map(([id, label]) => <button type="button" role="tab" key={id} aria-selected={tab === id} className={tab === id ? 'active' : ''} onClick={() => setTab(tab === id ? '' : id)}>{label}</button>)}</div>
        {tab && <div className="ic-detail-panel">
            {tab === 'transcript' && <>
                <div className="coach-metrics">
                    <span><strong>{d.words_per_minute}</strong> words/min</span>
                    <span><strong>{d.speaking_seconds}s</strong> spoken{answer.target_seconds ? ` of ~${answer.target_seconds}s` : ''}</span>
                    <span><strong>{d.fillers.length}</strong> filler words{d.fillers.length ? ` (${[...new Set(d.fillers.map(f => f.word))].join(', ')})` : ''}</span>
                    <span><strong>{d.long_pauses}</strong> long pauses</span>
                </div>
                <ul className="coach-notes">{d.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
                <p className="coach-method">Transcribed on this computer by {answer.model}. The audio was not saved.</p>
            </>}
            {tab === 'star' && answer.star && <>
                <div className="coach-star-parts">{STAR_PARTS.map(([key, name]) => <span key={key} className={`star-part ${answer.star!.present[key] ? 'present' : 'missing'}`}>{answer.star!.present[key] ? '✓' : '✗'} {name}</span>)}</div>
                <ol className="coach-star-sentences">{answer.star.sentences.map((s, i) => <li key={i} className={`star-${s.label}`}><span className="star-tag" title={`Confidence ${Math.round(s.confidence * 100)}%`}>{s.label}{s.uncertain ? '?' : ''}</span>{s.text}</li>)}</ol>
                <ul className="coach-notes">{answer.star.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
                <p className="coach-method">Labelled by our own classifier, trained on {answer.star.model.trained_on.sentences} sentences. “?” marks a low-confidence label.</p>
            </>}
            {tab === 'content' && answer.content && <ul className="coach-points">{answer.content.key_points.map((k, i) => <li key={i} className={`point-${k.status}`}><span className="point-mark">{POINT_MARK[k.status]}</span><div>{k.text}{k.quote && <small>You said: “{k.quote}”</small>}</div></li>)}</ul>}
            {tab === 'slides' && answer.slide_coverage && <>
                <ul className="coach-points">{answer.slide_coverage.slides.map((s, i) => <li key={i} className={`point-${s.status}`}><span className="point-mark">{POINT_MARK[s.status]}</span><div>{s.title}{s.quote && <small>You said: “{s.quote}”</small>}</div></li>)}</ul>
                <ul className="coach-notes">{answer.slide_coverage.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
            </>}
            {tab === 'facts' && answer.fact_check && <>
                <ul className="coach-claims">{answer.fact_check.claims.map((c, i) => <li key={i} className={`claim-${c.status}${c.flags.length ? ' claim-flagged' : ''}`}>
                    <span className="claim-status">{CLAIM_LABEL[c.status]}</span>“{c.text}”
                    {c.support && <small>Closest fact · {c.support.label}: {c.support.text}</small>}
                    {c.flags.map((f, j) => <small className="claim-flag" key={j}>⚠ {f.message}</small>)}
                </li>)}</ul>
                <ul className="coach-notes">{answer.fact_check.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
            </>}
            {tab === 'example' && answer.example_answer && <>
                <ol className="ic-example">{answer.example_answer.parts.map((p, i) => <li key={i} className={p.placeholder ? 'example-prompt' : ''}><span className="example-label">{p.label}</span>{p.text}{p.source && <small>From {p.source}</small>}</li>)}</ol>
                <p className="coach-method">{answer.example_answer.note}</p>
                {answer.example_answer.text && <SpeakButton text={answer.example_answer.text} label="Hear example" />}
            </>}
        </div>}
    </div>;
}

function Scorecard({ answer }: { answer: Answer }) {
    const good = praise(answer);
    const fixes = answer.progress.needs_work;
    const changed = answer.progress.changes.filter(c => c.direction !== 'same');
    return <div className="ic-scorecard">
        <div className="ic-score-head">
            <ScoreRing value={answer.score.overall} size={84} />
            <div>
                <strong className="ic-verdict">{fixes.length ? 'Needs work' : 'Strong answer'}</strong>
                <span className="ic-attempt">Attempt {answer.progress.attempt}</span>
                {changed.length > 0 && <div className="coach-changes">{changed.map(c => <span key={c.metric} className={`change-${c.direction}`}>{ARROW[c.direction]} {c.label}: {show(c.metric, c.before)} → {show(c.metric, c.after)}</span>)}</div>}
            </div>
            <div className="ic-bars">{Object.entries(answer.score.components).map(([k, v]) => <Bar key={k} label={PART_LABEL[k] ?? k} value={v} />)}</div>
        </div>
        <div className="ic-went">
            {good.length > 0 && <div className="ic-good"><h5>What went well</h5><ul>{good.map((g, i) => <li key={i}>{g}</li>)}</ul></div>}
            {fixes.length > 0 && <div className="ic-fix"><h5>Fix next</h5><ul>{fixes.map((f, i) => <li key={i}>{f}</li>)}</ul></div>}
        </div>
        <Details answer={answer} />
    </div>;
}

export default function AnswerRecorder({ workspaceId, questionId, questionText, jobId, requirementId, onResult, extra, hideFeedback, readAloud, nested, targetSeconds }: {
    workspaceId: string; questionId: string; questionText: string; jobId?: string; requirementId?: string; onResult?: () => void;
    extra?: Record<string, unknown>; hideFeedback?: boolean; readAloud?: boolean; nested?: boolean; targetSeconds?: number | null }) {
    const [phase, setPhase] = useState<'idle' | 'recording' | 'processing'>('idle');
    const [seconds, setSeconds] = useState(0);
    const [answer, setAnswer] = useState<Answer | null>(null);
    const [error, setError] = useState('');
    const [stream, setStream] = useState<MediaStream | null>(null);
    const recorder = useRef<MediaRecorder | null>(null);
    const timer = useRef<number | undefined>(undefined);
    useEffect(() => () => { window.clearInterval(timer.current); recorder.current?.stream.getTracks().forEach(t => t.stop()); }, []);
    useEffect(() => { if (readAloud && answer?.follow_up) speak(answer.follow_up.question); }, [answer]);

    async function start() {
        stopSpeaking(); // The read-aloud voice must not end up in the recording.
        setError('');
        setAnswer(null);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const chunks: Blob[] = [];
            const media = new MediaRecorder(stream);
            media.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
            media.onstop = async () => {
                stream.getTracks().forEach(t => t.stop());
                setStream(null);
                window.clearInterval(timer.current);
                setPhase('processing');
                try {
                    const audio = await toBase64(new Blob(chunks, { type: media.mimeType }));
                    setAnswer(await api<Answer>(`/interview/${workspaceId}/answer`, { ...extra, question_id: questionId, audio, question_text: questionText, job: jobId, requirement_id: requirementId }));
                    onResult?.();
                } catch (e) {
                    setError(e instanceof Error ? e.message : 'Transcription failed.');
                } finally {
                    setPhase('idle');
                }
            };
            recorder.current = media;
            setStream(stream);
            media.start();
            setSeconds(0);
            setPhase('recording');
            timer.current = window.setInterval(() => setSeconds(s => { if (s + 1 >= MAX_SECONDS) media.stop(); return s + 1; }), 1000);
        } catch {
            setError('Microphone access was blocked. Allow the microphone for this page and try again.');
        }
    }

    const minutes = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
    return <div className={`ic-turn ${nested ? 'ic-nested' : ''}`}>
        <div className="ic-controls">
            <button type="button" className={`ic-mic ${phase}`} disabled={phase === 'processing'} aria-label={phase === 'recording' ? 'Stop recording' : 'Record your answer'}
                onClick={() => phase === 'recording' ? recorder.current?.stop() : void start()}>
                {phase === 'recording' ? <Square size={20} /> : <Mic size={22} />}
            </button>
            <div className="ic-controls-text">
                <strong>{phase === 'recording' ? `Recording ${minutes}` : phase === 'processing' ? 'Analysing your answer…' : answer ? 'Record again' : nested ? 'Answer the follow-up' : 'Record your answer'}</strong>
                <span>{phase === 'recording' ? 'Tap the button to stop' : phase === 'processing' ? 'Transcribing and scoring on this computer' : 'Tap the microphone and speak naturally'}</span>
            </div>
            {!nested && <SpeakButton text={questionText} label="Hear question" />}
            {phase === 'recording' && stream && <LiveMeter stream={stream} seconds={seconds} target={targetSeconds ?? null} />}
        </div>
        {error && <p className="live-error" role="alert">{error}</p>}
        {answer && <>
            <Bubble who="you" meta={`${answer.delivery.speaking_seconds}s · ${answer.delivery.words_per_minute} words/min`}>{answer.transcript || <em>No speech was detected.</em>}</Bubble>
            {hideFeedback ? <p className="ic-saved">Answer saved. Feedback comes in your report at the end.</p> : <Scorecard answer={answer} />}
            {answer.follow_up && <>
                <Bubble who="interviewer" kind="follow-up" meta={<>Why: {answer.follow_up.why} <SpeakButton text={answer.follow_up.question} label="Hear it" /></>}>{answer.follow_up.question}</Bubble>
                <AnswerRecorder key={answer.follow_up.question} workspaceId={workspaceId} questionId={questionId} questionText={answer.follow_up.question} jobId={jobId}
                    requirementId={requirementId} onResult={onResult} extra={{ ...extra, follow_up: answer.follow_up }} hideFeedback={hideFeedback} readAloud={readAloud} nested targetSeconds={FOLLOW_UP_SECONDS} />
            </>}
        </>}
    </div>;
}

import { useEffect, useRef, useState } from 'react';
import { Mic, Square, Volume2 } from 'lucide-react';
import { api } from '../api';
import { speak, SpeechState, stopSpeaking } from './speech';

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
type Answer = { question_id: string; round: string; transcript: string; model: string; target_seconds: number | null; delivery: Delivery; star?: Star; content?: Content; fact_check?: FactCheck; progress: Progress; example_answer?: ExampleAnswer; slide_coverage?: SlideCoverage };
const ARROW = { better: '↑', worse: '↓', same: '=' };
const show = (metric: string, value: number) => metric === 'key_points' ? `${Math.round(value * 100)}%` : metric === 'length_gap' ? `${value}%` : String(value);
const POINT_MARK = { covered: '✓', partial: '~', missed: '✗' };
const CLAIM_LABEL = { supported: 'Matches your profile', weak: 'Loosely matches', unmatched: 'Not in your profile' };
const STAR_PARTS: [Exclude<StarLabel, 'other'>, string][] = [['situation', 'Situation'], ['task', 'Task'], ['action', 'Action'], ['result', 'Result']];
const MAX_SECONDS = 300;

function toBase64(blob: Blob) {
    return new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
        reader.onerror = () => reject(new Error('Could not read the recording.'));
        reader.readAsDataURL(blob);
    });
}

function SpeakButton({ text, label }: { text: string; label: string }) {
    const [state, setState] = useState<SpeechState>('idle');
    useEffect(() => () => { if (state === 'speaking') stopSpeaking(); }, [state]);
    return <span className="coach-speak">
        <button type="button" className="text-button" aria-pressed={state === 'speaking'} onClick={() => {
            if (state === 'speaking') { stopSpeaking(); setState('idle'); } else speak(text, setState);
        }}>{state === 'speaking' ? <><Square size={13} />Speaking… (click to stop)</> : <><Volume2 size={15} />{label}</>}</button>
        {state === 'failed' && <small role="status">No sound played. Check that your volume is on, or open the app in Chrome.</small>}
    </span>;
}

export default function AnswerRecorder({ workspaceId, questionId, questionText, jobId, requirementId, onResult, extra, hideFeedback }: { workspaceId: string; questionId: string; questionText: string; jobId?: string; requirementId?: string; onResult?: () => void; extra?: Record<string, unknown>; hideFeedback?: boolean }) {
    const [phase, setPhase] = useState<'idle' | 'recording' | 'processing'>('idle');
    const [seconds, setSeconds] = useState(0);
    const [answer, setAnswer] = useState<Answer | null>(null);
    const [error, setError] = useState('');
    const recorder = useRef<MediaRecorder | null>(null);
    const timer = useRef<number | undefined>(undefined);
    useEffect(() => () => { window.clearInterval(timer.current); recorder.current?.stream.getTracks().forEach(t => t.stop()); }, []);

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
            media.start();
            setSeconds(0);
            setPhase('recording');
            timer.current = window.setInterval(() => setSeconds(s => { if (s + 1 >= MAX_SECONDS) media.stop(); return s + 1; }), 1000);
        } catch {
            setError('Microphone access was blocked. Allow the microphone for this page and try again.');
        }
    }

    const d = answer?.delivery;
    return <div className="coach-recorder">
        <div className="coach-recorder-actions">
            <SpeakButton text={questionText} label="Hear question" />
            {phase === 'recording'
                ? <button type="button" className="button dark" onClick={() => recorder.current?.stop()}><Square size={14} />Stop · {seconds}s</button>
                : <button type="button" className="button dark" disabled={phase === 'processing'} onClick={() => void start()}><Mic size={15} />{phase === 'processing' ? 'Transcribing locally…' : answer ? 'Record again' : 'Record answer'}</button>}
        </div>
        {error && <p className="live-error" role="alert">{error}</p>}
        {answer && hideFeedback && <p className="live-success">Answer saved{answer.transcript ? '' : ', but no speech was detected'}. Feedback comes in your report at the end.</p>}
        {answer && d && !hideFeedback && <div className="coach-result"><div className="coach-col">
            <div className={`coach-verdict ${answer.progress.needs_work.length ? 'needs-work' : 'strong'}`}>
                <strong>Attempt {answer.progress.attempt} · {answer.progress.needs_work.length ? 'Needs work' : 'Strong answer'}</strong>
                {answer.progress.needs_work.length > 0 && <ul>{answer.progress.needs_work.map((r, i) => <li key={i}>{r}</li>)}</ul>}
                {answer.progress.changes.length > 0 && <div className="coach-changes"><span>Since your last try:</span>{answer.progress.changes.some(c => c.direction !== 'same')
                    ? answer.progress.changes.filter(c => c.direction !== 'same').map(c => <span key={c.metric} className={`change-${c.direction}`} title={c.label}>{ARROW[c.direction]} {c.label}: {show(c.metric, c.before)} → {show(c.metric, c.after)}</span>)
                    : <span className="change-same">no measurable change yet</span>}</div>}
            </div>
            <p className="coach-transcript"><strong>What Whisper heard:</strong> {answer.transcript || <em>nothing</em>}</p>
            <div className="coach-metrics">
                <span><strong>{d.words_per_minute}</strong> words/min</span>
                <span><strong>{d.speaking_seconds}s</strong> spoken{answer.target_seconds ? ` / ~${answer.target_seconds}s target` : ''}</span>
                <span><strong>{d.fillers.length}</strong> filler words{d.fillers.length ? ` (${[...new Set(d.fillers.map(f => f.word))].join(', ')})` : ''}</span>
                <span><strong>{d.long_pauses}</strong> long pauses</span>
            </div>
            <ul className="coach-notes">{d.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
            {answer.star && <div className="coach-star">
                <div className="coach-star-parts">{STAR_PARTS.map(([key, name]) => <span key={key} className={`star-part ${key} ${answer.star!.present[key] ? 'present' : 'missing'}`}>{answer.star!.present[key] ? '✓' : '✗'} {name}</span>)}</div>
                <ol className="coach-star-sentences">{answer.star.sentences.map((s, i) => <li key={i} className={`star-${s.label}`}><span className="star-tag" title={`Confidence ${Math.round(s.confidence * 100)}%`}>{s.label}{s.uncertain ? '?' : ''}</span>{s.text}</li>)}</ol>
                <ul className="coach-notes">{answer.star.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
                <p className="coach-method">STAR labels come from our own classifier, trained on {answer.star.model.trained_on.sentences} labelled sentences. “?” marks a low-confidence label.</p>
            </div>}
            </div><div className="coach-col">
            {answer.slide_coverage && <div className="coach-section">
                <h4>Slides you talked about: {answer.slide_coverage.covered} of {answer.slide_coverage.total}</h4>
                <ul className="coach-points">{answer.slide_coverage.slides.map((s, i) => <li key={i} className={`point-${s.status}`}><span className="point-mark">{POINT_MARK[s.status]}</span><div>{s.title}{s.quote && <small>You said: “{s.quote}”</small>}</div></li>)}</ul>
                <ul className="coach-notes">{answer.slide_coverage.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
            </div>}
            {answer.content && <div className="coach-section">
                <h4>Key points: {answer.content.key_points.filter(k => k.status === 'covered').length} of {answer.content.key_points.length} covered</h4>
                <ul className="coach-points">{answer.content.key_points.map((k, i) => <li key={i} className={`point-${k.status}`}><span className="point-mark">{POINT_MARK[k.status]}</span><div>{k.text}{k.quote && <small>You said: “{k.quote}”</small>}</div></li>)}</ul>
                <p className="coach-method">Matched locally with MiniLM against the question’s expected key points. This checks coverage, not whether every statement is correct.</p>
            </div>}
            {answer.fact_check && answer.fact_check.claims.length > 0 && <div className="coach-section">
                <h4>Fact check against your confirmed profile</h4>
                <ul className="coach-claims">{answer.fact_check.claims.map((c, i) => <li key={i} className={`claim-${c.status}${c.flags.length ? ' claim-flagged' : ''}`}>
                    <span className="claim-status">{CLAIM_LABEL[c.status]}</span>“{c.text}”
                    {c.support && <small>Closest fact · {c.support.label}: {c.support.text}</small>}
                    {c.flags.map((f, j) => <small className="claim-flag" key={j}>⚠ {f.message}</small>)}
                </li>)}</ul>
                <ul className="coach-notes">{answer.fact_check.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
            </div>}
            {answer.example_answer && <details className="coach-example" open={answer.progress.needs_work.length > 0}>
                <summary>Example answer from your confirmed facts</summary>
                <ol>{answer.example_answer.parts.map((p, i) => <li key={i} className={p.placeholder ? 'example-prompt' : ''}><span className="example-label">{p.label}</span>{p.text}{p.source && <small>From {p.source}</small>}</li>)}</ol>
                <p className="coach-method">{answer.example_answer.note}</p>
                {answer.example_answer.text && <SpeakButton text={answer.example_answer.text} label="Hear example" />}
            </details>}
            <p className="coach-method">Transcribed on this computer by {answer.model}. The recording was not saved; the transcript and scores are kept on this computer to track your progress.</p>
        </div></div>}
    </div>;
}

import { useEffect, useRef, useState } from 'react';
import { Mic, Square, Volume2 } from 'lucide-react';
import { api } from '../api';

type Delivery = { word_count: number; speaking_seconds: number; words_per_minute: number; pauses: { after: string; seconds: number }[]; long_pauses: number; fillers: { word: string; start: number }[]; fillers_per_minute: number; thinking_seconds: number; duration: number; notes: string[] };
type StarLabel = 'situation' | 'task' | 'action' | 'result' | 'other';
type Star = { sentences: { text: string; label: StarLabel; confidence: number; uncertain: boolean }[]; present: Record<Exclude<StarLabel, 'other'>, boolean>; notes: string[]; model: { trained_on: { stories: number; sentences: number } } };
type Answer = { question_id: string; round: string; transcript: string; model: string; target_seconds: number | null; delivery: Delivery; star?: Star };
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

export function speak(text: string) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

export default function AnswerRecorder({ workspaceId, questionId, questionText }: { workspaceId: string; questionId: string; questionText: string }) {
    const [phase, setPhase] = useState<'idle' | 'recording' | 'processing'>('idle');
    const [seconds, setSeconds] = useState(0);
    const [answer, setAnswer] = useState<Answer | null>(null);
    const [error, setError] = useState('');
    const recorder = useRef<MediaRecorder | null>(null);
    const timer = useRef<number | undefined>(undefined);
    useEffect(() => () => { window.clearInterval(timer.current); recorder.current?.stream.getTracks().forEach(t => t.stop()); }, []);

    async function start() {
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
                    setAnswer(await api<Answer>(`/interview/${workspaceId}/answer`, { question_id: questionId, audio }));
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
            <button type="button" className="text-button" onClick={() => speak(questionText)}><Volume2 size={15} />Hear question</button>
            {phase === 'recording'
                ? <button type="button" className="button dark" onClick={() => recorder.current?.stop()}><Square size={14} />Stop · {seconds}s</button>
                : <button type="button" className="button dark" disabled={phase === 'processing'} onClick={() => void start()}><Mic size={15} />{phase === 'processing' ? 'Transcribing locally…' : answer ? 'Record again' : 'Record answer'}</button>}
        </div>
        {error && <p className="live-error" role="alert">{error}</p>}
        {answer && d && <div className="coach-result">
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
            <p className="coach-method">Transcribed on this computer by {answer.model}. The recording was not saved.</p>
        </div>}
    </div>;
}

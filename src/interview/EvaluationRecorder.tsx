import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Mic, Square } from 'lucide-react';
import { api } from '../api';
import { stopSpeaking } from './speech';

type Script = { id: string; question_id: string; text: string };
type State = { scripts: Script[]; recorded: string[]; seconds: Record<string, number>; min_seconds: number };

// Records the read-aloud evaluation scripts for `python -m server.interview.evaluate`.
export default function EvaluationRecorder({ workspaceId }: { workspaceId: string }) {
    const [state, setState] = useState<State | null>(null);
    const [index, setIndex] = useState(0);
    const [phase, setPhase] = useState<'idle' | 'recording' | 'saving'>('idle');
    const [seconds, setSeconds] = useState(0);
    const [error, setError] = useState('');
    const recorder = useRef<MediaRecorder | null>(null);
    const timer = useRef<number | undefined>(undefined);
    useEffect(() => { api<State>(`/interview/${workspaceId}/evaluation`).then(setState).catch(e => setError(e.message)); }, [workspaceId]);
    useEffect(() => () => { window.clearInterval(timer.current); recorder.current?.stream.getTracks().forEach(t => t.stop()); }, []);
    if (!state) return error ? <p className="live-error">{error}</p> : null;
    const script = state.scripts[index];
    const good = (id: string) => (state.seconds[id] ?? 0) >= state.min_seconds;
    const done = state.scripts.filter(s => good(s.id)).length;

    async function start() {
        stopSpeaking();
        setError('');
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const chunks: Blob[] = [];
            const media = new MediaRecorder(stream);
            media.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
            media.onstop = async () => {
                stream.getTracks().forEach(t => t.stop());
                window.clearInterval(timer.current);
                setPhase('saving');
                try {
                    const blob = new Blob(chunks, { type: media.mimeType });
                    const audio = await new Promise<string>((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(String(r.result).split(',')[1] || ''); r.onerror = reject; r.readAsDataURL(blob); });
                    const saved = await api<Omit<State, 'scripts'>>(`/interview/${workspaceId}/evaluation-sample`, { script_id: script.id, audio });
                    setState(s => s && { ...s, ...saved });
                    const length = saved.seconds[script.id] ?? 0;
                    if (length < saved.min_seconds) setError(`Only ${length} s was saved for script ${index + 1}. Read the whole script before pressing Stop, then record it again.`);
                    else setIndex(i => Math.min(i + 1, state!.scripts.length - 1));
                } catch (e) {
                    setError(e instanceof Error ? e.message : 'Could not save the recording.');
                } finally {
                    setPhase('idle');
                }
            };
            recorder.current = media;
            media.start();
            setSeconds(0);
            setPhase('recording');
            timer.current = window.setInterval(() => setSeconds(s => s + 1), 1000);
        } catch {
            setError('Microphone access was blocked. Allow the microphone for this page and try again.');
        }
    }

    return <div className="coach-eval">
        <p className="coach-method">Read each script aloud at your normal pace. The recordings stay on this computer in <code>runtime/interview-evaluation/</code> and are used only by <code>python -m server.interview.evaluate</code> to measure accuracy for the report. {done} of {state.scripts.length} recorded.</p>
        <div className="room-steps">{state.scripts.map((s, i) => <button type="button" key={s.id} className={`room-step ${good(s.id) ? 'strong' : state.recorded.includes(s.id) ? 'work' : 'new'} ${i === index ? 'current' : ''}`} onClick={() => setIndex(i)}>{i + 1}</button>)}</div>
        <p className="room-meta">Script {index + 1} of {state.scripts.length}{good(script.id) ? ` · recorded, ${state.seconds[script.id]} s (recording again replaces it)` : state.recorded.includes(script.id) ? ` · too short (${state.seconds[script.id]} s), record it again` : ''}</p>
        <p className="eval-script">{script.text}</p>
        <div className="coach-recorder-actions">
            <button type="button" className="button subtle" disabled={index === 0 || phase !== 'idle'} onClick={() => setIndex(index - 1)}><ArrowLeft size={15} />Previous</button>
            {phase === 'recording'
                ? <button type="button" className="button dark" onClick={() => recorder.current?.stop()}><Square size={14} />Stop and save · {seconds}s</button>
                : <button type="button" className="button dark" disabled={phase === 'saving'} onClick={() => void start()}><Mic size={15} />{phase === 'saving' ? 'Saving…' : 'Record this script'}</button>}
            <button type="button" className="button subtle" disabled={index === state.scripts.length - 1 || phase !== 'idle'} onClick={() => setIndex(index + 1)}>Next<ArrowRight size={15} /></button>
        </div>
        {error && <p className="live-error" role="alert">{error}</p>}
        {done === state.scripts.length && <p className="live-success">All scripts recorded. Run <code>.venv/bin/python -m server.interview.evaluate</code> in the project folder.</p>}
    </div>;
}

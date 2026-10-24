import { useEffect, useRef, useState } from 'react';

// Live feedback while recording: time against the target, microphone level and long pauses.
// Runs on the open microphone stream in the browser; nothing extra is recorded or sent.
const SPEAKING_DB = -45;      // Louder than this counts as speech.
const QUIET_DB = -38;         // Speech that stays below this for a while is too quiet.
const LONG_PAUSE_SECONDS = 3;

export default function LiveMeter({ stream, seconds, target }: { stream: MediaStream; seconds: number; target: number | null }) {
    const [level, setLevel] = useState(0);
    const [quiet, setQuiet] = useState(false);
    const [pause, setPause] = useState(0);
    const lastVoice = useRef(performance.now());
    const [heard, setHeard] = useState(false);
    const quietSince = useRef<number | null>(null);
    useEffect(() => {
        const context = new AudioContext();
        const analyser = context.createAnalyser();
        analyser.fftSize = 1024;
        context.createMediaStreamSource(stream).connect(analyser);
        const samples = new Float32Array(analyser.fftSize);
        let frame = 0;
        let smoothed = -90;
        const tick = () => {
            analyser.getFloatTimeDomainData(samples);
            const rms = Math.sqrt(samples.reduce((sum, v) => sum + v * v, 0) / samples.length);
            const db = rms > 0 ? 20 * Math.log10(rms) : -90;
            smoothed = Math.max(db, smoothed * 0.85 + db * 0.15);
            const now = performance.now();
            if (db > SPEAKING_DB) { lastVoice.current = now; setHeard(true); }
            if (db > SPEAKING_DB && db < QUIET_DB) quietSince.current ??= now; else if (db >= QUIET_DB) quietSince.current = null;
            setLevel(Math.round(Math.max(0, Math.min(100, (smoothed + 60) / 50 * 100))));
            setQuiet(quietSince.current !== null && now - quietSince.current > 1500);
            setPause((now - lastVoice.current) / 1000);
            frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
        return () => { cancelAnimationFrame(frame); void context.close(); };
    }, [stream]);

    const share = target ? seconds / target : 0;
    const timeTone = !target ? 'good' : share > 1.4 ? 'poor' : share > 1 ? 'fair' : 'good';
    const hint = !heard ? (seconds > 3 ? 'Nothing heard yet. Check your microphone, or start speaking.' : 'Listening…')
        : pause >= LONG_PAUSE_SECONDS ? `Long pause (${Math.floor(pause)} s). Pick up the next point.`
        : quiet ? 'A little quiet. Move closer to the microphone or speak up.'
        : target && share > 1.4 ? 'Well over time. Wrap up with your result.'
        : target && share > 1 ? 'Past the target. Start wrapping up.'
        : 'Sounding good.';
    const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
    return <div className="ic-meter" aria-live="polite">
        <div className={`ic-meter-row tone-${timeTone}`}>
            <span>Time</span>
            {/* The track spans 1.4x the target; the marker shows the target itself. */}
            <span className="ic-meter-track"><span style={{ width: `${Math.min(100, share / 1.4 * 100)}%` }} />{target && <i style={{ left: `${100 / 1.4}%` }} title="Target" />}</span>
            <strong>{clock(seconds)}{target ? ` / ${clock(target)}` : ''}</strong>
        </div>
        <div className={`ic-meter-row tone-${quiet ? 'fair' : level < 8 ? 'none' : 'good'}`}>
            <span>Volume</span>
            <span className="ic-meter-track ic-level"><span style={{ width: `${level}%` }} /></span>
            <strong>{quiet ? 'quiet' : level < 8 ? '–' : 'good'}</strong>
        </div>
        <p className="ic-meter-hint">{hint}</p>
    </div>;
}

// Reading questions and example answers aloud, and the user's voice and recognition choices.
// The natural voice is Piper, run by the server on this computer; the browser's own voice is the fallback.
// Browser voice works around two Chrome quirks: an utterance queued right after cancel() can be
// dropped, and an unreferenced utterance can be garbage-collected mid-speech.

export type SpeechState = 'speaking' | 'idle' | 'failed';
export type SpeechSettings = {
    voice: { id: string; label: string; available: boolean };
    recognition: { options: { id: string; label: string; installed: boolean }[]; default: string };
};
export type VoiceChoice = 'natural' | 'browser';
const PREFERRED = /Samantha|Daniel|Karen|Moira|Google US English|Google UK English|Microsoft (Aria|Jenny|Guy|Zira|David)/;
const STORAGE_KEY = 'proofcv.interview.speech';
let current: SpeechSynthesisUtterance | null = null;
let playing: HTMLAudioElement | null = null;
let loading: AbortController | null = null;
let listener: ((state: SpeechState) => void) | null = null; // The natural voice's caller, told when it is stopped.
let generation = 0; // Bumped on every stop, so a stopped request never falls back to the browser voice.
let workspace = '';
let settings: SpeechSettings | null = null;
let choice: { voice: VoiceChoice; recognition: string | null } = { voice: 'natural', recognition: null };
try { choice = { ...choice, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') }; } catch { /* Storage unavailable: use the defaults. */ }

export function configureSpeech(workspaceId: string, available: SpeechSettings) {
    workspace = workspaceId;
    settings = available;
}

export function speechChoice() {
    const installed = settings?.recognition.options.filter(o => o.installed).map(o => o.id) || [];
    return {
        voice: settings?.voice.available && choice.voice === 'natural' ? 'natural' as const : 'browser' as const,
        recognition: choice.recognition && installed.includes(choice.recognition) ? choice.recognition : settings?.recognition.default ?? null,
    };
}

export function setSpeechChoice(update: Partial<typeof choice>) {
    choice = { ...choice, ...update };
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(choice)); } catch { /* Not remembered, still applied. */ }
}

function englishVoice() {
    const voices = window.speechSynthesis.getVoices().filter(v => v.lang.toLowerCase().startsWith('en'));
    return voices.find(v => v.default) || voices.find(v => PREFERRED.test(v.name)) || voices[0] || null;
}

export function stopSpeaking() {
    generation += 1;
    loading?.abort();
    loading = null;
    if (playing) { playing.pause(); URL.revokeObjectURL(playing.src); playing = null; }
    const stopped = listener;
    listener = null;
    stopped?.('idle');
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    current = null;
}

export function speak(text: string, onState: (state: SpeechState) => void = () => undefined) {
    stopSpeaking();
    if (!text.trim()) { onState('failed'); return; }
    if (speechChoice().voice === 'natural') void speakNatural(text, onState);
    else speakBrowser(text, onState);
}

async function speakNatural(text: string, onState: (state: SpeechState) => void) {
    const request = new AbortController();
    const mine = generation;
    loading = request;
    listener = onState;
    onState('speaking'); // Show the stop button while the voice is generated (about 0.3 s).
    try {
        const response = await fetch(`/api/interview/${workspace}/speak`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }), signal: request.signal });
        if (!response.ok) throw new Error('Voice unavailable');
        const url = URL.createObjectURL(await response.blob());
        if (mine !== generation) { URL.revokeObjectURL(url); return; }
        loading = null;
        const audio = new Audio(url);
        playing = audio;
        const finish = (state: SpeechState) => { if (playing !== audio) return; URL.revokeObjectURL(url); playing = null; listener = null; onState(state); };
        audio.onended = () => finish('idle');
        audio.onerror = () => finish('failed');
        await audio.play();
    } catch {
        if (mine !== generation) return;
        if (playing) { URL.revokeObjectURL(playing.src); playing = null; }
        loading = null;
        listener = null;
        speakBrowser(text, onState); // The server voice failed: fall back to the browser's own voice.
    }
}

function speakBrowser(text: string, onState: (state: SpeechState) => void) {
    if (!('speechSynthesis' in window)) { onState('failed'); return; }
    const synth = window.speechSynthesis;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    const voice = englishVoice();
    if (voice) utterance.voice = voice;
    let started = false;
    utterance.onstart = () => { started = true; onState('speaking'); };
    utterance.onend = () => { if (current === utterance) current = null; onState('idle'); };
    utterance.onerror = event => { if (current === utterance) current = null; onState(event.error === 'interrupted' || event.error === 'canceled' ? 'idle' : 'failed'); };
    current = utterance;
    window.setTimeout(() => {
        synth.resume();
        synth.speak(utterance);
    }, 120);
    window.setTimeout(() => { if (!started && current === utterance) { stopSpeaking(); onState('failed'); } }, 3000);
}

// Browser text-to-speech for reading questions and example answers aloud.
// Works around two Chrome quirks: an utterance queued right after cancel() can be
// dropped, and an unreferenced utterance can be garbage-collected mid-speech.

export type SpeechState = 'speaking' | 'idle' | 'failed';
const PREFERRED = /Samantha|Daniel|Karen|Moira|Google US English|Google UK English|Microsoft (Aria|Jenny|Guy|Zira|David)/;
let current: SpeechSynthesisUtterance | null = null;

function englishVoice() {
    const voices = window.speechSynthesis.getVoices().filter(v => v.lang.toLowerCase().startsWith('en'));
    return voices.find(v => v.default) || voices.find(v => PREFERRED.test(v.name)) || voices[0] || null;
}

export function stopSpeaking() {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    current = null;
}

export function speak(text: string, onState: (state: SpeechState) => void = () => undefined) {
    if (!('speechSynthesis' in window) || !text.trim()) {
        onState('failed');
        return;
    }
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

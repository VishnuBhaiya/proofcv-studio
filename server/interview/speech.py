"""Spoken answers: local Whisper transcription and delivery checks.

Whisper (faster-whisper, base.en, int8 on CPU) turns the recorded audio into
text with word timings. Delivery is then measured from those timings with
plain rules, not a model: speaking pace, pauses, filler words and length.
Audio is processed in memory and never saved.
"""
import io
import re
import threading

WHISPER_MODEL = 'base.en'
# Whisper tends to drop disfluencies; a prompt that contains them makes it keep "um" and "uh".
FILLER_PROMPT = 'Umm, let me think, uh, like, hmm. Okay, so, um, here is what I, uh, did.'
FILLERS = {'um', 'umm', 'uh', 'uhh', 'er', 'erm', 'ah', 'hmm', 'mm'}
FILLER_PHRASES = (('you', 'know'), ('i', 'mean'), ('sort', 'of'), ('kind', 'of'))
# Whisper can invent words after silence; those come with ~1% confidence. Real words,
# fillers included, scored above 30% in testing.
MIN_WORD_PROBABILITY = 0.1
PAUSE_SECONDS, LONG_PAUSE_SECONDS = 1.0, 2.5
SLOW_WPM, FAST_WPM = 110, 170
FILLERS_PER_MINUTE_LIMIT = 6


SAMPLE_RATE = 16000


def decode_audio(audio):
    """Recorded bytes -> 16 kHz mono float32 samples.

    Decoded here rather than by faster-whisper, whose decoder passes an option
    that PyAV 17+ no longer accepts.
    """
    import av
    import numpy as np
    resampler = av.AudioResampler(format='s16', layout='mono', rate=SAMPLE_RATE)
    chunks = []
    with av.open(io.BytesIO(audio), mode='r') as container:
        for frame in container.decode(audio=0):
            frame.pts = None
            chunks += [f.to_ndarray().reshape(-1) for f in resampler.resample(frame)]
        chunks += [f.to_ndarray().reshape(-1) for f in resampler.resample(None)]
    if not chunks:
        raise ValueError('The recording contains no audio.')
    return np.concatenate(chunks).astype(np.float32) / 32768.0


class WhisperTranscriber:
    def __init__(self, model_name=WHISPER_MODEL):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            try:
                self._model = WhisperModel(self.model_name, device='cpu', compute_type='int8', local_files_only=True)
            except Exception:
                # First run on a new machine: download the model once, like MiniLM.
                self._model = WhisperModel(self.model_name, device='cpu', compute_type='int8')
        return self._model

    def transcribe(self, audio):
        """Text and word timings for recorded audio bytes (webm, mp4, wav and other common formats)."""
        samples = decode_audio(audio)
        with self._lock:
            segments, info = self._load().transcribe(samples, language='en', word_timestamps=True,
                                                     vad_filter=True, initial_prompt=FILLER_PROMPT, condition_on_previous_text=False)
            words = [{'word': w.word.strip(), 'start': round(float(w.start), 2), 'end': round(float(w.end), 2), 'probability': round(float(w.probability), 3)}
                     for segment in segments for w in (segment.words or []) if w.probability >= MIN_WORD_PROBABILITY]
        return {'text': ' '.join(w['word'] for w in words).strip(), 'words': words, 'duration': round(float(info.duration), 2), 'model': f'whisper-{self.model_name}'}


_transcriber = None


def transcriber():
    global _transcriber
    if _transcriber is None:
        _transcriber = WhisperTranscriber()
    return _transcriber


def plain(word):
    return re.sub(r"[^a-z']", '', word.lower())


def find_fillers(words):
    """Filler words with their times. 'like' counts only when set off by commas, as in 'it was, like, slow'."""
    found = []
    tokens = [plain(w['word']) for w in words]
    for i, w in enumerate(words):
        token = tokens[i]
        if token in FILLERS:
            found.append({'word': token, 'start': w['start']})
        elif token == 'like' and (w['word'].endswith(',') or (i and words[i - 1]['word'].endswith(','))):
            found.append({'word': 'like', 'start': w['start']})
        elif i and (tokens[i - 1], token) in FILLER_PHRASES:
            found.append({'word': f'{tokens[i - 1]} {token}', 'start': words[i - 1]['start']})
    return found


def delivery(words, duration, target_seconds=None):
    """Pace, pauses, fillers and length from Whisper word timings, with plain-language notes."""
    if not words:
        return {'word_count': 0, 'speaking_seconds': 0, 'words_per_minute': 0, 'pauses': [], 'long_pauses': 0,
                'fillers': [], 'fillers_per_minute': 0, 'thinking_seconds': round(duration, 1), 'duration': round(duration, 1),
                'notes': ['No speech was detected. Check your microphone and try again.']}
    speaking = max(words[-1]['end'] - words[0]['start'], 0.1)
    minutes = speaking / 60
    pauses = [{'after': words[i - 1]['word'], 'seconds': round(words[i]['start'] - words[i - 1]['end'], 1)}
              for i in range(1, len(words)) if words[i]['start'] - words[i - 1]['end'] >= PAUSE_SECONDS]
    fillers = find_fillers(words)
    content_words = len(words) - len(fillers)
    wpm = round(content_words / minutes)
    long_pauses = sum(p['seconds'] >= LONG_PAUSE_SECONDS for p in pauses)
    fillers_per_minute = round(len(fillers) / minutes, 1)
    notes = []
    if wpm < SLOW_WPM:
        notes.append(f'Your pace was {wpm} words per minute, a little slow. Aim for about 120 to 160.')
    elif wpm > FAST_WPM:
        notes.append(f'Your pace was {wpm} words per minute, quite fast. Slow down slightly so key points land.')
    else:
        notes.append(f'Good pace: {wpm} words per minute.')
    if fillers_per_minute > FILLERS_PER_MINUTE_LIMIT:
        notes.append(f'{len(fillers)} filler words ({fillers_per_minute} per minute). A short silent pause sounds more confident than "um".')
    if long_pauses:
        notes.append(f'{long_pauses} long pause{"s" if long_pauses > 1 else ""} of {LONG_PAUSE_SECONDS:g} seconds or more. Plan your answer\'s structure before you start.')
    if target_seconds:
        if speaking < 0.6 * target_seconds:
            notes.append(f'You spoke for {round(speaking)} seconds; the target is about {target_seconds}. Add more detail.')
        elif speaking > 1.4 * target_seconds:
            notes.append(f'You spoke for {round(speaking)} seconds; the target is about {target_seconds}. Tighten it up.')
    return {'word_count': content_words, 'speaking_seconds': round(speaking, 1), 'words_per_minute': wpm, 'pauses': pauses,
            'long_pauses': long_pauses, 'fillers': fillers, 'fillers_per_minute': fillers_per_minute,
            'thinking_seconds': round(words[0]['start'], 1), 'duration': round(duration, 1), 'notes': notes}

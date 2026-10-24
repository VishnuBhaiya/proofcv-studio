"""Natural read-aloud voice: Piper (en_US "lessac", medium quality) on this computer.

Piper is a small neural text-to-speech model run with ONNX Runtime; a sentence takes
about 0.3 s on a laptop CPU. The voice file lives in runtime/models/piper (not
committed). When it is missing the app falls back to the browser's own voice.
"""
import io
import threading
import wave
from collections import OrderedDict
from pathlib import Path

VOICE = 'en_US-lessac-medium'
VOICE_LABEL = 'Natural (Piper, US English)'
MAX_CHARACTERS = 3000
CACHE_SIZE = 64


def model_path(runtime_dir):
    return Path(runtime_dir) / 'models' / 'piper' / f'{VOICE}.onnx'


class Speaker:
    def __init__(self, path):
        self.path = Path(path)
        self._voice = None
        self._lock = threading.Lock()
        self._cache = OrderedDict()

    def _load(self):
        if self._voice is None:
            from piper import PiperVoice
            self._voice = PiperVoice.load(self.path)
        return self._voice

    def wav(self, text):
        """WAV bytes for the text. Recent texts are cached: questions are often played twice."""
        text = ' '.join((text or '').split())
        if not text:
            raise ValueError('Nothing to read aloud.')
        if len(text) > MAX_CHARACTERS:
            raise ValueError('Text is too long to read aloud.')
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                return self._cache[text]
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as output:
                self._load().synthesize_wav(text, output)
            self._cache[text] = buffer.getvalue()
            if len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
            return self._cache[text]


_speakers = {}


def available(runtime_dir):
    if not model_path(runtime_dir).is_file():
        return False
    try:
        import piper  # noqa: F401
    except ImportError:
        return False
    return True


def speaker(runtime_dir):
    """The shared speaker, or None when Piper or its voice file is not installed."""
    path = model_path(runtime_dir)
    if not available(runtime_dir):
        return None
    if path not in _speakers:
        _speakers[path] = Speaker(path)
    return _speakers[path]

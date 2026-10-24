"""Read-aloud voice and recognition choice, without Piper or Whisper."""
import io
import tempfile
import unittest
import wave
from unittest import mock

from . import speech, voice


class FakePiper:
    calls = 0

    def synthesize_wav(self, text, output):
        FakePiper.calls += 1
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(22050)
        output.writeframes(b'\0\0' * len(text))


class SpeakerTests(unittest.TestCase):
    def setUp(self):
        self.speaker = voice.Speaker('unused.onnx')
        self.speaker._voice = FakePiper()
        FakePiper.calls = 0

    def test_returns_a_wav_and_caches_repeats(self):
        audio = self.speaker.wav('Tell me  about\nyourself.')
        with wave.open(io.BytesIO(audio)) as heard:
            self.assertEqual((heard.getframerate(), heard.getnframes()), (22050, len('Tell me about yourself.')))
        self.assertEqual(self.speaker.wav('Tell me about yourself.'), audio)
        self.assertEqual(FakePiper.calls, 1)

    def test_rejects_empty_and_very_long_text(self):
        for text in ('', '   ', None, 'x' * (voice.MAX_CHARACTERS + 1)):
            with self.assertRaises(ValueError):
                self.speaker.wav(text)

    def test_missing_voice_file_means_browser_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(voice.available(folder))
            self.assertIsNone(voice.speaker(folder))


class RecognitionTests(unittest.TestCase):
    def test_best_installed_model_is_the_default(self):
        with mock.patch.object(speech, 'installed', side_effect=lambda name: True):
            self.assertEqual(speech.recognition_options()['default'], 'small.en')
        with mock.patch.object(speech, 'installed', side_effect=lambda name: False):
            options = speech.recognition_options()
            self.assertEqual(options['default'], 'base.en')  # The original model always counts as installed.
            self.assertEqual([o['installed'] for o in options['options']], [False, True])

    def test_unknown_model_is_refused(self):
        with self.assertRaises(ValueError):
            speech.transcriber('large-v3')


if __name__ == '__main__':
    unittest.main()

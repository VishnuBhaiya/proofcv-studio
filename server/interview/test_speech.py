"""Delivery checks and audio decoding without the Whisper model."""
import io
import math
import struct
import unittest
import wave

from .speech import decode_audio, delivery, find_fillers


def words(text, start=0.0, gap=0.0, step=0.4):
    """Word timings for a sentence: each word lasts step seconds, separated by gap."""
    out, t = [], start
    for token in text.split():
        out.append({'word': token, 'start': round(t, 2), 'end': round(t + step, 2), 'probability': 0.9})
        t += step + gap
    return out


class FillerTests(unittest.TestCase):
    def test_fillers_and_phrases_are_found(self):
        found = [f['word'] for f in find_fillers(words('So um I built it, you know, with uh PyTorch'))]
        self.assertEqual(found, ['um', 'you know', 'uh'])

    def test_like_counts_only_when_set_off_by_commas(self):
        self.assertEqual([f['word'] for f in find_fillers(words('It was, like, slow'))], ['like'])
        self.assertEqual(find_fillers(words('I would like to explain')), [])


class DeliveryTests(unittest.TestCase):
    def test_good_pace_has_no_warnings(self):
        result = delivery(words(' '.join(['word'] * 60), step=0.4), 24.5, 25)
        self.assertEqual(result['words_per_minute'], 150)
        self.assertEqual(result['notes'], ['Good pace: 150 words per minute.'])

    def test_slow_and_fast_pace_are_flagged(self):
        self.assertIn('slow', delivery(words(' '.join(['word'] * 20), step=0.8), 16)['notes'][0])
        self.assertIn('fast', delivery(words(' '.join(['word'] * 60), step=0.25), 15)['notes'][0])

    def test_pauses_and_long_pauses(self):
        timed = words('first part') + words('second part', start=4.0)
        result = delivery(timed, 5)
        self.assertEqual(result['pauses'], [{'after': 'part', 'seconds': 3.2}])
        self.assertEqual(result['long_pauses'], 1)
        self.assertTrue(any('long pause' in note for note in result['notes']))

    def test_many_fillers_are_flagged_and_not_counted_as_words(self):
        result = delivery(words('um I uh built um a uh model um today'), 4)
        self.assertEqual((result['word_count'], len(result['fillers'])), (5, 5))
        self.assertTrue(any('filler words' in note for note in result['notes']))

    def test_length_is_compared_with_the_target(self):
        short = delivery(words(' '.join(['word'] * 50), step=0.4), 20, 90)
        self.assertTrue(any('Add more detail' in note for note in short['notes']))
        long = delivery(words(' '.join(['word'] * 150), step=0.4), 60, 30)
        self.assertTrue(any('Tighten it up' in note for note in long['notes']))

    def test_silence_gives_a_microphone_hint(self):
        self.assertIn('No speech', delivery([], 3.0)['notes'][0])


class DecodeTests(unittest.TestCase):
    def test_wav_is_resampled_to_16k_mono(self):
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as file:
            file.setnchannels(2); file.setsampwidth(2); file.setframerate(44100)
            file.writeframes(b''.join(struct.pack('<hh', s, s) for s in (int(8000 * math.sin(i / 20)) for i in range(44100))))
        samples = decode_audio(buffer.getvalue())
        self.assertAlmostEqual(len(samples) / 16000, 1.0, delta=0.05)
        self.assertLessEqual(float(abs(samples).max()), 1.0)

    def test_non_audio_is_rejected(self):
        with self.assertRaises(Exception):
            decode_audio(b'not audio at all')


if __name__ == '__main__':
    unittest.main()

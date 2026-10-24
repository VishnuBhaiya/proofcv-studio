"""Evaluation scripts and metrics, without Whisper or MiniLM."""
import tempfile
import unittest
from pathlib import Path

from .evaluate import lengths, load_scripts, normalise, overlap, problems, recorded, save_sample, star_accuracy, wer, word_errors
from .questions import load_bank


class ScriptTests(unittest.TestCase):
    def test_scripts_are_labelled_and_point_at_real_questions(self):
        scripts = load_scripts()
        bank = {q['id']: q for q in load_bank()['questions']}
        for script in scripts['scripts']:
            self.assertIn(script['question_id'], bank)
            if script['question_id'].startswith('bh-'):
                self.assertEqual({label for label, _ in script['sentences']}, {'situation', 'task', 'action', 'result'})
            if 'covers' in script:
                self.assertTrue(all(0 <= i < len(bank[script['question_id']]['key_points']) for i in script['covers']))

    def test_scripts_are_not_in_the_star_training_data(self):
        from .star import load_dataset
        training = {text for story in load_dataset()['stories'] for _, text in story['sentences']}
        self.assertFalse([t for s in load_scripts()['scripts'] for _, t in s['sentences'] if t in training])


class MetricTests(unittest.TestCase):
    def test_normalise_numbers_percent_and_punctuation(self):
        self.assertEqual(normalise('Accuracy went from sixty to over ninety percent.'), ['accuracy', 'went', 'from', '60', 'to', 'over', '90', 'percent'])
        self.assertEqual(normalise('It went from 60 to 90%!'), ['it', 'went', 'from', '60', 'to', '90', 'percent'])
        self.assertEqual(normalise("Two hundred, I'm sure; a few thousand rows"), ['200', "i'm", 'sure', 'a', 'few', 'thousand', 'rows'])

    def test_word_errors_and_wer(self):
        self.assertEqual(word_errors(['a', 'b', 'c'], ['a', 'x', 'c', 'd']), 2)
        self.assertEqual(wer('Hi, I am Tirth Patel.', 'hi i am faith patel'), (1, 5))
        self.assertEqual(wer('Hello there', 'hello there'), (0, 2))

    def test_overlap(self):
        self.assertEqual(overlap('the cat sat', 'the cat'), 2 / 3)

    def test_star_accuracy_aligns_whisper_sentences_to_the_script(self):
        class Labeller:
            def predict(self, sentences, backend):
                return [{'label': 'result' if 'improved' in s.lower() else 'action'} for s in sentences]
        script = {'sentences': [['action', 'I fixed the search.'], ['result', 'Accuracy improved a lot.']]}
        result = star_accuracy(script, 'I fixed the search. Accuracy improved a lot.', Labeller(), None)
        self.assertEqual((result['text_correct'], result['heard_correct'], result['heard_total']), (2, 2, 2))
        self.assertFalse(result['all_four_found'])


class SampleTests(unittest.TestCase):
    def test_samples_are_saved_per_script_and_replaced(self):
        scripts = load_scripts()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'samples'
            save_sample(folder, 'e01', b'one', scripts)
            save_sample(folder, 'e01', b'two', scripts)
            self.assertEqual(recorded(folder), ['e01'])
            self.assertEqual((folder / 'e01.webm').read_bytes(), b'two')
            with self.assertRaises(ValueError):
                save_sample(folder, '../escape', b'x', scripts)

    def test_missing_and_short_recordings_are_reported(self):
        scripts = {'scripts': [{'id': 'e01'}, {'id': 'e02'}, {'id': 'e03'}]}
        self.assertEqual(problems(scripts, {'e01': 12.5, 'e02': 1.0}), (['e03'], ['e02']))
        with tempfile.TemporaryDirectory() as directory:
            save_sample(Path(directory), 'e01', b'not audio', load_scripts())
            self.assertEqual(lengths(directory), {'e01': 0.0})


if __name__ == '__main__':
    unittest.main()

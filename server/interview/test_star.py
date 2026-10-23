"""STAR dataset, shipped model and coaching rules, without MiniLM."""
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import numpy as np

from .star import DATA_DIR, STAR, StarClassifier, analyse, load_dataset, position, split_sentences
from .train_star import keyword_baseline

LABELS = ['action', 'other', 'result', 'situation', 'task']


class KeywordBackend:
    """Maps a sentence to a one-hot vector by the first marker word it contains."""
    name = 'test-keywords'
    MARKERS = ('i built', 'that\'s it', 'improved', 'in my', 'my goal')

    def encode(self, texts):
        out = np.zeros((len(texts), len(self.MARKERS)))
        for row, text in enumerate(texts):
            for column, marker in enumerate(self.MARKERS):
                if marker in text.lower():
                    out[row, column] = 1.0
                    break
        return out


def fake_model(directory):
    """A classifier whose weights map each marker column straight to one label."""
    path = Path(directory) / 'model.json'
    path.write_text(json.dumps({'labels': LABELS, 'embedding_model': 'test', 'use_position': False, 'C': 1, 'trained_on': {},
                                'coef': (np.eye(5) * 10).tolist(), 'intercept': [0] * 5}), encoding='utf-8')
    return StarClassifier(path)


class DatasetTests(unittest.TestCase):
    def test_dataset_has_enough_examples_of_every_label(self):
        data = load_dataset()
        counts = Counter(label for story in data['stories'] for label, _ in story['sentences'])
        self.assertEqual(set(counts), set(data['labels']))
        self.assertTrue(all(n >= 30 for n in counts.values()), counts)
        self.assertEqual(len({s['id'] for s in data['stories']}), len(data['stories']))

    def test_shipped_model_matches_its_features(self):
        model = json.loads((DATA_DIR / 'star_model.json').read_text(encoding='utf-8'))
        self.assertEqual(model['labels'], sorted(load_dataset()['labels']))
        width = 384 + (1 if model['use_position'] else 0)
        self.assertEqual(np.asarray(model['coef']).shape, (5, width))
        self.assertEqual(len(model['intercept']), 5)

    def test_evaluation_report_beats_both_baselines(self):
        report = json.loads((DATA_DIR / 'star_evaluation.json').read_text(encoding='utf-8'))['test']
        self.assertGreater(report['classifier']['macro_f1'], report['baseline_keyword_rules']['macro_f1'])
        self.assertGreater(report['classifier']['macro_f1'], report['baseline_majority']['macro_f1'])


class HelperTests(unittest.TestCase):
    def test_position_and_sentence_splitting(self):
        self.assertEqual([position(i, 3) for i in range(3)], [0, 0.5, 1])
        self.assertEqual(position(0, 1), 0.5)
        self.assertEqual(split_sentences('I built it. Ok. Then it worked! Done?'), ['I built it.', 'Then it worked!'])

    def test_keyword_baseline(self):
        self.assertEqual(keyword_baseline('Recall improved to 78 percent.'), 'result')
        self.assertEqual(keyword_baseline('My job was to fix it.'), 'task')
        self.assertEqual(keyword_baseline('Um, let me think.'), 'other')


class AnalyseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.model = fake_model(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_complete_answer_gets_a_positive_note(self):
        result = analyse('In my internship a job kept failing. My goal was to fix it. I built a retry step. I built an alert too. Failures improved by 90 percent.', KeywordBackend(), self.model)
        self.assertEqual([s['label'] for s in result['sentences']], ['situation', 'task', 'action', 'action', 'result'])
        self.assertTrue(all(result['present'][label] for label in STAR))
        self.assertEqual(result['notes'], ['All four STAR parts are there, in a clear order.'])

    def test_missing_parts_and_unquantified_result_are_noted(self):
        result = analyse('In my course we had a project. I built the backend. It improved a lot.', KeywordBackend(), self.model)
        self.assertFalse(result['present']['task'])
        self.assertTrue(any('goal or responsibility' in n for n in result['notes']))
        self.assertTrue(any('no number' in n for n in result['notes']))

    def test_we_instead_of_i_and_too_much_filler(self):
        result = analyse('That\'s it, honestly. That\'s it, really. I built it so we could ship and we met and we tested. Results improved 5 percent.', KeywordBackend(), self.model)
        self.assertTrue(any('"we"' in n for n in result['notes']))
        self.assertTrue(any('filler' in n for n in result['notes']))

    def test_empty_transcript(self):
        self.assertIn('Not enough speech', analyse('Um.', KeywordBackend(), self.model)['notes'][0])


if __name__ == '__main__':
    unittest.main()

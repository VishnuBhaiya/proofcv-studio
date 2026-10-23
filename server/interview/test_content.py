"""Key-point coverage and fact checking with a small inspectable backend; no MiniLM."""
import unittest

import numpy as np

from .content import normalise, score, terms, windows
from .factcheck import check, numbers


class TopicBackend:
    """One dimension per topic word, so similarity means 'talks about the same topic'."""
    name = 'test-topics'
    TOPICS = ('precision', 'recall', 'iou', 'docker', 'yolo', 'warehouse', 'cafe', 'kubernetes')

    def encode(self, texts):
        out = np.zeros((len(texts), len(self.TOPICS) + 1))
        for row, text in enumerate(texts):
            for column, topic in enumerate(self.TOPICS):
                out[row, column] = topic in text.lower()
            out[row, -1] = 0.01
            out[row] /= np.linalg.norm(out[row])
        return out


PROFILE = {'skills': ['Python', 'YOLO'], 'projects': [{'title': 'Warehouse Safety', 'description': 'Tracked people in warehouse video with YOLO. Processed two hundred clips.', 'technologies': 'OpenCV'}],
           'education': 'Diploma of IT', 'experience': 'None', 'achievements': 'Peer mentor (2025).', 'summary_facts': []}


class ContentTests(unittest.TestCase):
    def test_windows_and_terms(self):
        self.assertEqual(terms('Per-class and per-condition error analysis'), ['per', 'class', 'condition', 'error', 'analysis'])
        chunks = windows(' '.join(f'w{i}' for i in range(30)) + '. Short sentence here.')
        self.assertIn(' '.join(f'w{i}' for i in range(14)), chunks)
        self.assertIn(' '.join(f'w{i}' for i in range(5, 19)), chunks)
        self.assertIn('Short sentence here.', chunks)

    def test_key_points_are_covered_partial_or_missed(self):
        result = score('I would report precision and recall. Then I would check the IoU of each box.',
                       ['Precision and recall', 'IoU threshold decides a correct detection', 'Docker image size'], TopicBackend())
        self.assertEqual([k['status'] for k in result['key_points']], ['covered', 'covered', 'missed'])
        self.assertIsNone(result['key_points'][2]['quote'])
        self.assertEqual(result['score'], 0.67)
        self.assertIn('Not mentioned: Docker image size.', result['notes'])

    def test_terms_alone_give_partial_credit(self):
        result = score('You should keep the image small and use fixed versions.', ['Docker image is small and versions pinned'], TopicBackend())
        self.assertEqual(result['key_points'][0]['status'], 'partial')

    def test_acronyms_match_their_spoken_form(self):
        self.assertEqual(normalise('IoU threshold'), 'IoU threshold (intersection over union)')
        self.assertEqual(normalise('use intersection over union'), 'use intersection over union (iou)')
        self.assertEqual(normalise('Precision and recall'), 'Precision and recall')
        result = score('A box counts if its intersection over union is high enough.', ['IoU threshold'], TopicBackend())
        self.assertIn('iou', result['key_points'][0]['terms_found'])

    def test_silence_scores_zero(self):
        self.assertEqual(score('', ['Precision and recall'], TopicBackend())['score'], 0.0)


class FactCheckTests(unittest.TestCase):
    def test_numbers_include_number_words(self):
        self.assertEqual(numbers('Processed two hundred clips in 2025, about 78.5%.'), {'200', '2025', '78.5'})
        self.assertEqual(numbers('seventy-eight percent of three thousand and five rows'), {'78', '3005'})

    def test_supported_claim_has_its_source(self):
        claim = check('I tracked people in warehouse video using YOLO.', PROFILE, TopicBackend())['claims'][0]
        self.assertEqual((claim['status'], claim['flags']), ('supported', []))
        self.assertEqual(claim['support']['label'], 'Project: Warehouse Safety')

    def test_unsupported_numbers_tools_and_leadership_are_flagged(self):
        profile = {**PROFILE, 'achievements': 'None'}
        result = check('I led a team of 6 on a cafe app. I deployed it with Kubernetes.', profile, TopicBackend())
        flags = [(f['type'], f['value']) for c in result['claims'] for f in c['flags']]
        self.assertIn(('number', '6'), flags)
        self.assertIn(('leadership', 'I led'), flags)
        self.assertIn(('tool', 'kubernetes'), flags)
        self.assertTrue(all(c['status'] == 'unmatched' for c in result['claims']))

    def test_mentoring_counts_as_leadership_evidence(self):
        flags = [f['type'] for c in check('I led the warehouse project.', PROFILE, TopicBackend())['claims'] for f in c['flags']]
        self.assertNotIn('leadership', flags)

    def test_numbers_without_i_count_only_in_personal_stories(self):
        sentence = 'Recall improved to 78% on the warehouse clips.'
        self.assertEqual(check(sentence, PROFILE, TopicBackend())['claims'][0]['flags'][0]['value'], '78%')
        self.assertEqual(check(sentence, PROFILE, TopicBackend(), personal_story=False)['claims'], [])

    def test_hypotheticals_are_not_claims(self):
        result = check("I would report precision and recall. I'd use YOLO. I'll check IoU. I used YOLO in the warehouse.", PROFILE, TopicBackend())
        self.assertEqual([c['text'] for c in result['claims']], ['I used YOLO in the warehouse.'])

    def test_greetings_and_thanks_are_not_claims(self):
        result = check("Hi, I'm Sam. Thank you for having me. I used YOLO in the warehouse.", PROFILE, TopicBackend())
        self.assertEqual([c['text'] for c in result['claims']], ['I used YOLO in the warehouse.'])

    def test_numbers_in_profile_are_not_flagged(self):
        claim = check('I processed 200 clips of warehouse video.', PROFILE, TopicBackend())['claims'][0]
        self.assertEqual(claim['flags'], [])


if __name__ == '__main__':
    unittest.main()

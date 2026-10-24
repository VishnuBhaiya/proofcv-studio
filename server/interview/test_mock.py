"""Mock interview selection, readiness scoring and report PDF."""
import re
import unittest

from .mock import band, components, pick, render_pdf, report

GOOD = {'words_per_minute': 140, 'fillers_per_minute': 1.0, 'long_pauses': 0, 'pace_gap': 0, 'length_gap': 10, 'star_parts': 4, 'flags': 0}
WEAK = {'words_per_minute': 90, 'fillers_per_minute': 9.0, 'long_pauses': 2, 'pace_gap': 30, 'length_gap': 80, 'star_parts': 1, 'flags': 1}


def question(qid, round_, **extra):
    return {'id': qid, 'round': round_, 'text': f'{qid}?', 'reason': 'r', **extra}


ROUNDS = {'self_introduction': [question('si-30', 'self_introduction', seconds=30), question('si-90', 'self_introduction', seconds=90)],
          'behavioural': [question(f'bh-{i}', 'behavioural') for i in range(5)],
          'technical': [question('tq-a', 'technical'), question('tq-b', 'technical')],
          'motivation_fit': [question('mf-why-role', 'motivation_fit'), question('mf-gap', 'motivation_fit')]}


class PickTests(unittest.TestCase):
    def test_five_questions_across_all_rounds(self):
        self.assertEqual([q['id'] for q in pick(ROUNDS)], ['si-90', 'bh-0', 'bh-2', 'tq-a', 'mf-gap'])

    def test_missing_rounds_are_skipped(self):
        self.assertEqual([q['id'] for q in pick({'behavioural': ROUNDS['behavioural'][:1]})], ['bh-0'])


class ScoreTests(unittest.TestCase):
    def test_good_delivery_cannot_rescue_an_answer_with_no_substance(self):
        from .mock import overall
        self.assertEqual(overall({'delivery': 100, 'length': 100, 'content': 0, 'honesty': 0}), 40)  # Was 50; this answer scored 97 before.
        self.assertEqual(overall({'delivery': 100, 'length': 100, 'honesty': 25}), 40)
        self.assertEqual(overall({'delivery': 90, 'length': 80, 'content': 100, 'honesty': 100}), 92)
        self.assertEqual(components({'words_per_minute': 140, 'fillers_per_minute': 0, 'long_pauses': 0, 'flags': 0, 'honesty': None}), {'delivery': 100})
        self.assertEqual(components({'words_per_minute': 140, 'fillers_per_minute': 0, 'long_pauses': 0, 'flags': 1})['honesty'], 75)  # Older attempts.

    def test_components(self):
        self.assertEqual(components(GOOD), {'delivery': 100, 'length': 90, 'structure': 100, 'honesty': 100})
        self.assertEqual(components(WEAK), {'delivery': 43, 'length': 20, 'structure': 25, 'honesty': 75})
        self.assertEqual(components({**GOOD, 'key_points': 0.6}), {'delivery': 100, 'length': 90, 'structure': 100, 'content': 60, 'honesty': 100})
        self.assertEqual(components({'words_per_minute': 0}), {'delivery': 0})

    def test_bands(self):
        self.assertEqual((band(85), band(70), band(40)), ('Ready', 'Nearly ready', 'Needs practice'))


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.session = {'id': 's1', 'created_at': '2026-10-23T10:00:00+00:00', 'job': {'document_id': 'j', 'title': 'AI Engineer'},
                        'questions': pick(ROUNDS), 'answers': {'0': 1, '1': 2}}
        self.attempts = {1: {'id': 1, 'transcript': 'good answer', 'summary': GOOD}, 2: {'id': 2, 'transcript': 'weak answer', 'summary': WEAK}}

    def test_report_averages_answered_questions_and_lists_next_steps(self):
        result = report(self.session, self.attempts)
        self.assertEqual((result['answered'], result['total']), (2, 5))
        self.assertEqual([q.get('score') for q in result['questions']], [98, 41, None, None, None])
        self.assertEqual((result['overall'], result['band']), (70, 'Incomplete'))
        self.assertTrue(any('Practise question 2 again' in s for s in result['next_steps']))
        self.assertTrue(any('skipped questions (3, 4, 5)' in s for s in result['next_steps']))

    def test_band_only_when_every_question_is_answered(self):
        full = {**self.session, 'answers': {str(i): 1 for i in range(5)}}
        self.assertEqual(report(full, self.attempts)['band'], 'Ready')

    def test_no_answers_is_an_error(self):
        with self.assertRaisesRegex(ValueError, 'at least one'):
            report({**self.session, 'answers': {}}, {})

    def test_pdf(self):
        pdf = render_pdf(report(self.session, self.attempts), 'Sam Lee')
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreaterEqual(len(re.findall(rb'/Type /Page\b', pdf)), 1)


if __name__ == '__main__':
    unittest.main()

"""Skill check: picking ten technical questions and finding weak and strong topics."""
import unittest

import numpy as np

from .diagnostic import COMPULSORY, QUESTION_COUNT, evaluate, level, pick


class WordBackend:
    """One dimension per topic word, so a question matches the requirements that share its topic."""
    WORDS = ('rag', 'vector', 'agent', 'docker', 'python', 'testing', 'sql', 'cloud', 'prompt', 'monitoring', 'git', 'statistics')

    def encode(self, texts):
        out = np.zeros((len(texts), len(self.WORDS) + 1))
        for row, text in enumerate(texts):
            for column, word in enumerate(self.WORDS):
                out[row, column] = word in text.lower()
            out[row, -1] = 0.05
            out[row] /= np.linalg.norm(out[row])
        return out


BANK = {'questions': [{'id': f'tq-{w}', 'round': 'technical', 'focus': f'{w} topic', 'text': f'Explain {w}.', 'key_points': ['a', 'b']} for w in WordBackend.WORDS]
        + [{'id': 'bh-x', 'round': 'behavioural', 'focus': 'rag teamwork', 'text': 'Teamwork?', 'key_points': []}]}
FIT = [{'id': 'r-rag', 'text': 'RAG pipelines', 'level': 'required', 'status': 'gap'},
       {'id': 'r-vector', 'text': 'Vector databases', 'level': 'preferred', 'status': 'gap'},
       {'id': 'r-agent', 'text': 'Agent workflows', 'level': 'required', 'status': 'partial'},
       {'id': 'r-python', 'text': 'Python', 'level': 'required', 'status': 'strong'},
       {'id': 'r-docker', 'text': 'Docker deployment', 'level': 'responsibility', 'status': 'gap'},
       {'id': 'r-testing', 'text': 'Testing practice', 'level': 'required', 'status': 'strong'},
       {'id': 'r-degree', 'text': "Bachelor's degree", 'level': 'required', 'status': 'verify'},
       {'id': 'r-prompt', 'text': 'Prompt engineering', 'level': 'preferred', 'status': 'gap'},
       {'id': 'r-cloud', 'text': 'Cloud platforms', 'level': 'preferred', 'status': 'gap'}]


class PickTests(unittest.TestCase):
    def setUp(self):
        self.picked = pick(BANK, FIT, ['r-prompt'], WordBackend())

    def test_ten_technical_questions_four_compulsory_first(self):
        self.assertEqual(len(self.picked), QUESTION_COUNT)
        self.assertEqual([q['compulsory'] for q in self.picked], [True] * COMPULSORY + [False] * (QUESTION_COUNT - COMPULSORY))
        self.assertTrue(all(q['round'] == 'technical' for q in self.picked))
        self.assertEqual(len({q['id'] for q in self.picked}), QUESTION_COUNT)

    def test_compulsory_cover_different_required_skills(self):
        compulsory = self.picked[:COMPULSORY]
        self.assertEqual({q['requirement']['id'] for q in compulsory}, {'r-rag', 'r-agent', 'r-python', 'r-testing'})
        self.assertTrue(all(q['requirement']['level'] == 'required' for q in compulsory))

    def test_skills_to_learn_get_a_question_and_degrees_never_do(self):
        prompt = next(q for q in self.picked if q['id'] == 'tq-prompt')
        self.assertTrue(prompt['learning'])
        self.assertEqual(self.picked.index(prompt), COMPULSORY)  # Right after the compulsory ones.
        self.assertNotIn('r-degree', {q['requirement']['id'] for q in self.picked})

    def test_no_requirements_means_no_questions(self):
        self.assertEqual(pick(BANK, [], [], WordBackend()), [])


def summary(key_points, wpm=140):
    return {'words_per_minute': wpm, 'fillers_per_minute': 0.0, 'long_pauses': 0, 'pace_gap': 0, 'length_gap': 0, 'key_points': key_points, 'flags': 0, 'honesty': None}


class EvaluateTests(unittest.TestCase):
    def test_levels_study_lists_and_unanswered_topics(self):
        questions = [{'id': f'tq-{i}', 'text': f'Q{i}', 'topic': f'topic {i}', 'compulsory': i < 2, 'requirement': {'id': f'r{i}', 'text': f'R{i}', 'level': 'required', 'status': 'gap'}}
                     for i in range(4)]
        session = {'questions': questions, 'finished_at': None, 'answers': {
            '0': {'id': 1, 'covered': ['a', 'b'], 'partial': [], 'missed': []},
            '1': {'id': 2, 'covered': [], 'partial': ['a'], 'missed': ['b']},
            '2': {'id': 3, 'covered': ['a'], 'partial': [], 'missed': ['b']}}}
        attempts = {1: {'summary': summary(1.0)}, 2: {'summary': summary(0.25)}, 3: {'summary': summary(0.5)}}
        result = evaluate(session, attempts, ['Prompt engineering'])
        self.assertEqual((result['answered'], result['total'], result['compulsory_done']), (3, 4, 2))
        self.assertEqual([t['topic'] for t in result['strong']], ['topic 0'])
        self.assertEqual([t['topic'] for t in result['developing']], ['topic 2'])
        self.assertEqual([(t['topic'], t['partial'], t['missed']) for t in result['weak']], [('topic 1', ['a'], ['b'])])
        self.assertEqual([t['topic'] for t in result['not_assessed']], ['topic 3'])
        self.assertEqual((result['knowledge'], result['learn_skills'], result['finished']), (58, ['Prompt engineering'], False))

    def test_level_thresholds(self):
        self.assertEqual([level(v) for v in (0.7, 0.69, 0.4, 0.39)], ['strong', 'developing', 'developing', 'weak'])


if __name__ == '__main__':
    unittest.main()

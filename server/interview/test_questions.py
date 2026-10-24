"""Question bank and picker with the offline inspectable embedding backend; no model downloads."""
import json
import tempfile
import unittest
from pathlib import Path

from ..retrieval import InspectableHashEmbeddingBackend
from .fit import job_fit, load_requirements
from .questions import BANK_PATH, ROUNDS, load_bank, pick_questions
from .test_fit import JOBS, PROFILE


def pick(job_id, profile=PROFILE):
    job = next(j for j in JOBS if j['document_id'] == job_id)
    requirements = load_requirements(JOBS)['jobs'][job_id]
    backend = InspectableHashEmbeddingBackend()
    fit = job_fit(job, requirements, profile, backend)
    keywords = {r['id']: r.get('keywords', []) for r in requirements}
    return fit, pick_questions(job, fit['requirements'], keywords, profile, load_bank(), backend)


class BankTests(unittest.TestCase):
    def test_bank_loads_with_every_round_and_key_points(self):
        bank = load_bank()
        self.assertEqual({q['round'] for q in bank['questions']}, set(ROUNDS))
        self.assertTrue(all(len(q['key_points']) >= 3 for q in bank['questions'] if q['round'] == 'technical'))

    def test_undeclared_slot_is_rejected(self):
        data = json.loads(BANK_PATH.read_text(encoding='utf-8'))
        data['questions'][3]['text'] = 'Tell me about {project} and {salary}.'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bank.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Slots'):
                load_bank(path)


class PickerTests(unittest.TestCase):
    def test_every_round_is_filled_and_no_slot_is_left_unfilled(self):
        _, result = pick('computer_vision_engineer')
        self.assertEqual(len(result['rounds']['self_introduction']), 3)
        self.assertEqual(len(result['rounds']['behavioural']), 5)
        self.assertTrue(1 <= len(result['rounds']['technical']) <= 5)
        self.assertTrue(result['rounds']['motivation_fit'])
        texts = [q['text'] for qs in result['rounds'].values() for q in qs]
        self.assertFalse([t for t in texts if '{' in t])
        self.assertTrue(all('AI Computer Vision Engineer' in q['text'] for q in result['rounds']['self_introduction']))

    def test_project_questions_use_the_users_own_project(self):
        _, result = pick('computer_vision_engineer')
        project = [q for q in result['rounds']['behavioural'] if q['id'].startswith('bh-project')]
        self.assertEqual(len(project), 2)
        self.assertTrue(all('Lane Detector' in q['text'] for q in project))

    def test_no_projects_means_no_project_questions(self):
        _, result = pick('computer_vision_engineer', {**PROFILE, 'projects': []})
        self.assertFalse([q for q in result['rounds']['behavioural'] if q['id'].startswith('bh-project')])
        self.assertEqual(len(result['rounds']['behavioural']), 5)

    def test_technical_questions_name_their_requirement_without_duplicates(self):
        fit, result = pick('computer_vision_engineer')
        technical = result['rounds']['technical']
        self.assertEqual(len({q['id'] for q in technical}), len(technical))
        statuses = {r['id']: r['status'] for r in fit['requirements']}
        for q in technical:
            self.assertEqual(q['requirement']['status'], statuses[q['requirement']['id']])
            self.assertIn(q['requirement']['text'], q['reason'])
        self.assertNotIn('key_points', json.dumps(result))

    def test_gap_and_eligibility_questions_quote_real_requirements(self):
        fit, result = pick('computer_vision_engineer')
        motivation = {q['id']: q for q in result['rounds']['motivation_fit']}
        gaps = {r['text'] for r in fit['requirements'] if r['status'] == 'gap'}
        for q in result['rounds']['motivation_fit']:
            if q['id'] == 'mf-gap':
                self.assertIn(q['requirement']['text'], gaps)
        self.assertIn('Three to five or more years', motivation['mf-eligibility']['text'])

    def test_picks_are_deterministic(self):
        self.assertEqual(pick('rag_agent_engineer')[1], pick('rag_agent_engineer')[1])



class TopicalTests(unittest.TestCase):
    def test_two_exact_tag_matches_make_a_question_on_topic(self):
        import numpy as np
        from .questions import topical
        requirements = [{'category': 'skill', 'keywords': ['rag', 'retrieval', 'embeddings']}, {'category': 'practice', 'keywords': ['model evaluation']},
                        {'category': 'soft', 'keywords': ['algorithms', 'collaborated']}]
        questions = [{'tags': ['rag', 'retrieval']}, {'tags': ['object detection', 'model evaluation']}, {'tags': ['algorithms', 'data structures']}, {'tags': []}]
        weak = np.full((4, 3), 0.2)  # All embed weakly, as short topic labels often do.
        weak[3] = 0.6  # Strong meaning match on every requirement.
        eligible, strength = topical(questions, requirements, weak)
        self.assertEqual(list(eligible), [True, False, False, True])  # One tag is not enough; soft-skill keywords do not count.
        self.assertGreater(strength[3], strength[0])


if __name__ == '__main__':
    unittest.main()

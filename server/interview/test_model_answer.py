"""Example answers and attempt tracking, without MiniLM."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import model_answer
from .attempts import AttemptStore, compare, needs_work, summarise
from .model_answer import build, clauses, first_person, lower_first, stories
from .test_content import TopicBackend

PROFILE = {'name': 'Sam Lee', 'skills': ['Python', 'YOLO'],
           'projects': [{'title': 'Warehouse Safety', 'description': 'Built a YOLO tracker for warehouse video. Measured recall on night clips.', 'technologies': 'OpenCV'}],
           'education': 'Diploma of IT', 'experience': 'Cafe Barista | Bean Bar | 2023 - 2024\nServed customers, trained new staff, handled the till and closed the shop.',
           'achievements': 'Finalist, Campus Expo (2025) - presented the Warehouse Safety tracker.', 'summary_facts': ['Computer-vision student who builds prototypes.']}
JOB = {'document_id': 'computer_vision_engineer', 'title': 'AI Computer Vision Engineer'}
FIT = [{'id': 'r1', 'text': 'Python and OpenCV', 'level': 'required', 'status': 'strong', 'evidence': []},
       {'id': 'r2', 'text': 'Video streaming and MLOps', 'level': 'preferred', 'status': 'gap', 'evidence': []},
       {'id': 'r3', 'text': 'Working with large datasets', 'level': 'required', 'status': 'gap', 'evidence': []}]


class TextTests(unittest.TestCase):
    def test_cv_style_becomes_first_person(self):
        self.assertEqual(first_person('Built a tracker.'), 'I built a tracker.')
        self.assertEqual(first_person('Uses Python daily.'), 'I use Python daily.')
        self.assertEqual(first_person('Teaches classes.'), 'I teach classes.')
        self.assertEqual(first_person('No real workers were filmed.'), 'No real workers were filmed.')

    def test_action_lists_split_only_when_every_piece_is_a_verb(self):
        self.assertEqual(clauses('Served customers, trained new staff, handled the till and closed the shop.'),
                         ['Served customers.', 'Trained new staff.', 'Handled the till and closed the shop.'])
        self.assertEqual(clauses('Added frame sampling, object tracking and event counts.'), ['Added frame sampling, object tracking and event counts.'])

    def test_lower_first_keeps_names(self):
        self.assertEqual(lower_first('Built it.'), 'built it.')
        self.assertEqual(lower_first('YOLO helped.'), 'YOLO helped.')
        self.assertEqual(lower_first('Artificial Intelligence student.'), 'Artificial Intelligence student.')

    def test_stories_cover_projects_and_roles(self):
        found = stories(PROFILE)
        self.assertEqual([s['source'] for s in found], ['Project: Warehouse Safety', 'Experience: Cafe Barista'])
        self.assertEqual(found[1]['as'], 'as Cafe Barista at Bean Bar')
        self.assertEqual(found[1]['sentences'][0], 'I served customers.')


class FakeStar:
    """Labels sentences that report a measurement as results and everything else as actions."""
    def predict(self, sentences, backend):
        return [{'label': 'result' if 'measured' in s.lower() else 'action', 'confidence': 0.9} for s in sentences]


class BuildTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(model_answer, 'classifier', return_value=FakeStar())
        patcher.start()
        self.addCleanup(patcher.stop)

    def build(self, question, text='', requirement=None):
        return build(question, text, PROFILE, FIT, JOB, TopicBackend(), None, requirement)

    def test_behavioural_uses_the_named_project_and_never_invents_a_task(self):
        result = self.build({'id': 'bh', 'round': 'behavioural'}, 'In your Warehouse Safety project, what was hardest?')
        labels = [(p['label'], p['placeholder']) for p in result['parts']]
        self.assertEqual(labels[0], ('Situation', False))
        self.assertIn(('Task', True), labels)
        self.assertTrue(result['parts'][0]['text'].startswith('In my Warehouse Safety project, I built a YOLO tracker'))
        self.assertTrue(any(p['text'].startswith('This led to: Finalist') for p in result['parts']))
        self.assertNotIn('[', result['text'])
        self.assertTrue(all(p['source'] for p in result['parts'] if not p['placeholder']))

    def test_no_projects_or_roles_gives_only_prompts(self):
        empty = {**PROFILE, 'projects': [], 'experience': 'None'}
        result = build({'id': 'bh', 'round': 'behavioural'}, 'Tell me about teamwork.', empty, FIT, JOB, TopicBackend())
        self.assertTrue(all(p['placeholder'] for p in result['parts']))
        self.assertEqual(result['text'], '')

    def test_technical_marks_missed_points_and_links_experience(self):
        question = {'id': 'tq', 'round': 'technical', 'focus': 'yolo tracking in warehouse video', 'key_points': ['Track objects', 'Count once']}
        result = build(question, '', PROFILE, FIT, JOB, TopicBackend(), {'key_points': [{'text': 'Track objects', 'status': 'covered'}, {'text': 'Count once', 'status': 'missed'}]})
        self.assertEqual([p['label'] for p in result['parts']], ['Key point', 'Key point you missed', 'Link to your experience'])
        self.assertIn('Warehouse Safety', result['parts'][-1]['text'])

    def test_intro_key_points_come_from_the_profile_and_job(self):
        short = model_answer.intro_points({'id': 'si-30', 'seconds': 30}, PROFILE, FIT, JOB, TopicBackend())
        self.assertEqual(short, ['your background as a computer-vision student', 'your Warehouse Safety project', 'why you want the AI Computer Vision Engineer role'])
        long = model_answer.intro_points({'id': 'si-90', 'seconds': 90}, PROFILE, FIT, JOB, TopicBackend())
        self.assertIn('your experience as Cafe Barista at Bean Bar', long)

    def test_introduction_grows_with_the_target_length(self):
        short = self.build({'id': 'si-30', 'round': 'self_introduction', 'seconds': 30})
        long = self.build({'id': 'si-120', 'round': 'self_introduction', 'seconds': 120})
        self.assertEqual(short['parts'][0]['text'], "Hi, I'm Sam.")
        self.assertNotIn('Experience', [p['label'] for p in short['parts']])
        self.assertIn('Experience', [p['label'] for p in long['parts']])
        self.assertIn('“Working with large datasets”', next(p['text'] for p in long['parts'] if p['label'] == 'Growth'))
        self.assertIn('“Python and OpenCV”', next(p['text'] for p in short['parts'] if p['label'] == 'Why this role'))

    def test_gap_answer_is_honest_and_asks_for_a_plan(self):
        result = self.build({'id': 'mf-gap', 'round': 'motivation_fit'}, requirement='r2')
        self.assertIn('“Video streaming and MLOps”', result['parts'][0]['text'])
        self.assertTrue(result['parts'][-1]['placeholder'])


class AttemptTests(unittest.TestCase):
    def response(self, fillers, parts, flags=0):
        return {'target_seconds': 90, 'delivery': {'words_per_minute': 140, 'fillers_per_minute': fillers, 'long_pauses': 0, 'speaking_seconds': 80},
                'star': {'present': {'situation': True, 'task': parts > 1, 'action': parts > 2, 'result': parts > 3}},
                'fact_check': {'claims': [{'status': 'supported', 'flags': [{}] * flags}], 'score': max(0, 100 - 25 * flags)}}

    def test_unsure_recognition_is_never_a_strong_answer(self):
        clean = {**summarise(self.response(1.0, 4)), 'unsure_share': 0.05}
        self.assertEqual(needs_work(clean), [])
        self.assertIn('not reliable', needs_work({**clean, 'unsure_share': 0.3})[0])

    def test_claims_the_profile_does_not_back_need_work(self):
        response = self.response(1.0, 4)
        response['fact_check'] = {'claims': [{'status': 'unmatched', 'flags': []}] * 4, 'score': 0}
        summary = summarise(response)
        self.assertEqual((summary['unmatched'], summary['honesty']), (4, 0))
        self.assertEqual(needs_work(summary), ['4 things you said about yourself are not in your confirmed profile.'])

    def test_summary_and_reasons(self):
        summary = summarise(self.response(8.0, 2, flags=1))
        self.assertEqual((summary['star_parts'], summary['flags'], summary['pace_gap'], summary['length_gap']), (2, 1, 0, 11))
        reasons = needs_work(summary)
        self.assertEqual(len(reasons), 3)
        self.assertEqual(needs_work(summarise(self.response(1.0, 4))), [])

    def test_compare_marks_better_worse_and_same(self):
        changes = {c['metric']: c['direction'] for c in compare(summarise(self.response(8.0, 2, 1)), summarise(self.response(2.0, 4, 2)))}
        self.assertEqual((changes['fillers_per_minute'], changes['star_parts'], changes['flags'], changes['long_pauses']), ('better', 'better', 'worse', 'same'))

    def test_store_numbers_attempts_per_question(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AttemptStore(Path(directory) / 'interview.sqlite3')
            first = store.record('w1', 'bh-teamwork', 'first try', summarise(self.response(8.0, 2)))
            second = store.record('w1', 'bh-teamwork', 'second try', summarise(self.response(2.0, 4)))
            other = store.record('w1', 'bh-conflict', 'other', summarise(self.response(2.0, 4)))
            self.assertEqual((first['attempt'], first['changes']), (1, []))
            self.assertEqual(second['attempt'], 2)
            self.assertIn('better', {c['direction'] for c in second['changes']})
            self.assertEqual(other['attempt'], 1)
            self.assertEqual([h['transcript'] for h in store.history('w1', 'bh-teamwork')], ['first try', 'second try'])


if __name__ == '__main__':
    unittest.main()

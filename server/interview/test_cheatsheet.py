"""Interview-day cheat sheet and its one-page PDF, without MiniLM."""
import re
import unittest
from unittest import mock

from . import model_answer, star
from .cheatsheet import best_attempts, build, reminders, render_pdf
from .test_content import TopicBackend
from .test_model_answer import FIT, JOB, PROFILE, FakeStar

STRONG_FIT = [{**FIT[0], 'evidence': [{'label': 'Skill', 'text': 'Python'}, {'label': 'Project: Warehouse Safety', 'text': 'Built a YOLO tracker for warehouse video.'}]},
              *FIT[1:], {'id': 'd1', 'text': 'Deploy models to edge devices.', 'level': 'responsibility', 'status': 'partial', 'evidence': []}]
QUESTIONS = {'bh-teamwork': {'id': 'bh-teamwork', 'text': 'Tell me about working in a team.'}, 'bh-failure': {'id': 'bh-failure', 'text': 'Tell me about a failure.'}}


def attempt(qid, transcript, **summary):
    base = {'words_per_minute': 140, 'fillers_per_minute': 0.0, 'long_pauses': 0, 'pace_gap': 0, 'length_gap': 0, 'length_ratio': 1.0, 'flags': 0}
    return {'id': 1, 'question_id': qid, 'created_at': '2026-10-24T00:00:00+00:00', 'transcript': transcript, 'summary': {**base, **summary}}


class CheatSheetTests(unittest.TestCase):
    def setUp(self):
        for target in (model_answer, star):
            patcher = mock.patch.object(target, 'classifier', return_value=FakeStar())
            patcher.start()
            self.addCleanup(patcher.stop)

    def build(self, attempts, readiness=None):
        return build(PROFILE, STRONG_FIT, JOB, attempts, QUESTIONS, TopicBackend(), readiness)

    def test_no_practice_falls_back_to_the_profile(self):
        sheet = self.build([])
        self.assertEqual(sheet['practised'], 0)
        self.assertTrue(sheet['introduction']['text'].startswith("Hi, I'm Sam."))
        self.assertIn('Built from your confirmed profile', sheet['introduction']['source'])
        self.assertEqual(sheet['stories'][0]['source'], 'Not practised yet: record it in Practice')
        self.assertIn('Practise a few answers first', sheet['reminders'][0])

    def test_strengths_prefer_project_evidence_over_a_skill_tag(self):
        sheet = self.build([])
        self.assertEqual(sheet['strengths'], [{'requirement': 'Python and OpenCV', 'evidence': 'Project: Warehouse Safety: Built a YOLO tracker for warehouse video.'}])

    def test_gaps_required_first_with_an_honest_answer(self):
        gaps = self.build([])['gaps']
        self.assertEqual([g['requirement'] for g in gaps], ['Working with large datasets', 'Video streaming and MLOps'])
        self.assertEqual(gaps[0]['answer'][0]['label'], 'Be honest')
        self.assertTrue(gaps[0]['answer'][-1]['placeholder'])

    def test_questions_to_ask_use_the_job_duties(self):
        asked = self.build([])['questions_to_ask']
        self.assertEqual(asked[0], 'What does “deploy models to edge devices” look like day to day in this team?')
        self.assertIn('AI Computer Vision Engineer', asked[1])

    def test_a_strong_practised_intro_is_used_as_said(self):
        mine = attempt('si-30', "Hi, I'm Sam and I build vision prototypes.")
        weak = attempt('si-30', 'Um hi.', length_ratio=0.2, length_gap=80)
        sheet = self.build([weak, mine])
        self.assertEqual(sheet['introduction']['text'], mine['transcript'])
        self.assertIn('Your own best', sheet['introduction']['source'])
        self.assertEqual(self.build([weak])['introduction']['source'][:10], 'Built from')

    def test_best_stories_are_the_highest_scoring_and_skip_follow_ups(self):
        high = attempt('bh-teamwork', 'I joined a team of four. I measured accuracy at 91%.', star_parts=4)
        low = attempt('bh-failure', 'I tried something.', star_parts=1)
        follow = attempt('bh-teamwork:follow-up', 'I measured it twice.', star_parts=4)
        stories = self.build([low, follow, high])['stories']
        self.assertEqual([s['question'] for s in stories], ['Tell me about working in a team.', 'Tell me about a failure.'])
        self.assertGreater(stories[0]['score'], stories[1]['score'])
        self.assertEqual(stories[0]['parts'], [['Action', 'I joined a team of four.'], ['Result', 'I measured accuracy at 91%.']])
        self.assertEqual([a['question_id'] for a in best_attempts([low, follow, high], 'bh-')], ['bh-teamwork', 'bh-failure'])

    def test_reminders_come_from_delivery_numbers(self):
        tips = reminders([attempt('si-30', 'a', words_per_minute=180, fillers_per_minute=4.0, length_ratio=0.5, long_pauses=2, flags=1),
                          attempt('si-90', 'b', words_per_minute=170, fillers_per_minute=3.0, length_ratio=0.5)])
        self.assertEqual(tips[0], 'Slow down: you average 175 words per minute (aim for 120-160).')
        self.assertEqual(tips[1], 'Cut filler words: 3.5 per minute on average.')
        self.assertIn('about 50% of the target length', tips[2])
        self.assertIn('2 long pauses', tips[3])
        self.assertEqual(tips[4], '1 detail you said was not in your confirmed profile. Only claim what you can back up.')
        silent = reminders([attempt('si-30', '', words_per_minute=0)])
        self.assertIn('Practise a few answers first', silent[0])

    def test_unfinished_mock_is_not_shown_as_a_score(self):
        from .cheatsheet import mock_line
        self.assertEqual(mock_line({'overall': 71, 'band': 'Incomplete', 'answered': 1, 'total': 5}), 'latest mock interview unfinished (1 of 5 answered)')
        self.assertEqual(mock_line({'overall': 82, 'band': 'Ready', 'answered': 5, 'total': 5}), 'latest mock interview 82/100 (Ready)')

    def test_pdf_is_one_page_even_with_long_content_and_symbols(self):
        long = attempt('bh-teamwork', ' '.join(['I measured accuracy at 91% on the night clips ✓.'] * 6), star_parts=4)
        sheet = self.build([long, attempt('bh-failure', 'I tried something 🎤.', star_parts=2)], readiness={'overall': 72, 'band': 'Nearly ready', 'answered': 5, 'total': 5})
        pdf = render_pdf(sheet)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(len(re.findall(rb'/Type /Page\b', pdf)), 1)


if __name__ == '__main__':
    unittest.main()

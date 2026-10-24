"""Countdown practice plan scheduling."""
import unittest
from datetime import date, timedelta, timezone

from .plan import build, parse_date, schedule, question_states, todays_questions

TODAY = date(2026, 10, 24)
QUESTIONS = [{'id': qid, 'round': r, 'text': f'Question {qid}'} for qid, r in [
    ('si-30', 'self_introduction'), ('si-90', 'self_introduction'), ('bh-a', 'behavioural'), ('bh-b', 'behavioural'), ('bh-c', 'behavioural'),
    ('tq-a', 'technical'), ('tq-b', 'technical'), ('mf-a', 'motivation_fit'), ('mf-b', 'motivation_fit')]]
GOOD = {'words_per_minute': 140, 'fillers_per_minute': 0.0, 'long_pauses': 0, 'length_ratio': 1.0, 'flags': 0}
WEAK = {**GOOD, 'length_ratio': 0.3}


def attempt(qid, day, summary=GOOD):
    return {'question_id': qid, 'created_at': f'{day.isoformat()}T12:00:00+00:00', 'transcript': 'x', 'summary': summary}


def make(interview, attempts=(), mocks=(), frozen=None, today=TODAY):
    return build(interview, today, QUESTIONS, list(attempts), list(mocks), frozen or {}, timezone.utc)


def questions_on(result, index):
    return [t['question_id'] for t in result['days'][index]['tasks'] if t['kind'] == 'question']


class PlanTests(unittest.TestCase):
    def test_countdown_days_end_with_mock_and_interview_day(self):
        result = make(TODAY + timedelta(4))
        self.assertEqual((result['status'], result['days_left']), ('active', 4))
        self.assertEqual([d['label'] for d in result['days']][:2], ['Today', 'Tomorrow'])
        self.assertEqual(len(result['days']), 5)
        before, interview = result['days'][-2], result['days'][-1]
        self.assertEqual([t['kind'] for t in before['tasks']], ['question', 'question', 'mock', 'cheatsheet'])
        self.assertEqual(interview['label'], 'Interview day')
        self.assertEqual([t['kind'] for t in interview['tasks']], ['question', 'cheatsheet'])
        self.assertEqual(interview['tasks'][0]['question_id'], 'si-30')

    def test_new_questions_first_and_rounds_take_turns(self):
        today = questions_on(make(TODAY + timedelta(4)), 0)
        self.assertEqual(today[0], 'si-30')
        self.assertEqual(len(today), 3)  # 9 open questions over 3 practice days.
        rounds = {q['id']: q['round'] for q in QUESTIONS}
        self.assertEqual(len({rounds[q] for q in today}), 3)

    def test_every_open_question_fits_when_there_is_time(self):
        result = make(TODAY + timedelta(4))
        self.assertEqual(result['unplanned'], [])
        planned = {q for i in range(len(result['days'])) for q in questions_on(result, i)}
        self.assertEqual(planned, {q['id'] for q in QUESTIONS})

    def test_too_little_time_lists_what_will_not_fit(self):
        result = make(TODAY + timedelta(1))
        self.assertEqual(len(questions_on(result, 0)), 2)  # The day before is a mock day.
        self.assertEqual(len(result['unplanned']), 9 - 2)

    def test_strong_answers_rest_and_weak_ones_come_back(self):
        attempts = [attempt('tq-a', TODAY - timedelta(1)), attempt('tq-b', TODAY - timedelta(1), WEAK), attempt('mf-a', TODAY - timedelta(6))]
        states = question_states(QUESTIONS, attempts, timezone.utc)
        self.assertEqual((states['tq-a']['status'], states['tq-b']['status'], states['mf-a']['status']), ('strong', 'work', 'strong'))
        days = schedule(QUESTIONS, states, TODAY, TODAY + timedelta(10), {})
        everything = [q for d in days.values() for q in d['questions']]
        first_tq_a = next(d for d, item in days.items() if 'tq-a' in item['questions'])
        self.assertGreaterEqual((first_tq_a - (TODAY - timedelta(1))).days, 5)
        self.assertIn('tq-b', everything)
        self.assertIn('mf-a', everything)

    def test_practice_today_ticks_tasks_off(self):
        result = make(TODAY + timedelta(4))
        first = questions_on(result, 0)[0]
        done = make(TODAY + timedelta(4), [attempt(first, TODAY, WEAK)], frozen={TODAY: questions_on(result, 0)})
        self.assertTrue(done['days'][0]['tasks'][0]['done'])
        self.assertFalse(done['days'][0]['tasks'][1]['done'])
        self.assertEqual(questions_on(done, 0), questions_on(result, 0))  # Today's list does not shift.

    def test_follow_up_answers_do_not_count_as_the_main_question(self):
        result = make(TODAY + timedelta(4), [attempt('si-30:follow-up', TODAY)])
        self.assertFalse(result['days'][0]['tasks'][0]['done'])

    def test_finished_mock_ticks_the_mock_task(self):
        tomorrow = TODAY + timedelta(1)
        mocks = [{'created_at': f'{TODAY.isoformat()}T09:00:00+00:00', 'answered': 5, 'total': 5}]
        mock_task = next(t for t in make(tomorrow, mocks=mocks)['days'][0]['tasks'] if t['kind'] == 'mock')
        self.assertTrue(mock_task['done'])
        unfinished = [{**mocks[0], 'answered': 2}]
        self.assertFalse(next(t for t in make(tomorrow, mocks=unfinished)['days'][0]['tasks'] if t['kind'] == 'mock')['done'])

    def test_long_countdowns_add_a_midway_mock(self):
        result = make(TODAY + timedelta(8))
        mock_days = [d['label'] for d in result['days'] if any(t['kind'] == 'mock' for t in d['tasks'])]
        self.assertEqual(len(mock_days), 2)

    def test_interview_today_and_passed(self):
        today = make(TODAY)
        self.assertEqual((today['status'], len(today['days'])), ('interview_today', 1))
        self.assertEqual(todays_questions(today), [])
        self.assertEqual(make(TODAY - timedelta(1))['status'], 'passed')

    def test_date_validation(self):
        self.assertEqual(parse_date('2026-10-28', TODAY), date(2026, 10, 28))
        for bad in ('28/10/2026', None, '2026-10-23', '2027-03-01'):
            with self.assertRaises(ValueError):
                parse_date(bad, TODAY)


if __name__ == '__main__':
    unittest.main()

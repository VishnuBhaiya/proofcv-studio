"""Adaptive preparation plan: day kinds, topic order, tests, progress and adaptation."""
import unittest
from datetime import date, timedelta, timezone

from .plan import build, day_kinds, parse_date

START = date(2026, 10, 25)


def topic(qid, learning=False, question=True):
    return {'id': qid, 'question_id': qid if question else None, 'topic': f'topic {qid}', 'question': f'Explain {qid}.' if question else None,
            'requirement': {'text': f'req {qid}'}, 'learning': learning, 'key_points': [{'text': f'{qid} point', 'covered': False}]}


TOPICS = [topic('strong'), topic('weak'), topic('developing'), topic('skipped'), topic('learn-0', learning=True, question=False)]


def answer(qid, day, key_points):
    return {'question_id': qid, 'created_at': f'{day.isoformat()}T12:00:00+00:00', 'summary': {'key_points': key_points}}


CHECK = [answer('strong', START, 1.0), answer('weak', START, 0.0), answer('developing', START, 0.5)]  # 'skipped' was not answered.


def make(interview, attempts=CHECK, today=START, ticks=(), minutes=60, mocks=(), next_steps=()):
    return build(START, today, interview, TOPICS, list(attempts), list(mocks), set(ticks), minutes, 'technical', next_steps, timezone.utc)


def kinds(result):
    return [d['kind'] for d in result['days']]


class DayKindTests(unittest.TestCase):
    def test_study_study_test_then_mock_focus_interview(self):
        self.assertEqual(kinds(make(START + timedelta(9))), ['study', 'study', 'test'] * 2 + ['study', 'mock', 'focus', 'interview'])

    def test_short_countdowns_are_compressed(self):
        span = lambda days: [k for _, k in sorted(day_kinds(START, START + timedelta(days)).items())]
        self.assertEqual(span(0), ['interview'])
        self.assertEqual(span(1), ['mock', 'interview'])
        self.assertEqual(span(2), ['mock', 'focus', 'interview'])
        self.assertEqual(span(3), ['study', 'mock', 'focus', 'interview'])
        self.assertEqual(span(4), ['study', 'test', 'mock', 'focus', 'interview'])  # Always a test before the mock when there is room.


class TopicOrderTests(unittest.TestCase):
    def setUp(self):
        self.plan = make(START + timedelta(9))

    def studied(self, index):
        return [t['topic_id'] for t in self.plan['days'][index]['tasks']]

    def test_weakest_first_then_rotation_and_strong_last(self):
        self.assertEqual(self.studied(0), ['weak', 'skipped'])  # Weak, then not assessed: two topics for an hour a day.
        self.assertEqual(self.studied(1), ['learn-0', 'developing'])  # A chosen skill to learn, then developing.
        self.assertEqual(self.studied(3), ['weak', 'skipped'])  # Back round, still weakest first.
        self.assertNotIn('strong', self.studied(0) + self.studied(1))

    def test_every_topic_gets_a_turn_before_weak_ones_repeat(self):
        topics = [topic(f'w{i}') for i in range(3)] + [topic(f'n{i}') for i in range(6)]
        check = [answer(f'w{i}', START, 0.0) for i in range(3)]
        plan = build(START, START, START + timedelta(14), topics, check, [], set(), 60, 'technical', (), timezone.utc)
        studied = [t['topic_id'] for d in plan['days'] if d['kind'] == 'study' for t in d['tasks']]
        self.assertEqual(set(studied[:9]), {t['id'] for t in topics})  # All nine before any repeats.
        self.assertEqual(studied[:3], ['w0', 'w1', 'w2'])  # Weak first.

    def test_test_session_asks_what_was_studied(self):
        test = self.plan['days'][2]
        self.assertEqual([t['question_id'] for t in test['tasks']], ['weak', 'developing', 'skipped', 'strong'])  # Studied first, then weakest.
        self.assertTrue(all(t['kind'] == 'test' for t in test['tasks']))
        self.assertEqual(test['tasks'][0]['before'], 0)

    def test_daily_time_sets_topics_per_study_day(self):
        self.assertEqual(len(make(START + timedelta(9), minutes=30)['days'][0]['tasks']), 1)
        self.assertEqual(len(make(START + timedelta(9), minutes=180)['days'][0]['tasks']), 4)

    def test_tracker_shows_start_and_now(self):
        later = make(START + timedelta(9), CHECK + [answer('weak', START + timedelta(1), 0.8)], today=START + timedelta(2))
        weak = next(t for t in later['topics'] if t['id'] == 'weak')
        self.assertEqual((weak['start'], weak['start_knowledge'], weak['level'], weak['knowledge']), ('weak', 0, 'strong', 80))
        self.assertEqual(next(t for t in later['topics'] if t['id'] == 'skipped')['level'], 'not_assessed')
        self.assertEqual(next(t for t in later['topics'] if t['id'] == 'learn-0')['level'], 'to_learn')


class ProgressTests(unittest.TestCase):
    def test_study_done_by_tick_or_by_answering(self):
        day = START.isoformat()
        plan = make(START + timedelta(9), CHECK + [answer('skipped', START, 0.2)], ticks={(day, 'study:weak')})
        self.assertEqual([t['done'] for t in plan['days'][0]['tasks']], [True, True])
        self.assertEqual(plan['days'][0]['done'], 2)

    def test_skill_check_answers_do_not_tick_off_the_first_day(self):
        since = f'{START.isoformat()}T12:30:00+00:00'
        plan = build(START, START, START + timedelta(9), TOPICS, CHECK, [], set(), 60, 'technical', (), timezone.utc, since)
        self.assertEqual([t['done'] for t in plan['days'][0]['tasks']], [False, False])
        self.assertEqual(plan['days'][0]['tasks'][0]['level'], 'weak')  # But they still set the starting level.

    def test_test_answers_show_before_and_after(self):
        test_day = START + timedelta(2)
        plan = make(START + timedelta(9), CHECK + [answer('weak', test_day, 0.6)], today=test_day)
        first = plan['days'][2]['tasks'][0]
        self.assertEqual((first['question_id'], first['before'], first['after'], first['done']), ('weak', 0, 60, True))

    def test_a_test_taken_early_counts_for_its_day(self):
        test_day = START + timedelta(2)
        plan = make(START + timedelta(9), CHECK + [answer('weak', START + timedelta(1), 0.7)], today=START + timedelta(1),
                    ticks={(test_day.isoformat(), 'test:weak')})
        early = next(t for t in plan['days'][2]['tasks'] if t['question_id'] == 'weak')
        self.assertEqual((early['done'], early['early'], early['before'], early['after']), (True, True, 0, 70))  # Before is from the skill check.
        others = [t for t in plan['days'][2]['tasks'] if t['question_id'] != 'weak']
        self.assertFalse(any(t['done'] for t in others))
        untaken = make(START + timedelta(9), CHECK + [answer('weak', START + timedelta(1), 0.7)], today=START + timedelta(1))
        self.assertFalse(next(t for t in untaken['days'][2]['tasks'] if t['question_id'] == 'weak')['done'])  # Practice alone does not tick a future test.

    def test_better_answers_change_the_days_after_but_not_today(self):
        day1 = START + timedelta(1)
        before = make(START + timedelta(9), today=day1)
        improved = make(START + timedelta(9), CHECK + [answer('weak', day1, 0.9)], today=day1)
        self.assertEqual(before['days'][1]['tasks'], [{**t, 'done': t['done']} for t in improved['days'][1]['tasks']])  # Today stays fixed.
        self.assertNotIn('weak', [t['topic_id'] for t in improved['days'][3]['tasks']])  # Now strong, so it drops back.
        self.assertIn('weak', [t['topic_id'] for t in before['days'][3]['tasks']])

    def test_mock_focus_and_interview_days(self):
        mock_day = START + timedelta(7)
        mocks = [{'created_at': f'{mock_day.isoformat()}T09:00:00+00:00', 'answered': 5, 'total': 5}]
        plan = make(START + timedelta(9), mocks=mocks, next_steps=['Slow down.'], ticks={((START + timedelta(8)).isoformat(), 'cheatsheet')})
        mock, focus, interview = plan['days'][-3:]
        self.assertEqual((mock['tasks'][0]['done'], mock['mock_next_steps'], 'tip' in mock), (True, ['Slow down.'], True))
        self.assertEqual([t['topic_id'] for t in focus['tasks'][:-1]], ['weak', 'skipped', 'learn-0'])
        self.assertEqual((focus['tasks'][-1]['kind'], focus['tasks'][-1]['done'], focus['mock_next_steps']), ('cheatsheet', True, ['Slow down.']))
        self.assertEqual([t['kind'] for t in interview['tasks']], ['warmup', 'cheatsheet'])

    def test_status_and_labels(self):
        self.assertEqual(make(START + timedelta(9), today=START + timedelta(10))['status'], 'passed')
        self.assertEqual(make(START + timedelta(9), today=START + timedelta(9))['status'], 'interview_today')
        plan = make(START + timedelta(9), today=START + timedelta(1))
        self.assertEqual([d['label'] for d in plan['days'][:3]], ['Yesterday', 'Today', 'Tomorrow'])

    def test_date_validation(self):
        self.assertEqual(parse_date('2026-10-28', START), date(2026, 10, 28))
        for bad in ('28/10/2026', None, '2026-10-24', '2027-03-01'):
            with self.assertRaises(ValueError):
                parse_date(bad, START)


if __name__ == '__main__':
    unittest.main()

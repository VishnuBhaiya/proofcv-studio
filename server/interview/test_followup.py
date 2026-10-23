"""Which follow-up question the interviewer asks next."""
import unittest

from .followup import MAX_DEPTH, follow_up

BEHAVIOURAL = {'id': 'bh-teamwork', 'round': 'behavioural'}
TECHNICAL = {'id': 'tq-detection-eval', 'round': 'technical'}
INTRO = {'id': 'si-90', 'round': 'self_introduction'}


def response(round_='behavioural', **extra):
    return {'round': round_, 'transcript': 'I did it.', 'target_seconds': 90, 'delivery': {'speaking_seconds': 80}, **extra}


def claim(status='supported', *flags):
    return {'text': 'I deployed it on AWS with my team of 6 people.', 'status': status, 'flags': list(flags)}


def star(present=('situation', 'task', 'action', 'result'), notes=()):
    return {'present': {k: k in present for k in ('situation', 'task', 'action', 'result')}, 'notes': list(notes)}


class FollowUpTests(unittest.TestCase):
    def test_unbacked_tool_comes_first_and_keeps_its_spoken_form(self):
        flag = {'type': 'tool', 'value': 'aws', 'said': 'AWS'}
        result = follow_up(BEHAVIOURAL, response(fact_check={'claims': [claim('supported', flag)]}, star=star(('situation',))))
        self.assertTrue(result['question'].startswith('You mentioned AWS.'))
        self.assertEqual((result['kind'], result['depth']), ('evidence', 1))

    def test_unbacked_number_and_leadership(self):
        number = follow_up(BEHAVIOURAL, response(fact_check={'claims': [claim('supported', {'type': 'number', 'value': '78%'})]}))
        self.assertIn('You said 78%', number['question'])
        lead = follow_up(BEHAVIOURAL, response(fact_check={'claims': [claim('supported', {'type': 'leadership', 'value': 'I led'})]}))
        self.assertIn('led others', lead['question'])

    def test_unmatched_story_is_probed_in_personal_answers_only(self):
        story = follow_up(BEHAVIOURAL, response(fact_check={'claims': [claim('unmatched')]}))
        self.assertTrue(story['question'].startswith('Tell me more about this'))
        technical = follow_up(TECHNICAL, response('technical', fact_check={'claims': [claim('unmatched')]}))
        self.assertEqual(technical['kind'], 'deeper')

    def test_missing_star_parts_in_priority_order(self):
        self.assertIn('outcome', follow_up(BEHAVIOURAL, response(star=star(('situation', 'action'))))['question'])
        self.assertIn('put a number', follow_up(BEHAVIOURAL, response(star=star(notes=['Your result has no number.'])))['question'])
        self.assertIn('trying to achieve', follow_up(BEHAVIOURAL, response(star=star(('situation', 'action', 'result'))))['question'])
        self.assertIn('personally do', follow_up(BEHAVIOURAL, response(star=star(notes=['Your actions mostly say "we".'])))['question'])

    def test_missed_key_point_is_asked_about_and_carried(self):
        content = {'key_points': [{'text': 'Precision and recall', 'status': 'covered'}, {'text': 'mAP across classes', 'status': 'missed'}]}
        result = follow_up(TECHNICAL, response('technical', content=content))
        self.assertEqual(result['question'], 'You did not mention mAP across classes. How does that fit in?')
        self.assertEqual(result['key_point'], 'mAP across classes')

    def test_short_intro_and_strong_answers(self):
        short = follow_up(INTRO, response('self_introduction', delivery={'speaking_seconds': 20}))
        self.assertIn('most proud of', short['question'])
        strong = follow_up(BEHAVIOURAL, response(star=star(), fact_check={'claims': [claim()]}))
        self.assertEqual((strong['kind'], strong['question']), ('deeper', 'What would you do differently if you faced that situation again?'))

    def test_stops_at_max_depth_and_on_silence(self):
        self.assertIsNone(follow_up(BEHAVIOURAL, response(), MAX_DEPTH))
        self.assertIsNone(follow_up(BEHAVIOURAL, response(transcript='')))
        self.assertEqual(follow_up(BEHAVIOURAL, response(star=star()), 1)['depth'], 2)


if __name__ == '__main__':
    unittest.main()

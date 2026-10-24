"""Adaptive preparation plan: what to do each day from the skill check to the interview.

Plain scheduling rules, no model. Days run from the day the skill check was finished:
study, study, test, repeated; a full mock interview two days before the interview;
a focus day the day before; then the interview day. Short countdowns are compressed.

Study days take the topics from the skill check, weakest first: weak, not yet
assessed, skills the user chose to learn, developing, and strong last as refreshers.
A topic already studied moves down the queue, so every topic gets a turn and weak
ones come back sooner than strong ones. Test days re-ask the topics just studied. Each
topic's level comes from the user's latest answer to its question before that day,
so practice and tests change the days that follow, while today's list stays fixed.
"""
from datetime import date, datetime, timedelta

from .diagnostic import level as knowledge_level

MAX_DAYS = 60
INTRO = 'si-30'
TOPICS_PER_DAY = {30: 1, 60: 2, 120: 3, 180: 4}  # From the daily time chosen in setup.
MAX_TEST_QUESTIONS = 4
FOCUS_TOPICS = 3
RANK = {'weak': 0, 'not_assessed': 1, 'to_learn': 2, 'developing': 3, 'strong': 4}
STUDIED_PENALTY = 2  # Each earlier study day moves a topic down about two levels, so every topic gets a turn.
TITLES = {'study': 'Study day', 'test': 'Test session', 'mock': 'Mock interview day', 'focus': 'Focus day', 'interview': 'Interview day'}
NOTES = {
    'study': 'Learn the key points for each topic, then say an answer out loud.',
    'test': 'A questioning session on what you studied: answer each question as in the interview.',
    'mock': 'A full mock interview, as close to the real thing as possible, with a report at the end.',
    'focus': 'No new topics. Go over your weakest points and the mock interview report, then rest.',
    'interview': 'One warm-up, a last look at your cheat sheet, and that is it. Good luck.',
}
STAGE_TIPS = {
    'screening': 'Screening calls are short: lead with your 30-second introduction and why this role.',
    'technical': 'Expect deeper technical questions and follow-ups: explain your reasoning, not just the answer.',
    'panel': 'With a panel, answer the person who asked, but include everyone, and keep answers structured.',
    'final': 'Final interviews weigh motivation and fit: have clear reasons for this job and good questions to ask.',
}


def local_day(timestamp, tz=None):
    """The calendar day of a stored UTC timestamp, on this computer's clock."""
    return datetime.fromisoformat(timestamp).astimezone(tz).date()


def parse_date(value, today):
    try:
        chosen = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError('Enter the interview date as YYYY-MM-DD.')
    if chosen < today:
        raise ValueError('The interview date is in the past.')
    if (chosen - today).days > MAX_DAYS:
        raise ValueError(f'Pick a date within the next {MAX_DAYS} days.')
    return chosen


def label(day, today, interview):
    if day == interview:
        return 'Interview day'
    if day == today:
        return 'Today'
    if day == today + timedelta(1):
        return 'Tomorrow'
    if day == today - timedelta(1):
        return 'Yesterday'
    return ''


def day_kinds(start, interview):
    """The kind of every day from start to the interview."""
    span = (interview - start).days
    if span <= 0:
        return {interview: 'interview'}
    if span == 1:
        return {start: 'mock', interview: 'interview'}
    if span == 2:
        return {start: 'mock', start + timedelta(1): 'focus', interview: 'interview'}
    prep = span - 2
    # Study, study, test; with exactly two days before the mock, study then test.
    kinds = {start + timedelta(d): ('test' if d % 3 == 2 or (prep == 2 and d == 1) else 'study') for d in range(prep)}
    return {**kinds, interview - timedelta(2): 'mock', interview - timedelta(1): 'focus', interview: 'interview'}


class Evidence:
    """Each question's knowledge (share of key points covered) from the latest answer to it."""

    def __init__(self, attempts, tz=None, since=None):
        self.by_question, self.answered_on = {}, {}
        for a in sorted(attempts, key=lambda a: a['created_at']):
            if ':' in a['question_id']:
                continue
            day = local_day(a['created_at'], tz)
            # Answers from the skill check itself set the starting knowledge but do not tick off plan tasks.
            if since is None or datetime.fromisoformat(a['created_at']) > datetime.fromisoformat(since):
                self.answered_on.setdefault(day, set()).add(a['question_id'])
            if a['summary'].get('key_points') is not None:
                self.by_question.setdefault(a['question_id'], []).append((day, a['summary']['key_points']))

    def knowledge(self, question_id, before=None):
        """Latest knowledge before a day (or ever, when before is None); None if never answered."""
        found = [k for day, k in self.by_question.get(question_id, []) if before is None or day < before]
        return found[-1] if found else None

    def answered(self, question_id, day):
        return question_id in self.answered_on.get(day, set())

    def last_answered(self, question_id, before):
        """The latest day before a date on which the question was answered (after the skill check), or None."""
        days = [day for day, ids in self.answered_on.items() if day < before and question_id in ids]
        return max(days) if days else None


def topic_level(topic, knowledge):
    if knowledge is not None:
        return knowledge_level(knowledge)
    return 'to_learn' if topic['learning'] and not topic['question_id'] else 'not_assessed'


def pct(value):
    return None if value is None else round(value * 100)


def build(start, today, interview, topics, attempts, mocks, ticks, daily_minutes, stage, mock_next_steps=(), tz=None, since=None):
    """The whole plan: every day's kind and tasks with progress, and each topic's level at the start and now.

    topics: from the skill check, each {id, question_id (None for a skill to learn with no question),
    topic, question, requirement, learning, key_points: [{text, covered}]}. ticks: {(iso day, task key)}
    the user marked done. mocks: this job's mock interviews with created_at, answered and total.
    since: when the skill check finished; only later answers count towards a day's tasks.
    """
    evidence = Evidence(attempts, tz, since)
    finished_mocks = {local_day(m['created_at'], tz) for m in mocks if m['answered'] and m['answered'] == m['total']}
    per_day = TOPICS_PER_DAY.get(daily_minutes, 2)
    order = {t['id']: i for i, t in enumerate(topics)}
    studied = {t['id']: 0 for t in topics}
    recent, previous = [], set()  # Topics from the study days since the last test; topics of the last study day.

    first_day = start + timedelta(1)

    def known(topic, before):
        """Knowledge from answers before a day; the skill check's own answers count from the start day."""
        if not topic['question_id']:
            return None
        return evidence.knowledge(topic['question_id'], before if before is None else max(before, first_day))

    def need(topic, before):
        """Sort key: weakest level first, then least knowledge, then the topic's skill-check order."""
        value = known(topic, before)
        return RANK[topic_level(topic, value)], -1 if value is None else value, order[topic['id']]

    def ticked(day, key):
        return (day.isoformat(), key) in ticks

    days = []
    for day, kind in sorted(day_kinds(start, interview).items()):
        if kind == 'study':
            ranked = sorted(topics, key=lambda t: (need(t, day)[0] + STUDIED_PENALTY * studied[t['id']], *need(t, day)[1:]))
            chosen = ([t for t in ranked if t['id'] not in previous] + [t for t in ranked if t['id'] in previous])[:per_day]
            for t in chosen:
                studied[t['id']] += 1
            previous = {t['id'] for t in chosen}
            recent += [t['id'] for t in chosen]
            tasks = [{'kind': 'study', 'key': f"study:{t['id']}", 'topic_id': t['id'], 'text': t['topic'], 'question_id': t['question_id'],
                      'question': t['question'], 'key_points': t['key_points'], 'resources': t.get('resources', []), 'level': topic_level(t, known(t, day)),
                      'done': ticked(day, f"study:{t['id']}") or bool(t['question_id'] and evidence.answered(t['question_id'], day))} for t in chosen]
        elif kind == 'test':
            asked = [t for t in topics if t['id'] in recent and t['question_id']]
            asked += [t for t in sorted(topics, key=lambda t: need(t, day)) if t['question_id'] and t not in asked]
            tasks = []
            for t in asked[:MAX_TEST_QUESTIONS]:
                # A test can be taken early: its answers are given on an earlier day and the question is ticked for this one.
                taken = day if evidence.answered(t['question_id'], day) else (
                    evidence.last_answered(t['question_id'], day) if ticked(day, f"test:{t['id']}") else None)
                tasks.append({'kind': 'test', 'key': f"test:{t['id']}", 'topic_id': t['id'], 'text': t['question'], 'topic': t['topic'], 'question_id': t['question_id'],
                              'before': pct(known(t, taken or day)), 'after': pct(evidence.knowledge(t['question_id'], taken + timedelta(1))) if taken else None,
                              'done': taken is not None, 'early': bool(taken and taken < day)})
            recent = []
        elif kind == 'mock':
            tasks = [{'kind': 'mock', 'key': 'mock', 'text': 'Full mock interview (5 questions with follow-ups) and its report', 'done': day in finished_mocks}]
        elif kind == 'focus':
            tasks = [{'kind': 'focus', 'key': f"focus:{t['id']}", 'topic_id': t['id'], 'text': t['topic'], 'key_points': t['key_points'], 'resources': t.get('resources', []),
                      'level': topic_level(t, known(t, day)), 'done': ticked(day, f"focus:{t['id']}")} for t in sorted(topics, key=lambda t: need(t, day))[:FOCUS_TOPICS]]
            tasks.append({'kind': 'cheatsheet', 'key': 'cheatsheet', 'text': 'Read your cheat sheet and fill in any [brackets]', 'done': ticked(day, 'cheatsheet')})
        else:
            tasks = [{'kind': 'warmup', 'key': 'warmup', 'text': 'One run of your 30-second introduction', 'question_id': INTRO, 'done': evidence.answered(INTRO, day)},
                     {'kind': 'cheatsheet', 'key': 'cheatsheet', 'text': 'Read your cheat sheet once, then stop practising', 'done': ticked(day, 'cheatsheet')}]
        entry = {'date': day.isoformat(), 'label': label(day, today, interview), 'kind': kind, 'title': TITLES[kind], 'note': NOTES[kind],
                 'tasks': tasks, 'done': sum(t['done'] for t in tasks), 'total': len(tasks)}
        if mock_next_steps and (kind == 'focus' or (kind == 'mock' and day in finished_mocks)):
            entry['mock_next_steps'] = list(mock_next_steps)
        if kind in ('mock', 'interview') and stage in STAGE_TIPS:
            entry['tip'] = STAGE_TIPS[stage]
        days.append(entry)

    tracker = [{'id': t['id'], 'topic': t['topic'], 'requirement': t['requirement'], 'learning': t['learning'], 'question_id': t['question_id'], 'resources': t.get('resources', []),
                'start': topic_level(t, known(t, start)), 'start_knowledge': pct(known(t, start)),
                'level': topic_level(t, known(t, None)), 'knowledge': pct(known(t, None))} for t in topics]
    days_left = (interview - today).days
    status = 'passed' if days_left < 0 else 'interview_today' if days_left == 0 else 'active'
    return {'start': start.isoformat(), 'today': today.isoformat(), 'interview_date': interview.isoformat(), 'days_left': days_left,
            'status': status, 'per_day': per_day, 'topics': tracker, 'days': days}

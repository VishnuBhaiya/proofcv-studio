"""Countdown practice plan: what to practise each day until the interview.

Plain scheduling rules, no model. Questions that were never practised come first,
then answers that still need work (oldest first), and strong answers come back
only every few days to stay fresh. The day before the interview is a full mock
interview; the interview day is a light warm-up with the cheat sheet. Today's list
is frozen once it is made, so it does not shift while the user works through it;
later days are a projection that is recalculated from real practice every time.
"""
from datetime import date, datetime, timedelta
from math import ceil

from .attempts import needs_work

MAX_DAYS = 60
MIN_PER_DAY, MAX_PER_DAY = 3, 6
REVISIT_WORK_DAYS = 2    # A weak answer comes back after this many days.
REVISIT_STRONG_DAYS = 5  # A strong answer is kept fresh this often.
INTRO = 'si-30'
INTRO_REFRESH_DAYS = 3


def local_day(timestamp, tz=None):
    """The calendar day of a stored UTC timestamp, on this computer's clock."""
    return datetime.fromisoformat(timestamp).astimezone(tz).date()


def question_states(questions, attempts, tz=None):
    """Latest state of every planned question: never practised, needs work or strong."""
    states = {q['id']: {'status': 'new', 'last': None, 'attempts': 0} for q in questions}
    for a in attempts:
        state = states.get(a['question_id'])
        if state is None:
            continue
        state['attempts'] += 1
        state['last'] = local_day(a['created_at'], tz)
        state['status'] = 'work' if needs_work(a['summary']) else 'strong'
    return states


def priority(state, day):
    """Lower is more urgent; None when the question should rest on this day."""
    if state['status'] == 'new':
        return (0, 0)
    gap = (day - state['last']).days
    if state['status'] == 'work':
        # A real weak answer can be retried the next day; one only planned for an earlier day rests longer.
        return (1, -gap) if gap >= (REVISIT_WORK_DAYS if state.get('planned') else 1) else None
    return (2, -gap) if gap >= REVISIT_STRONG_DAYS else None


def balanced(candidates, count, by_id):
    """The most urgent questions, taking rounds in turn so one day is not all technical."""
    picked, rounds = [], {}
    for qid in candidates:
        rounds.setdefault(by_id[qid]['round'], []).append(qid)
    while len(picked) < count and any(rounds.values()):
        for name in list(rounds):
            if rounds[name] and len(picked) < count:
                picked.append(rounds[name].pop(0))
    return picked


def reason(state):
    if state['status'] == 'new':
        return 'Not practised yet'
    if state['status'] == 'work':
        return 'Still needs work'
    return 'Strong: keep it fresh'


def schedule(questions, states, today, interview, frozen):
    """Question ids for every day from today to the day before the interview."""
    by_id = {q['id']: q for q in questions}
    order = {q['id']: i for i, q in enumerate(questions)}  # Ties follow the question list: introduction first.
    plan_states = {qid: dict(s) for qid, s in states.items()}
    days = [today + timedelta(d) for d in range((interview - today).days)]
    practice_days = [d for d in days if d != interview - timedelta(1)] or days
    open_items = sum(s['status'] != 'strong' for s in plan_states.values())
    per_day = max(MIN_PER_DAY, min(MAX_PER_DAY, ceil(open_items / max(1, len(practice_days)))))
    result = {}
    for index, day in enumerate(days):
        mock_day = day == interview - timedelta(1) or (len(days) >= 6 and index == len(days) // 2)
        if day in frozen:
            picked = frozen[day]
        else:
            count = 2 if mock_day else per_day
            ranked = sorted((p, order[qid], qid) for qid, s in plan_states.items() if (p := priority(s, day)) is not None)
            picked = []
            for tier in sorted({p[0] for p, _, _ in ranked}):
                # Never-practised questions first, then weak ones, then strong ones; rounds take turns within each.
                picked += balanced([qid for p, _, qid in ranked if p[0] == tier], count - len(picked), by_id)
            if len(picked) < min(count, MIN_PER_DAY):
                # Nothing much is due: top up with the answers practised longest ago.
                spare = sorted((s['last'], order[qid], qid) for qid, s in plan_states.items() if qid not in picked and s['last'] and s['last'] < day)
                picked += [qid for _, _, qid in spare][:min(count, MIN_PER_DAY) - len(picked)]
            # The 30-second introduction opens every interview: it goes first whenever it is due,
            # and even a strong one is refreshed every few days.
            intro = plan_states.get(INTRO)
            if intro and INTRO not in picked and (priority(intro, day) is not None or intro['status'] == 'strong' and (day - intro['last']).days >= INTRO_REFRESH_DAYS):
                picked = [INTRO] + picked[:count - 1]
        if INTRO in picked:
            picked = [INTRO] + [qid for qid in picked if qid != INTRO]
        for qid in picked:
            state = plan_states.get(qid)
            if state and state['last'] != day:
                # Projection: planned practice gets done. A first try or a weak answer gets one review
                # a couple of days later; after that review it is treated as settled.
                settled = state['status'] == 'strong' or state['status'] == 'work' and state.get('planned')
                state.update(status='strong' if settled else 'work', last=day, planned=True)
        result[day] = {'questions': picked, 'mock': mock_day}
    return result


def build(interview, today, questions, attempts, mocks, frozen, tz=None):
    """The whole plan: countdown, today's tasks with progress, and the days ahead."""
    by_id = {q['id']: q for q in questions}
    states = question_states(questions, attempts, tz)
    counts = {status: sum(s['status'] == status for s in states.values()) for status in ('new', 'work', 'strong')}
    days_left = (interview - today).days
    base = {'interview_date': interview.isoformat(), 'today': today.isoformat(), 'days_left': days_left, 'counts': counts, 'total': len(questions)}
    if days_left < 0:
        return {**base, 'status': 'passed', 'days': []}
    done_on = {}
    for a in attempts:
        if ':' not in a['question_id']:
            done_on.setdefault(local_day(a['created_at'], tz), set()).add(a['question_id'])
    finished_mocks = {local_day(m['created_at'], tz) for m in mocks if m['answered'] and m['answered'] == m['total']}
    days = []
    for day, item in schedule(questions, states, today, interview, frozen).items():
        tasks = [{'kind': 'question', 'question_id': qid, 'text': by_id[qid]['text'], 'round': by_id[qid]['round'],
                  'reason': reason(states[qid]) if day == today else None, 'done': qid in done_on.get(day, set())}
                 for qid in item['questions'] if qid in by_id]
        if item['mock']:
            tasks.append({'kind': 'mock', 'text': 'Full mock interview (5 questions with follow-ups)', 'done': day in finished_mocks})
        if day == interview - timedelta(1):
            tasks.append({'kind': 'cheatsheet', 'text': 'Read your cheat sheet and fill in any [brackets]', 'done': False})
        days.append({'date': day.isoformat(), 'label': label(day, today, interview), 'tasks': tasks})
    warm_up = [{'kind': 'question', 'question_id': INTRO, 'text': by_id[INTRO]['text'], 'round': by_id[INTRO]['round'],
                'reason': 'One warm-up run', 'done': INTRO in done_on.get(interview, set())}] if INTRO in by_id else []
    days.append({'date': interview.isoformat(), 'label': label(interview, today, interview),
                 'tasks': warm_up + [{'kind': 'cheatsheet', 'text': 'Read your cheat sheet once, then stop practising', 'done': False}]})
    planned = {t['question_id'] for d in days for t in d['tasks'] if t['kind'] == 'question'}
    return {**base, 'status': 'interview_today' if days_left == 0 else 'active', 'days': days,
            'unplanned': [by_id[qid]['text'] for qid, s in states.items() if s['status'] != 'strong' and qid not in planned]}


def todays_questions(result):
    """The question ids to freeze for today (none on interview day, which is fixed anyway)."""
    if result.get('status') != 'active':
        return []
    return [t['question_id'] for t in result['days'][0]['tasks'] if t['kind'] == 'question']


def label(day, today, interview):
    if day == interview:
        return 'Interview day'
    if day == today:
        return 'Today'
    if day == today + timedelta(1):
        return 'Tomorrow'
    return day.strftime('%A %d %B').replace(' 0', ' ')


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

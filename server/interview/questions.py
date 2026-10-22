"""Question picker: choose interview questions for one job from the reviewed bank.

Runs fully locally and deterministically. Questions are linked to the job's
requirements by MiniLM similarity between the question's focus and the
requirement text, plus a bonus for shared exact keywords. Technical questions
mix the user's strengths (to show off) with gaps (to prepare for); slots are
filled only from the user's own confirmed data.
"""
import json
import re
from pathlib import Path

import numpy as np

BANK_PATH = Path(__file__).resolve().parent / 'data' / 'question_bank.json'
ROUNDS = ('self_introduction', 'behavioural', 'technical', 'motivation_fit')
SLOTS = ('job_title', 'project', 'strength', 'gap', 'eligibility')
TAG_BONUS = 0.15
MIN_TECHNICAL_RELEVANCE = 0.45  # Below this a technical question is not about this job.
TECHNICAL_SHOW, TECHNICAL_PREPARE = 3, 2
BEHAVIOURAL_COUNT = 5  # Including both project questions.


def load_bank(path=BANK_PATH):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    ids = [q['id'] for q in data['questions']]
    if len(ids) != len(set(ids)):
        raise ValueError('Question ids must be unique.')
    for q in data['questions']:
        if q['round'] not in ROUNDS:
            raise ValueError(f"Invalid round for {q['id']}.")
        used = set(re.findall(r'\{(\w+)\}', q['text']))
        if not used <= set(SLOTS) or set(q.get('slots', [])) - {'job_title'} != used - {'job_title'}:
            raise ValueError(f"Slots for {q['id']} do not match its text.")
        if q['round'] == 'technical' and len(q.get('key_points') or []) < 3:
            raise ValueError(f"Technical question {q['id']} needs at least three key points.")
    if not all(any(q['round'] == r for q in data['questions']) for r in ROUNDS):
        raise ValueError('Every round needs questions.')
    return data


LEVEL_REASON = {'required': 'Required by the job', 'preferred': 'Preferred by the job', 'responsibility': 'Part of the role'}


def spread(order, requirement_of, limit):
    """Take up to limit items, covering different requirements before repeating one."""
    first, rest, seen = [], [], set()
    for i in order:
        (rest if requirement_of(i) in seen else first).append(i)
        seen.add(requirement_of(i))
    return (first + rest)[:limit]


def best_project(profile, fit_items):
    """The project cited most often as evidence for the job's strengths."""
    projects = profile.get('projects') or []
    if not projects:
        return None
    hits = [0] * len(projects)
    for item in fit_items:
        if item['status'] in ('strong', 'partial'):
            for source in {e['source'] for e in item['evidence']}:
                if source.startswith('project:'):
                    hits[int(source.split(':')[1])] += 1
    return projects[int(np.argmax(hits))]['title']


def relevance(questions, requirements, backend):
    """Question x requirement score: focus similarity plus a bonus for shared exact keywords."""
    if not questions or not requirements:
        return np.zeros((len(questions), len(requirements)))
    scores = np.asarray(backend.encode([q['focus'] for q in questions])) @ np.asarray(backend.encode([r['text'] for r in requirements])).T
    for i, q in enumerate(questions):
        tags = set(q.get('tags') or [])
        for j, r in enumerate(requirements):
            if tags & set(r.get('keywords') or []):
                scores[i, j] += TAG_BONUS
    return scores


def entry(question, text, reason, requirement=None):
    item = {'id': question['id'], 'round': question['round'], 'text': text, 'reason': reason}
    if question.get('seconds'):
        item['seconds'] = question['seconds']
    if requirement:
        item['requirement'] = {'id': requirement['id'], 'text': requirement['text'], 'status': requirement['status']}
    return item


def pick_questions(job, fit_items, keywords_by_id, profile, bank, backend):
    """Questions per round for one job. fit_items come from fit.job_fit; keywords from the requirement map."""
    by_round = {r: [q for q in bank['questions'] if q['round'] == r] for r in ROUNDS}
    title = job['title']
    judged = [{**item, 'keywords': keywords_by_id.get(item['id'], [])} for item in fit_items if item['status'] != 'verify']
    rounds = {'self_introduction': [entry(q, q['text'].replace('{job_title}', title), f"{q['seconds']}-second version") for q in by_round['self_introduction']]}

    # Behavioural: both questions about the user's strongest project, then the most job-relevant others.
    project = best_project(profile, fit_items)
    behavioural = []
    for q in by_round['behavioural']:
        if 'project' in q.get('slots', []) and project:
            behavioural.append(entry(q, q['text'].replace('{project}', project), 'Uses your project with the most evidence for this job'))
    others = [q for q in by_round['behavioural'] if 'project' not in q.get('slots', [])]
    soft = [r for r in judged if r['category'] in ('soft', 'practice')] or judged
    scores = relevance(others, soft, backend)
    order = sorted(range(len(others)), key=lambda i: (-scores[i].max() if soft else 0, i))
    for i in spread(order, lambda i: int(scores[i].argmax()) if soft else i, BEHAVIOURAL_COUNT - len(behavioural)):
        requirement = soft[int(scores[i].argmax())] if soft else None
        behavioural.append(entry(others[i], others[i]['text'], f"Linked to “{requirement['text']}”" if requirement else 'Common behavioural question', requirement))
    rounds['behavioural'] = behavioural

    # Technical: link each question to its best requirement; one question per requirement.
    technical = by_round['technical']
    scores = relevance(technical, judged, backend)
    candidates = sorted((i for i in range(len(technical)) if judged and scores[i].max() >= MIN_TECHNICAL_RELEVANCE), key=lambda i: (-scores[i].max(), i))
    show, prepare, picked, used = [], [], set(), set()
    for i in candidates:
        requirement = judged[int(scores[i].argmax())]
        bucket, limit = (prepare, TECHNICAL_PREPARE) if requirement['status'] == 'gap' else (show, TECHNICAL_SHOW)
        if requirement['id'] not in used and len(bucket) < limit:
            used.add(requirement['id']); picked.add(i); bucket.append(i)
    # Too few strengths or gaps for this job: fill with the next most relevant questions.
    extra = spread([i for i in candidates if i not in picked], lambda i: judged[int(scores[i].argmax())]['id'] in used, TECHNICAL_SHOW + TECHNICAL_PREPARE - len(picked))
    rounds['technical'] = []
    for i in show + prepare + extra:
        requirement = judged[int(scores[i].argmax())]
        reason = 'A gap to prepare for' if requirement['status'] == 'gap' else 'Shows off a strength' if requirement['status'] == 'strong' else 'Partly covered by your evidence'
        rounds['technical'].append(entry(technical[i], technical[i]['text'], f"{reason}: “{requirement['text']}”", requirement))

    # Motivation and fit: fixed core questions plus slots from the user's own strengths and gaps.
    ranked = sorted(judged, key=lambda r: ({'required': 0, 'preferred': 1, 'responsibility': 2}[r['level']], -r['similarity']))
    strengths = [r for r in ranked if r['status'] == 'strong']
    gaps = [r for r in ranked if r['status'] == 'gap' and r['level'] != 'responsibility'] or [r for r in ranked if r['status'] == 'gap']
    eligibility = [r for r in fit_items if r['status'] == 'verify' and r['category'] == 'experience']
    motivation = []
    for q in by_round['motivation_fit']:
        slots = q.get('slots', [])
        if 'strength' in slots:
            motivation += [entry(q, q['text'].replace('{strength}', r['text']), f"{LEVEL_REASON[r['level']]} and backed by your facts", r) for r in strengths[:1]]
        elif 'gap' in slots:
            motivation += [entry(q, q['text'].replace('{gap}', r['text']), f"{LEVEL_REASON[r['level']]}, with no supporting fact in your profile", r) for r in gaps[:2]]
        elif 'eligibility' in slots:
            motivation += [entry(q, q['text'].replace('{eligibility}', r['text']), 'An eligibility requirement to check yourself', r) for r in eligibility[:1]]
        else:
            motivation.append(entry(q, q['text'].replace('{job_title}', title), 'Asked in most interviews'))
    rounds['motivation_fit'] = motivation
    return {'job': {'document_id': job['document_id'], 'title': title}, 'review_status': bank['review_status'], 'rounds': rounds}

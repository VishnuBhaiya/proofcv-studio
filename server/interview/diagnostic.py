"""Skill check: ten technical questions for the chosen job, and where the user is strong or weak.

Runs locally, without Gemini. Questions come from the question bank, matched to the
job's requirements with MiniLM and exact tags (questions.relevance, questions.topical). They cover as many different
requirements as possible; any skill the user chose to learn in setup gets one. The
first four are compulsory and cover the job's most important required skills.

Each answer is scored by the usual pipeline. A topic's level comes from how many of
the question's key points were covered (the knowledge shown), and the key points
that were missed become concrete things to study.
"""
from statistics import mean

from .mock import components, overall
from .questions import MIN_TECHNICAL_RELEVANCE, relevance, topical

QUESTION_COUNT = 10
COMPULSORY = 4
PER_REQUIREMENT = 2
STRONG, DEVELOPING = 0.7, 0.4  # Share of key points covered.
LEVEL_ORDER = {'required': 0, 'preferred': 1, 'responsibility': 2}


def pick(bank, fit_items, learn_ids, backend):
    """Ten technical questions for this job, the four compulsory ones first."""
    technical = [q for q in bank['questions'] if q['round'] == 'technical']
    judged = [r for r in fit_items if r['status'] != 'verify']
    if not judged:
        return []
    scores = relevance(technical, judged, backend)
    eligible, strengths = topical(technical, judged, scores)
    best = {i: int(scores[i].argmax()) for i in range(len(technical))}
    strength = lambda i: strengths[i]
    relevant = sorted((i for i in best if eligible[i]), key=lambda i: (-strength(i), i))
    # Compulsory: one question each for different requirements, required ones first, most relevant first.
    compulsory, used = [], set()
    for i in sorted(relevant, key=lambda i: (LEVEL_ORDER.get(judged[best[i]]['level'], 3), -strength(i), i)):
        if best[i] not in used and len(compulsory) < COMPULSORY:
            compulsory.append(i)
            used.add(best[i])
    compulsory += [i for i in relevant if i not in compulsory][:COMPULSORY - len(compulsory)]
    # Skills the user chose to learn each get their best question, if one is relevant enough.
    learning = []
    for skill_id in learn_ids:
        column = next((c for c, r in enumerate(judged) if r['id'] == skill_id), None)
        if column is not None:
            choice = max((i for i in range(len(technical)) if i not in compulsory + learning), key=lambda i: scores[i, column], default=None)
            if choice is not None and scores[choice, column] >= MIN_TECHNICAL_RELEVANCE and eligible[choice]:
                learning.append(choice)
    # The rest: the best-fitting questions, at most PER_REQUIREMENT for any one requirement, so the check
    # stays on the job's core topics without asking five questions about one of them.
    rest, per_requirement = [], {}
    for i in relevant:
        if i not in compulsory and i not in learning and per_requirement.get(best[i], 0) < PER_REQUIREMENT:
            rest.append(i)
            per_requirement[best[i]] = per_requirement.get(best[i], 0) + 1
    order = compulsory + (learning + rest)[:QUESTION_COUNT - len(compulsory)]
    if len(order) < QUESTION_COUNT:  # A job with few technical requirements: fill with the questions that fit it best.
        order += sorted((i for i in range(len(technical)) if i not in order), key=lambda i: (-strength(i), i))[:QUESTION_COUNT - len(order)]
    picked = []
    for position, i in enumerate(order):
        requirement = judged[best[i]]
        picked.append({'id': technical[i]['id'], 'text': technical[i]['text'], 'topic': technical[i]['focus'], 'round': 'technical',
                       'compulsory': position < COMPULSORY,
                       'requirement': {'id': requirement['id'], 'text': requirement['text'], 'status': requirement['status'], 'level': requirement['level']},
                       'learning': i in learning})
    return picked


def level(knowledge):
    return 'strong' if knowledge >= STRONG else 'developing' if knowledge >= DEVELOPING else 'weak'


def evaluate(session, attempts, learn_skills=()):
    """Strong, developing and weak topics from the answered questions, with what to study for each."""
    topics, delivery, flags = [], [], 0
    for position, question in enumerate(session['questions']):
        link = session['answers'].get(str(position))
        attempt = attempts.get(int(link['id'])) if link else None
        if not attempt:
            topics.append({'position': position, 'topic': question['topic'], 'question': question['text'], 'requirement': question['requirement'],
                           'compulsory': question['compulsory'], 'answered': False, 'level': 'not_assessed'})
            continue
        summary = attempt['summary']
        parts = components(summary)
        knowledge = summary.get('key_points', 0.0)
        delivery.append(parts['delivery'])
        flags += summary.get('flags', 0)
        topics.append({'position': position, 'topic': question['topic'], 'question': question['text'], 'requirement': question['requirement'],
                       'compulsory': question['compulsory'], 'answered': True, 'knowledge': round(knowledge * 100), 'score': overall(parts),
                       'level': level(knowledge), 'covered': link.get('covered', []), 'partial': link.get('partial', []), 'missed': link.get('missed', [])})
    answered = [t for t in topics if t['answered']]
    groups = {name: [t for t in answered if t['level'] == name] for name in ('strong', 'developing', 'weak')}
    for name in ('developing', 'weak'):
        groups[name].sort(key=lambda t: (t['knowledge'], LEVEL_ORDER.get(t['requirement']['level'], 3)))
    return {
        'answered': len(answered), 'total': len(topics), 'compulsory_done': sum(t['compulsory'] and t['answered'] for t in topics),
        'knowledge': round(mean(t['knowledge'] for t in answered)) if answered else None,
        'score': round(mean(t['score'] for t in answered)) if answered else None,
        'topics': topics, **groups, 'not_assessed': [t for t in topics if not t['answered']],
        'communication': {'delivery': round(mean(delivery)) if delivery else None, 'flags': flags},
        'learn_skills': list(learn_skills),
        'finished': bool(session.get('finished_at')),
        'method': ('Each topic is rated by the share of the question\'s key points your answer covered, matched by meaning on this computer: '
                   f'{round(STRONG * 100)}% or more is strong, {round(DEVELOPING * 100)}-{round(STRONG * 100) - 1}% developing, under {round(DEVELOPING * 100)}% weak. '
                   'Missed and partly covered key points are what to study. Delivery and claims are reported separately.'),
    }

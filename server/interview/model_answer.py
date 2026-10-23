"""Example answers built only from the candidate's confirmed facts.

No text generation model is used. Facts are taken from the confirmed profile,
turned from CV style ("Built a prototype") into spoken first person ("I built a
prototype"), and placed into a structure for the question's round. For
behavioural answers our STAR classifier decides which facts are actions and
results. Anything a strong answer needs that the profile does not contain is
left as a [bracketed prompt] for the candidate to fill in, never invented.
"""
import re

import numpy as np

from .fit import sentences
from .star import classifier

IRREGULAR_PAST = {'built', 'wrote', 'made', 'ran', 'led', 'took', 'found', 'set', 'gave', 'kept', 'put', 'won', 'got', 'drew', 'chose',
                  'sent', 'taught', 'brought', 'did', 'met', 'spoke', 'held', 'grew', 'began', 'became', 'read', 'saw', 'told'}
NOTE = 'Built only from your confirmed profile. [Brackets] mark details your profile does not contain: fill them in from memory, never invent them.'


def is_past_verb(word):
    word = word.lower()
    return word.endswith('ed') or word in IRREGULAR_PAST


def first_person(sentence):
    """'Built a prototype.' -> 'I built a prototype.'; 'Uses Python.' -> 'I use Python.'; other sentences unchanged."""
    sentence = sentence.strip()
    word, rest = (sentence.split(' ', 1) + [''])[:2]
    if is_past_verb(word):
        verb = word.lower()
    elif re.fullmatch(r'[A-Z][a-z]+s', word) and not word.endswith('ss'):
        verb = word.lower()[:-2] if re.search(r'(ch|sh|x|ss|zz)es$', word) else word.lower()[:-1]
    else:
        return sentence
    return f'I {verb} {rest}'.strip()


def clauses(sentence):
    """Split a CV-style list of actions into separate steps, but only when every piece starts with a verb."""
    pieces = [p.strip() for p in re.split(r',\s+(?:and\s+)?', sentence.strip().rstrip('.')) if p.strip()]
    if len(pieces) >= 3 and all(is_past_verb(p.split()[0]) for p in pieces):
        return [p[0].upper() + p[1:] + '.' for p in pieces]
    return [sentence]


def lower_first(sentence):
    """Lower-case the first letter mid-sentence, unless it starts a name such as 'YOLO' or 'Artificial Intelligence'."""
    words = sentence.split(' ')
    if sentence[:2].isupper() or sentence.startswith('I ') or (len(words) > 1 and words[1][:1].isupper()):
        return sentence
    return sentence[:1].lower() + sentence[1:]


def part(label, text, source=None):
    return {'label': label, 'text': text, 'source': source, 'placeholder': False}


def prompt(label, text):
    return {'label': label, 'text': f'[{text}]', 'source': None, 'placeholder': True}


def finish(kind, parts):
    return {'kind': kind, 'parts': parts, 'text': ' '.join(p['text'] for p in parts if not p['placeholder']), 'note': NOTE}


def stories(profile):
    """Projects and experience roles with their facts as spoken first-person sentences."""
    found = []
    for p in profile.get('projects') or []:
        found.append({'kind': 'project', 'context': f"my {p['title']} project", 'title': p['title'], 'source': f"Project: {p['title']}",
                      'sentences': [first_person(c) for s in sentences(p.get('description') or '') for c in clauses(s)]})
    experience = (profile.get('experience') or '').strip()
    if experience.lower() not in ('', 'none', 'no', 'n/a'):
        for block in re.split(r'\n\s*\n', experience):
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            header = [h.strip() for h in lines[0].split('|')] if lines else []
            if len(header) >= 2:
                found.append({'kind': 'role', 'context': f'my role as {header[0]} at {header[1]}', 'as': f'as {header[0]} at {header[1]}',
                              'title': header[0], 'source': f'Experience: {header[0]}',
                              'sentences': [first_person(c) for line in lines[1:] for s in sentences(line) for c in clauses(s)]})
    return [s for s in found if s['sentences']]


def closest(texts, query, backend):
    if not texts:
        return None, 0.0
    scores = np.asarray(backend.encode(texts)) @ np.asarray(backend.encode([query]))[0]
    best = int(scores.argmax())
    return best, float(scores[best])


def closest_fact(profile, query, backend):
    """The single project or role sentence closest to the query, with its story."""
    facts = [(story, s) for story in stories(profile) for s in story['sentences']]
    best, similarity = closest([s for _, s in facts], query, backend)
    return (facts[best] if best is not None else (None, None)), similarity


def achievements_about(profile, title):
    words = set(re.findall(r'[a-z]{4,}', title.lower()))
    lines = [l.strip() for l in (profile.get('achievements') or '').splitlines() if l.strip()]
    return [l for l in lines if len(words & set(re.findall(r'[a-z]{4,}', l.lower()))) >= 2]


def quoted(requirements):
    return ' and '.join(f"“{r['text']}”" for r in requirements)


def behavioural(question_text, profile, backend):
    options = stories(profile)
    if not options:
        return finish('star', [prompt('Situation', 'Your profile has no projects or roles yet: pick a real example and say where you were'),
                               prompt('Task', 'What you needed to achieve'), prompt('Action', 'Two or three specific steps you took'),
                               prompt('Result', 'What changed, ideally with a number')])
    named = [s for s in options if s['title'].lower() in question_text.lower()]
    story = named[0] if named else options[closest([' '.join(s['sentences']) for s in options], question_text, backend)[0]]
    spoken = story['sentences']
    labels = [p['label'] for p in classifier().predict(spoken, backend)]
    rest = list(zip(spoken[1:], labels[1:]))
    parts = [part('Situation', f"In {story['context']}, {lower_first(spoken[0])}", story['source'])]
    tasks = [s for s, l in rest if l == 'task']
    parts.append(part('Task', tasks[0], story['source']) if tasks else prompt('Task', 'Say what your goal was: the target, deadline or problem you were asked to solve'))
    actions = [s for s, l in rest if l == 'action'][:3] or [s for s, l in rest if l not in ('task', 'result')][:3]
    parts += [part('Action', s, story['source']) for s in actions] or [prompt('Action', 'Two or three specific steps you took yourself')]
    results = [f'This led to: {a}' for a in achievements_about(profile, story['title'])] + [s for s, l in rest if l == 'result' and s not in actions]
    parts += [part('Result', s, story['source']) for s in results[:2]] or [prompt('Result', 'What changed because of your work? Add a number if you can')]
    if not any(re.search(r'\d', p['text']) for p in parts if p['label'] == 'Result'):
        parts.append(prompt('Result', 'Add a measurable outcome if you have one: time saved, accuracy, a grade'))
    return finish('star', parts)


def technical(question, content_result, profile, backend):
    status = {k['text']: k['status'] for k in (content_result or {}).get('key_points', [])}
    parts = [part('Key point you missed' if status.get(k) == 'missed' else 'Key point', k + '.') for k in question['key_points']]
    (story, fact), similarity = closest_fact(profile, question['focus'], backend)
    if story and similarity >= 0.35:
        parts.append(part('Link to your experience', f"For example, in {story['context']}, {lower_first(fact)}", story['source']))
    else:
        parts.append(prompt('Link to your experience', 'Mention a project where you used this, if you have one'))
    return finish('outline', parts)


def introduction(question, profile, fit_items, job, backend):
    seconds = question.get('seconds', 30)
    name = (profile.get('name') or '').split(' ')[0]
    parts = [part('Hello', f"Hi, I'm {name}.") if name else prompt('Hello', 'Your name')]
    facts = profile.get('summary_facts') or []
    if facts:
        who = sentences(facts[0])[0]
        spoken = first_person(who)
        parts.append(part('Who you are', spoken if spoken != who else f"I'm {'an' if who[0].lower() in 'aeiou' else 'a'} {lower_first(who)}", 'Summary fact'))
    options = stories(profile)
    projects = [s for s in options if s['kind'] == 'project']
    roles = [s for s in options if s['kind'] == 'role']
    strong = [r for r in fit_items if r['status'] == 'strong' and r['level'] == 'required'] or [r for r in fit_items if r['status'] == 'strong']
    if projects:
        story = projects[closest([' '.join(s['sentences']) for s in projects], ' '.join(r['text'] for r in strong) or job['title'], backend)[0]]
        parts.append(part('Highlight', f"Recently, in {story['context']}, {lower_first(story['sentences'][0])}", story['source']))
    if seconds >= 90 and roles:
        parts.append(part('Experience', f"I also worked {roles[0]['as']}, where {lower_first(roles[0]['sentences'][0])}", roles[0]['source']))
    if strong:
        parts.append(part('Why this role', f"I'm applying for the {job['title']} role because it asks for {quoted(strong[:2])}, which is what I have been doing."))
    else:
        parts.append(prompt('Why this role', f"Why you want the {job['title']} role"))
    gaps = sorted((r for r in fit_items if r['status'] == 'gap' and r['level'] != 'responsibility'), key=lambda r: r['level'] != 'required')
    if seconds >= 120 and gaps:
        parts.append(part('Growth', f"I'm still building experience in {quoted(gaps[:1])}, and I want to grow that in this role."))
    return finish('introduction', parts)


def motivation(question, requirement_id, profile, fit_items, job, backend):
    requirement = next((r for r in fit_items if r['id'] == requirement_id), None)
    strong = [r for r in fit_items if r['status'] == 'strong']
    if question['id'] == 'mf-strength' and requirement:
        (story, fact), _ = closest_fact(profile, requirement['text'], backend)
        parts = [part('Claim', f"“{requirement['text']}” is one of my strongest areas.")]
        parts.append(part('Evidence', f"For example, in {story['context']}, {lower_first(fact)}", story['source']) if story else prompt('Evidence', 'A specific example'))
        parts.append(prompt('Use in this role', f"How you would apply it in the {job['title']} role"))
    elif question['id'] in ('mf-gap', 'mf-eligibility') and requirement:
        (story, fact), similarity = closest_fact(profile, requirement['text'], backend)
        parts = [part('Be honest', f"The job asks for “{requirement['text']}”, and I haven't fully met that yet.")]
        if story and similarity >= 0.25:
            parts.append(part('Closest experience', f"The closest experience I have is in {story['context']}: {lower_first(fact)}", story['source']))
        parts.append(prompt('Plan', 'How you would close the gap: a course, a side project, or learning on the job, and how quickly'))
    elif question['id'] == 'mf-questions':
        parts = [part('Question', f"What would success look like in the first six months for the {job['title']}?"),
                 part('Question', 'What does a typical week look like for the team?'),
                 prompt('Question', 'One question about something specific in the job ad that interests you')]
    else:
        parts = [part('Why this role', f"This role asks for {quoted(strong[:2])}, which is the work I enjoy most.") if strong else prompt('Why this role', 'What draws you to this role')]
        options = stories(profile)
        if options:
            story = options[closest([' '.join(s['sentences']) for s in options], job['title'] + ' ' + ' '.join(r['text'] for r in strong[:2]), backend)[0]]
            parts.append(part('Evidence', f"In {story['context']}, {lower_first(story['sentences'][0])}", story['source']))
        parts.append(prompt('Your goal', 'Where you want to be in a few years, and how this role gets you there'))
    return finish('motivation', parts)


def build(question, question_text, profile, fit_items, job, backend, content_result=None, requirement_id=None):
    """Example answer for one question, in the structure that suits its round."""
    if question['round'] == 'behavioural':
        return behavioural(question_text, profile, backend)
    if question['round'] == 'technical':
        return technical(question, content_result, profile, backend)
    if question['round'] == 'self_introduction':
        return introduction(question, profile, fit_items, job, backend)
    return motivation(question, requirement_id, profile, fit_items, job, backend)

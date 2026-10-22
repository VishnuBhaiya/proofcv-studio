"""Strengths and gaps: link each job requirement to confirmed profile evidence.

Runs fully locally. Two signals decide each requirement's status:
  1. Keywords: exact terms from the reviewed requirement map found in a fact.
  2. Semantic similarity: MiniLM cosine between the requirement and each fact.
Education and experience are eligibility checks that are never auto-judged;
the closest evidence is shown so the user can verify them.
"""
import json
import re
from pathlib import Path

import numpy as np

REQUIREMENTS_PATH = Path(__file__).resolve().parent / 'data' / 'job_requirements.json'
LEVELS = ('required', 'preferred', 'responsibility')
CATEGORIES = ('education', 'experience', 'skill', 'practice', 'soft')
ELIGIBILITY = ('education', 'experience')
# Cosine thresholds for all-MiniLM-L6-v2, calibrated on the labelled sample profile.
# Similarity alone mostly measures topic, so it must be high to count as strong.
STRONG_SIMILARITY = 0.65
PARTIAL_SIMILARITY = 0.52
EMPTY = {'', 'none', 'no', 'n/a'}


def load_requirements(jobs, path=REQUIREMENTS_PATH):
    """Load the requirement map and reject anything that is not traceable to the job text."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    by_id = {job['document_id']: job for job in jobs}
    if set(data['jobs']) != set(by_id):
        raise ValueError('Requirement map must cover exactly the supplied jobs.')
    seen = set()
    for job_id, requirements in data['jobs'].items():
        for item in requirements:
            if item['id'] in seen:
                raise ValueError(f"Duplicate requirement id {item['id']}.")
            seen.add(item['id'])
            if item['level'] not in LEVELS or item['category'] not in CATEGORIES:
                raise ValueError(f"Invalid level or category for {item['id']}.")
            if item['source'] not in by_id[job_id][item.get('source_field', 'description')]:
                raise ValueError(f"Source for {item['id']} is not quoted from the job.")
            if item.get('keyword_mode', 'all') not in ('any', 'all'):
                raise ValueError(f"Invalid keyword_mode for {item['id']}.")
    return data


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]


def evidence_units(profile):
    """Split a confirmed profile into small, labelled, quotable facts."""
    units = [{'source': f'skill:{i}', 'label': 'Skill', 'text': skill} for i, skill in enumerate(profile.get('skills') or []) if skill.strip()]
    for i, project in enumerate(profile.get('projects') or []):
        label = f"Project: {project['title']}"
        units += [{'source': f'project:{i}', 'label': label, 'text': s} for s in sentences(project.get('description') or '')]
        if (project.get('technologies') or '').strip():
            units.append({'source': f'project:{i}', 'label': label, 'text': 'Technologies: ' + project['technologies'].strip()})
    for field, label in (('education', 'Education'), ('experience', 'Experience'), ('achievements', 'Achievement')):
        value = (profile.get(field) or '').strip()
        if value.lower() not in EMPTY:
            units += [{'source': f'{field}:{i}', 'label': label, 'text': s} for i, block in enumerate(re.split(r'\n\s*\n', value)) for s in sentences(block)]
    units += [{'source': f'summary:{i}', 'label': 'Summary fact', 'text': s} for i, fact in enumerate(profile.get('summary_facts') or []) for s in sentences(fact)]
    return units


def keyword_pattern(term):
    return re.compile(r'(?<![a-z0-9])' + re.escape(term.lower()) + r'(?:s|es)?(?![a-z0-9])')


def assess(requirement, units, similarities):
    """Status for one requirement from keyword hits and its similarity row."""
    keywords = requirement.get('keywords') or []
    hits = {}
    for term in keywords:
        pattern = keyword_pattern(term)
        for index, unit in enumerate(units):
            if pattern.search(unit['text'].lower()):
                hits.setdefault(term, index)
                break
    if keywords:
        coverage = 1.0 if hits and requirement.get('keyword_mode') == 'any' else len(hits) / len(keywords)
    else:
        coverage = 0.0
    order = [int(i) for i in np.argsort(-similarities)] if len(units) else []
    if requirement['category'] in ELIGIBILITY:
        # Degrees and years of experience are only evidenced by that section of the profile.
        order = [i for i in order if units[i]['source'].startswith(requirement['category'] + ':')]
    best = float(similarities[order[0]]) if order else 0.0
    if requirement['category'] in ELIGIBILITY:
        status = 'verify'
    elif coverage >= 0.5 or best >= STRONG_SIMILARITY:
        status = 'strong'
    elif coverage > 0 or best >= PARTIAL_SIMILARITY:
        status = 'partial'
    else:
        status = 'gap'
    picked = list(dict.fromkeys(list(hits.values()) + [i for i in order[:2] if similarities[i] >= PARTIAL_SIMILARITY or requirement['category'] in ELIGIBILITY]))[:3]
    return {
        'id': requirement['id'], 'text': requirement['text'], 'source': requirement['source'],
        'level': requirement['level'], 'category': requirement['category'], 'status': status,
        'similarity': round(best, 3), 'keywords_found': sorted(hits), 'keywords_missing': sorted(set(keywords) - set(hits)),
        'evidence': [{**units[i], 'similarity': round(float(similarities[i]), 3)} for i in picked],
    }


def job_fit(job, requirements, profile, backend):
    """Strengths, gaps and eligibility checks for one job and one confirmed profile."""
    units = evidence_units(profile)
    if units:
        req_vectors = backend.encode([r['text'] for r in requirements])
        unit_vectors = backend.encode([u['text'] for u in units])
        matrix = np.asarray(req_vectors) @ np.asarray(unit_vectors).T
    else:
        matrix = np.zeros((len(requirements), 0))
    items = [assess(r, units, matrix[i]) for i, r in enumerate(requirements)]
    counts = {status: sum(item['status'] == status for item in items) for status in ('strong', 'partial', 'gap', 'verify')}
    return {'job': {'document_id': job['document_id'], 'title': job['title']}, 'embedding_backend': backend.name,
            'evidence_count': len(units), 'counts': counts, 'requirements': items}

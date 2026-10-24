"""Interview Coach setup: the job to prepare for, the interview date, and what to learn.

The user may pick any job in the supplied list, not only the one their CV was
tailored to. Skills to learn are the job's technical requirements that the
confirmed profile does not show (or only partly shows), most important first.
Degrees and years of experience are eligibility checks, not things to learn
before an interview, so they are never suggested.
"""
from datetime import date

from .plan import parse_date

LEARNABLE = ('skill', 'practice')
LEVEL_ORDER = {'required': 0, 'preferred': 1, 'responsibility': 2}
STATUS_ORDER = {'gap': 0, 'partial': 1}
STAGES = {'screening': 'Phone or video screening', 'technical': 'Technical interview', 'panel': 'Panel interview', 'final': 'Final interview'}
DAILY_MINUTES = (30, 60, 120, 180)
MAX_NOTES = 500
ACRONYMS = ('rag', 'nlp', 'llm')


def skills_to_learn(fit_items):
    """Technical requirements the profile does not show yet: required gaps first, partial matches last."""
    missing = [r for r in fit_items if r['category'] in LEARNABLE and r['status'] in STATUS_ORDER]
    missing.sort(key=lambda r: (STATUS_ORDER[r['status']], LEVEL_ORDER.get(r['level'], 3)))
    return [{'id': r['id'], 'text': r['text'], 'level': r['level'], 'status': r['status']} for r in missing]


def focus(job, jobs):
    """A short tag that tells apart jobs with the same title, from the job's id ('healthcare', 'rag agent')."""
    if sum(j['title'] == job['title'] for j in jobs) < 2:
        return None
    words = [w.upper() if w in ACRONYMS else w for w in job['document_id'].split('_') if w not in ('ml', 'ai', 'engineer', 'scientist')]
    text = ' '.join(words)
    return text[:1].upper() + text[1:] or None


def job_list(jobs, matched, target_id):
    """Every supplied job, with its match score when it was one of the user's top matches."""
    scores = {m['document_id']: m['score'] for m in matched}
    return [{'document_id': j['document_id'], 'title': j['title'], 'location': j.get('location'), 'focus': focus(j, jobs),
             'match_score': scores.get(j['document_id']), 'cv_target': j['document_id'] == target_id} for j in jobs]


def validate(data, job_ids, learnable_ids, today=None):
    """A clean setup from the submitted form, or ValueError with what to fix."""
    if data.get('job') not in job_ids:
        raise ValueError('Choose a job from the list.')
    when = parse_date(data.get('interview_date'), today or date.today())
    learn = data.get('learn_skills') or []
    if not isinstance(learn, list) or any(skill not in learnable_ids for skill in learn):
        raise ValueError('Choose skills to learn from the list for this job.')
    if data.get('stage') not in STAGES:
        raise ValueError('Choose the interview stage.')
    if data.get('daily_minutes') not in DAILY_MINUTES:
        raise ValueError('Choose how much time you have each day.')
    notes = str(data.get('notes') or '').strip()
    if len(notes) > MAX_NOTES:
        raise ValueError(f'Keep the notes under {MAX_NOTES} characters.')
    return {'job': data['job'], 'interview_date': when.isoformat(), 'learn_skills': list(dict.fromkeys(learn)),
            'stage': data['stage'], 'daily_minutes': data['daily_minutes'], 'notes': notes}

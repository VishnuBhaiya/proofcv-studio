"""HTTP entry point for the Interview Coach module."""
from urllib.parse import parse_qs, urlsplit

from .fit import job_fit, load_requirements

ROUNDS = ['self_introduction', 'behavioural', 'technical', 'motivation_fit']
_requirements = None


def requirements(jobs):
    global _requirements
    if _requirements is None:
        _requirements = load_requirements(jobs)
    return _requirements


def readiness(state):
    """The core facts the coach needs: a confirmed profile and the user's matched jobs."""
    confirmed = state.get('confirmed_revision') is not None and state['confirmed_revision'] == state['revision']
    results = (state.get('retrieval') or {}).get('results') or []
    draft = state.get('draft')
    return {
        'workspace_id': state['id'],
        'profile_confirmed': confirmed,
        'matched_jobs': [{'document_id': r['document_id'], 'title': r['title'], 'score': r['score']} for r in results],
        'target_job': {'document_id': draft['job']['document_id'], 'title': draft['job']['title']} if draft else None,
        'rounds': ROUNDS,
    }


def fit(service, state, job_id=None):
    """Strengths and gaps for the target job, or another of the user's matched jobs."""
    ready = readiness(state)
    if not ready['profile_confirmed'] or not state.get('confirmed_profile'):
        raise ValueError('Confirm your profile before preparing for an interview.')
    allowed = [j['document_id'] for j in ready['matched_jobs']] + ([ready['target_job']['document_id']] if ready['target_job'] else [])
    job_id = job_id or (ready['target_job'] or {}).get('document_id')
    if not job_id:
        raise ValueError('Choose a target job first.')
    if job_id not in allowed:
        raise ValueError('Choose one of your matched jobs.')
    data = requirements(service.jobs)
    job = next(j for j in service.jobs if j['document_id'] == job_id)
    return {**job_fit(job, data['jobs'][job_id], state['confirmed_profile'], service.retriever.backend),
            'review_status': data['review_status']}


def handle_get(service, url):
    """GET /api/interview/<workspace_id>/status and /api/interview/<workspace_id>/fit[?job=<document_id>]"""
    split = urlsplit(url)
    parts = split.path.strip('/').split('/')
    if len(parts) == 4 and parts[3] == 'status':
        return readiness(service.store.get(parts[2]))
    if len(parts) == 4 and parts[3] == 'fit':
        return fit(service, service.store.get(parts[2]), (parse_qs(split.query).get('job') or [None])[0])
    raise ValueError('Endpoint not found.')

"""HTTP entry point for the Interview Coach module."""
import base64
import binascii
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import attempts, content, factcheck, model_answer, speech, star
from .fit import job_fit, load_requirements
from .questions import ROUNDS as QUESTION_ROUNDS, load_bank, pick_questions

ROUNDS = list(QUESTION_ROUNDS)
_requirements = None
_bank = None
# The page requests fit and questions together; MiniLM's first load is not safe to run twice at once.
_embedding_lock = threading.Lock()


def requirements(jobs):
    global _requirements
    if _requirements is None:
        _requirements = load_requirements(jobs)
    return _requirements


def bank():
    global _bank
    if _bank is None:
        _bank = load_bank()
    return _bank


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
    with _embedding_lock:
        result = job_fit(job, data['jobs'][job_id], state['confirmed_profile'], service.retriever.backend)
    return {**result, 'review_status': data['review_status']}


def questions(service, state, job_id=None):
    """Interview questions per round for the same job that fit() resolves."""
    result = fit(service, state, job_id)
    job = next(j for j in service.jobs if j['document_id'] == result['job']['document_id'])
    keywords = {r['id']: r.get('keywords', []) for r in requirements(service.jobs)['jobs'][job['document_id']]}
    with _embedding_lock:
        return pick_questions(job, result['requirements'], keywords, state['confirmed_profile'], bank(), service.retriever.backend)


MAX_AUDIO_BYTES = 5_000_000
ROUND_TARGET_SECONDS = {'behavioural': 90, 'technical': 75, 'motivation_fit': 60}


def answer(service, state, data):
    """Transcribe one spoken answer locally and measure its delivery. Audio is not stored."""
    question = next((q for q in bank()['questions'] if q['id'] == data.get('question_id')), None)
    if not question:
        raise ValueError('Unknown question.')
    try:
        audio = base64.b64decode(data.get('audio') or '', validate=True)
    except (binascii.Error, TypeError):
        raise ValueError('Audio must be base64 encoded.')
    if not 0 < len(audio) <= MAX_AUDIO_BYTES:
        raise ValueError('Recording is empty or longer than about five minutes.')
    target = question.get('seconds') or ROUND_TARGET_SECONDS.get(question['round'])
    result = speech.transcriber().transcribe(audio)
    response = {'workspace_id': state['id'], 'question_id': question['id'], 'round': question['round'], 'transcript': result['text'], 'words': result['words'],
                'model': result['model'], 'target_seconds': target, 'delivery': speech.delivery(result['words'], result['duration'], target)}
    backend = service.retriever.backend
    confirmed = readiness(state)['profile_confirmed'] and bool(state.get('confirmed_profile'))
    try:
        job_fit_result = fit(service, state, data.get('job')) if confirmed else None
    except ValueError:
        job_fit_result = None  # No target job yet: feedback still works, the example answer needs a job.
    with _embedding_lock:
        if question['round'] == 'behavioural':
            response['star'] = star.analyse(result['text'], backend)
        if question.get('key_points'):
            response['content'] = content.score(result['text'], question['key_points'], backend)
        if confirmed:
            response['fact_check'] = factcheck.check(result['text'], state['confirmed_profile'], backend, personal_story=question['round'] != 'technical')
        if job_fit_result:
            response['example_answer'] = model_answer.build(question, data.get('question_text') or question['text'], state['confirmed_profile'],
                                                            job_fit_result['requirements'], job_fit_result['job'], backend,
                                                            response.get('content'), data.get('requirement_id'))
    response['progress'] = attempt_store(service).record(state['id'], question['id'], result['text'], attempts.summarise(response))
    return response


_attempt_stores = {}


def attempt_store(service):
    """The module's own attempt database, next to the core database."""
    path = str(Path(service.store.path).parent / 'interview.sqlite3')
    if path not in _attempt_stores:
        _attempt_stores[path] = attempts.AttemptStore(path)
    return _attempt_stores[path]


def handle_post(service, path, data):
    """POST /api/interview/<workspace_id>/answer"""
    parts = path.strip('/').split('/')
    if len(parts) == 4 and parts[3] == 'answer':
        return answer(service, service.store.get(parts[2]), data)
    raise ValueError('Endpoint not found.')


def handle_get(service, url):
    """GET /api/interview/<workspace_id>/(status|fit|questions)[?job=<document_id>] and .../attempts?question=<id>"""
    split = urlsplit(url)
    parts = split.path.strip('/').split('/')
    query = parse_qs(split.query)
    job_id = (query.get('job') or [None])[0]
    if len(parts) == 4 and parts[3] == 'attempts':
        state = service.store.get(parts[2])
        if 'question' in query:
            return attempt_store(service).history(state['id'], query['question'][0])
        return attempt_store(service).overview(state['id'])
    if len(parts) == 4 and parts[3] == 'status':
        return readiness(service.store.get(parts[2]))
    if len(parts) == 4 and parts[3] == 'fit':
        return fit(service, service.store.get(parts[2]), job_id)
    if len(parts) == 4 and parts[3] == 'questions':
        return questions(service, service.store.get(parts[2]), job_id)
    raise ValueError('Endpoint not found.')

"""HTTP entry point for the Interview Coach module."""
import base64
import binascii
import threading
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import attempts, cheatsheet, content, evaluate, factcheck, followup, mock, model_answer, plan, slides, speech, star, voice
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
QUIET_RMS_DB = -45  # A real test recording averaged -22.5 dB; below -45 speech is hard to recognise.
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
    asked = data.get('follow_up') if isinstance(data.get('follow_up'), dict) else None  # Answering an interviewer follow-up.
    depth = int(asked.get('depth', 1)) if asked else 0
    target = followup.FOLLOW_UP_SECONDS if asked else question.get('seconds') or ROUND_TARGET_SECONDS.get(question['round'])
    job_title = next((j['title'] for j in service.jobs if j['document_id'] == data.get('job')), None) or ((state.get('draft') or {}).get('job') or {}).get('title')
    result = speech.transcriber(recognition(data.get('recognition'))).transcribe(audio, speech.expected_words(state.get('confirmed_profile') or state.get('profile'), job_title))
    response = {'workspace_id': state['id'], 'question_id': question['id'], 'round': question['round'], 'follow_up_of': asked['question'] if asked else None,
                'transcript': result['text'], 'words': result['words'],
                'model': result['model'], 'target_seconds': target, 'delivery': speech.delivery(result['words'], result['duration'], target)}
    if result.get('audio', {}).get('rms_db', 0) < QUIET_RMS_DB:
        response['delivery']['notes'].insert(0, 'Your microphone level was very low, which makes the transcript less accurate. Move closer or check the input device in your system sound settings.')
    response['audio'] = result.get('audio')
    response['recognition'] = speech.recognition_check(result['words'])
    if response['recognition']['unsure']:
        response['delivery']['notes'].insert(0, f"Speech recognition was unsure about {round(response['recognition']['unsure_share'] * 100)}% of your words "
                                                '(underlined in the transcript), so the scores may be off. Speak a little slower and closer to the microphone, '
                                                'or switch to Accurate recognition.')
    backend = service.retriever.backend
    confirmed = readiness(state)['profile_confirmed'] and bool(state.get('confirmed_profile'))
    try:
        job_fit_result = fit(service, state, data.get('job')) if confirmed else None
    except ValueError:
        job_fit_result = None  # No target job yet: feedback still works, the example answer needs a job.
    with _embedding_lock:
        # A follow-up answer is one part of a story, so it gets no STAR check or example answer;
        # a follow-up about a missed key point is scored on that point only.
        if question['round'] == 'behavioural' and not asked:
            response['star'] = star.analyse(result['text'], backend)
        key_points = ([asked['key_point']] if asked.get('key_point') else []) if asked else question.get('key_points')
        if question['round'] == 'self_introduction' and not asked and job_fit_result:
            # Introductions have no fixed answer: what they should cover comes from the confirmed profile and the job.
            key_points = model_answer.intro_points(question, state['confirmed_profile'], job_fit_result['requirements'], job_fit_result['job'], backend)
        if key_points:
            response['content'] = content.score(result['text'], key_points, backend)
        if confirmed:
            response['fact_check'] = factcheck.check(result['text'], state['confirmed_profile'], backend, personal_story=question['round'] != 'technical')
        if job_fit_result and not asked:
            response['example_answer'] = model_answer.build(question, data.get('question_text') or question['text'], state['confirmed_profile'],
                                                            job_fit_result['requirements'], job_fit_result['job'], backend,
                                                            response.get('content'), data.get('requirement_id'))
        if job_fit_result and data.get('rehearsal'):
            response['slide_coverage'] = slide_coverage(result['text'], slides.build(state['confirmed_profile'], job_fit_result['requirements'], job_fit_result['job'], backend), backend)
    summary = attempts.summarise(response)
    parts = mock.components(summary)
    response['score'] = {'overall': mock.overall(parts), 'components': parts}
    response['progress'] = attempt_store(service).record(state['id'], f"{question['id']}:follow-up" if asked else question['id'], result['text'], summary)
    in_mock = bool(data.get('mock_session'))
    # In a mock interview the interviewer cross-questions once per question; in practice, up to MAX_DEPTH times.
    response['follow_up'] = None if in_mock and asked else followup.follow_up(question, response, depth)
    if in_mock:
        attempt_store(service).link_answer(state['id'], data['mock_session'], int(data.get('mock_position', -1)), response['progress']['id'],
                                           follow_up_question=asked['question'] if asked else None)
    return response


def start_mock(service, state, data):
    """A new five-question mock interview for the target job or a matched job."""
    picked = questions(service, state, data.get('job'))
    return attempt_store(service).create_session(state['id'], picked['job'], mock.pick(picked['rounds']))


def mock_report(service, state, session_id):
    store = attempt_store(service)
    session = store.session(state['id'], session_id)
    return mock.report(session, store.get(state['id'], [int(v['id'] if isinstance(v, dict) else v) for v in session['answers'].values()]))


def mock_list(service, state):
    """Every mock interview with its score, newest first, for the Reports tab."""
    store = attempt_store(service)
    listed = []
    for session in store.sessions(state['id']):
        item = {'id': session['id'], 'created_at': session['created_at'], 'job': session['job'], 'total': len(session['questions'])}
        try:
            result = mock_report(service, state, session['id'])
            item.update(overall=result['overall'], band=result['band'], answered=result['answered'], cross_questioning=result['cross_questioning'])
        except ValueError:
            item.update(overall=None, band='Not started', answered=0, cross_questioning=None)
        listed.append(item)
    return listed


def slide_coverage(transcript, deck, backend):
    """Which slides the spoken rehearsal actually talked about, using the key-point matcher."""
    covered = [s for s in deck['slides'] if s['point']]
    scored = content.score(transcript, [s['point'] for s in covered], backend)['key_points'] if covered else []
    items = [{'title': s['title'], 'status': k['status'], 'quote': k['quote']} for s, k in zip(covered, scored)]
    missed = [i['title'] for i in items if i['status'] == 'missed']
    notes = [f"You didn't talk about: {', '.join(missed)}." if missed else 'You talked about every slide.']
    return {'slides': items, 'covered': sum(i['status'] != 'missed' for i in items), 'total': len(items), 'notes': notes}


def deck(service, state, job_id=None):
    """The self-introduction deck for the target job or a matched job."""
    result = fit(service, state, job_id)
    with _embedding_lock:
        return slides.build(state['confirmed_profile'], result['requirements'], result['job'], service.retriever.backend)


def cheat_sheet(service, state, job_id=None):
    """The one-page interview-day sheet for the target job or a matched job, from practice so far."""
    picked = questions(service, state, job_id)
    result = fit(service, state, picked['job']['document_id'])
    by_id = {q['id']: q for qs in picked['rounds'].values() for q in qs}
    latest = next((m for m in mock_list(service, state) if m['job']['document_id'] == result['job']['document_id'] and m['overall'] is not None), None)
    with _embedding_lock:
        return cheatsheet.build(state['confirmed_profile'], result['requirements'], result['job'], attempt_store(service).all(state['id']),
                                by_id, service.retriever.backend, readiness=latest)


def practice_plan(service, state, job_id=None, today=None):
    """The countdown plan for a job, or just the job when no interview date is set yet."""
    picked = questions(service, state, job_id)
    job = picked['job']['document_id']
    store = attempt_store(service)
    when = store.interview_date(state['id'], job)
    if when is None:
        return {'job': picked['job'], 'interview_date': None}
    today = today or date.today()
    flat = [q for r in ROUNDS for q in picked['rounds'].get(r, [])]
    frozen = {date.fromisoformat(day): ids for day, ids in store.plan_days(state['id'], job).items()}
    mocks = [m for m in mock_list(service, state) if m['job']['document_id'] == job]
    result = plan.build(date.fromisoformat(when), today, flat, store.all(state['id']), mocks, frozen)
    if today not in frozen and plan.todays_questions(result):
        store.freeze_day(state['id'], job, today.isoformat(), plan.todays_questions(result))
    return {'job': picked['job'], **result}


def set_plan(service, state, data, today=None):
    picked = questions(service, state, data.get('job'))
    chosen = data.get('interview_date')
    when = None if chosen is None else plan.parse_date(chosen, today or date.today()).isoformat()
    attempt_store(service).set_interview_date(state['id'], picked['job']['document_id'], when)
    return practice_plan(service, state, picked['job']['document_id'], today)


def recognition(requested):
    """The Whisper model to use: the user's pick if it is installed (nothing is ever downloaded here)."""
    options = speech.recognition_options()
    if requested is None:
        return options['default']
    if not any(o['id'] == requested and o['installed'] for o in options['options']):
        raise ValueError('That speech recognition model is not installed.')
    return requested


def speech_settings(service):
    """Which read-aloud voice and recognition models this computer has."""
    return {'voice': {'id': voice.VOICE, 'label': voice.VOICE_LABEL, 'available': voice.available(runtime_dir(service))},
            'recognition': speech.recognition_options()}


def runtime_dir(service):
    return Path(service.store.path).parent


_attempt_stores = {}


def attempt_store(service):
    """The module's own attempt database, next to the core database."""
    path = str(runtime_dir(service) / 'interview.sqlite3')
    if path not in _attempt_stores:
        _attempt_stores[path] = attempts.AttemptStore(path)
    return _attempt_stores[path]


def handle_post(service, path, data):
    """POST /api/interview/<workspace_id>/answer and /api/interview/<workspace_id>/mock"""
    parts = path.strip('/').split('/')
    if len(parts) == 4 and parts[3] == 'answer':
        return answer(service, service.store.get(parts[2]), data)
    if len(parts) == 4 and parts[3] == 'mock':
        return start_mock(service, service.store.get(parts[2]), data)
    if len(parts) == 4 and parts[3] == 'plan':
        return set_plan(service, service.store.get(parts[2]), data)
    if len(parts) == 4 and parts[3] == 'speak':
        service.store.get(parts[2])
        speaker = voice.speaker(runtime_dir(service))
        if speaker is None:
            raise ValueError('The natural voice is not installed.')
        return speaker.wav(data.get('text'))
    if len(parts) == 4 and parts[3] == 'evaluation-sample':
        service.store.get(parts[2])
        try:
            audio = base64.b64decode(data.get('audio') or '', validate=True)
        except (binascii.Error, TypeError):
            raise ValueError('Audio must be base64 encoded.')
        if not 0 < len(audio) <= MAX_AUDIO_BYTES:
            raise ValueError('Recording is empty or too long.')
        directory = evaluate.samples_dir(service.store.path)
        evaluate.save_sample(directory, data.get('script_id'), audio, evaluate.load_scripts())
        return {'recorded': evaluate.recorded(directory), 'seconds': evaluate.lengths(directory), 'min_seconds': evaluate.MIN_SECONDS}
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
    if len(parts) == 4 and parts[3] == 'plan':
        return practice_plan(service, service.store.get(parts[2]), job_id)
    if len(parts) == 4 and parts[3] == 'speech':
        service.store.get(parts[2])
        return speech_settings(service)
    if len(parts) == 4 and parts[3] == 'status':
        return readiness(service.store.get(parts[2]))
    if len(parts) == 4 and parts[3] == 'fit':
        return fit(service, service.store.get(parts[2]), job_id)
    if len(parts) == 4 and parts[3] == 'questions':
        return questions(service, service.store.get(parts[2]), job_id)
    if len(parts) == 4 and parts[3] == 'slides':
        return deck(service, service.store.get(parts[2]), job_id)
    if len(parts) == 4 and parts[3] == 'evaluation':
        service.store.get(parts[2])
        scripts = evaluate.load_scripts()
        return {'scripts': [{'id': s['id'], 'question_id': s['question_id'], 'text': ' '.join(t for _, t in s['sentences'])} for s in scripts['scripts']],
                'recorded': evaluate.recorded(evaluate.samples_dir(service.store.path)), 'seconds': evaluate.lengths(evaluate.samples_dir(service.store.path)), 'min_seconds': evaluate.MIN_SECONDS}
    if len(parts) == 4 and parts[3] == 'mock':
        return mock_list(service, service.store.get(parts[2]))
    if len(parts) == 5 and parts[3] == 'mock':
        return attempt_store(service).session(service.store.get(parts[2])['id'], parts[4])
    if len(parts) == 6 and parts[3] == 'mock' and parts[5] in ('report', 'report.pdf'):
        state = service.store.get(parts[2])
        result = mock_report(service, state, parts[4])
        if parts[5] == 'report':
            return result
        return mock.render_pdf(result, ((state.get('confirmed_profile') or state.get('profile') or {}).get('name') or 'Candidate'))
    if len(parts) == 4 and parts[3] in ('cheatsheet', 'cheatsheet.pdf'):
        sheet = cheat_sheet(service, service.store.get(parts[2]), job_id)
        return sheet if parts[3] == 'cheatsheet' else cheatsheet.render_pdf(sheet)
    if len(parts) == 4 and parts[3] == 'slides.pdf':
        return slides.render_pdf(deck(service, service.store.get(parts[2]), job_id))
    raise ValueError('Endpoint not found.')

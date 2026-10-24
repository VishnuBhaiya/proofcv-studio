"""HTTP entry point for the Interview Coach module."""
import base64
import binascii
import re
import threading
import time
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import attempts, cheatsheet, content, diagnostic, evaluate, factcheck, followup, gemini_speech, mock, model_answer, plan, resources, setup, slides, speech, star, voice
from ..gemini import GeminiError
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


def status(service, state):
    """Readiness plus every job the user can prepare for and their saved setup."""
    ready = readiness(state)
    return {**ready, 'jobs': setup.job_list(service.jobs, ready['matched_jobs'], (ready['target_job'] or {}).get('document_id')),
            'setup': attempt_store(service).setup(state['id'])}


def fit(service, state, job_id=None):
    """Strengths, gaps and skills to learn for any supplied job; by default the one chosen in setup, else the CV's job."""
    ready = readiness(state)
    if not ready['profile_confirmed'] or not state.get('confirmed_profile'):
        raise ValueError('Confirm your profile before preparing for an interview.')
    job_id = job_id or (attempt_store(service).setup(state['id']) or {}).get('job') or (ready['target_job'] or {}).get('document_id')
    if not job_id:
        raise ValueError('Choose a job to prepare for.')
    job = next((j for j in service.jobs if j['document_id'] == job_id), None)
    if not job:
        raise ValueError('Choose a job from the list.')
    data = requirements(service.jobs)
    with _embedding_lock:
        result = job_fit(job, data['jobs'][job_id], state['confirmed_profile'], service.retriever.backend)
    return {**result, 'review_status': data['review_status'], 'to_learn': setup.skills_to_learn(result['requirements'])}


def save_setup(service, state, data, today=None):
    """Check and store the setup form; its date and daily time drive the plan."""
    chosen = fit(service, state, data.get('job') if isinstance(data.get('job'), str) else None) if data.get('job') in {j['document_id'] for j in service.jobs} else None
    clean = setup.validate(data, {j['document_id'] for j in service.jobs}, {s['id'] for s in (chosen or {}).get('to_learn', [])}, today)
    attempt_store(service).save_setup(state['id'], clean)
    return status(service, state)


def questions(service, state, job_id=None):
    """Interview questions per round for the same job that fit() resolves."""
    result = fit(service, state, job_id)
    job = next(j for j in service.jobs if j['document_id'] == result['job']['document_id'])
    keywords = {r['id']: r.get('keywords', []) for r in requirements(service.jobs)['jobs'][job['document_id']]}
    with _embedding_lock:
        picked = pick_questions(job, result['requirements'], keywords, state['confirmed_profile'], bank(), service.retriever.backend)
    # Once there is a skill check for this job, its ten questions are the technical round, so Practice,
    # the mock interview and the plan all work on the same job-specific topics.
    check = attempt_store(service).latest_diagnostic(state['id'], job['document_id'])
    if check:
        picked['rounds']['technical'] = [{'id': q['id'], 'round': 'technical', 'text': q['text'], 'reason': f"From your skill check: {q['topic']}",
                                          'requirement': {k: q['requirement'][k] for k in ('id', 'text', 'status')}} for q in check['questions']]
    return picked


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
    check = check_position(service, state, data, question) if data.get('diagnostic') else None
    depth = int(asked.get('depth', 1)) if asked else 0
    target = followup.FOLLOW_UP_SECONDS if asked else question.get('seconds') or ROUND_TARGET_SECONDS.get(question['round'])
    job_title = next((j['title'] for j in service.jobs if j['document_id'] == data.get('job')), None) or ((state.get('draft') or {}).get('job') or {}).get('title')
    choice = recognition(service, data.get('recognition'))
    local_model = speech.recognition_options()['default'] if choice == 'gemini' else choice
    prompt = speech.expected_words(state.get('confirmed_profile') or state.get('profile'), job_title)
    started = time.monotonic()
    online_job = gemini_speech.start(service.model, audio, prompt.replace(speech.FILLER_PROMPT, '').strip()) if choice == 'gemini' else None
    # Whisper always runs: even when Gemini writes the transcript, pace, pauses and fillers come from Whisper's word timings.
    result = speech.transcriber(local_model).transcribe(audio, prompt)
    online, online_note = False, None
    if online_job:
        try:
            heard = online_job.result(timeout=max(1, gemini_speech.DEADLINE_SECONDS - (time.monotonic() - started)))
            if heard or not result['text']:
                result = {**result, 'text': heard, 'model': f"{service.model.name} (transcript) + whisper-{local_model} (timing)"}
                online = True
            else:
                online_note = 'Gemini heard no speech, so the local Whisper transcript was used.'
        except GeminiError as error:
            online_note = f'Gemini could not transcribe this answer ({error}), so the local Whisper transcript was used.'
        except FutureTimeout:
            online_note = f'Gemini took longer than {gemini_speech.DEADLINE_SECONDS} seconds, so the local Whisper transcript was used.'
    response = {'workspace_id': state['id'], 'question_id': question['id'], 'round': question['round'], 'follow_up_of': asked['question'] if asked else None,
                'transcript': result['text'], 'words': [] if online else result['words'],
                'model': result['model'], 'target_seconds': target, 'delivery': speech.delivery(result['words'], result['duration'], target)}
    if online_note:
        response['delivery']['notes'].insert(0, online_note)
    if result.get('audio', {}).get('rms_db', 0) < QUIET_RMS_DB:
        response['delivery']['notes'].insert(0, 'Your microphone level was very low, which makes the transcript less accurate. Move closer or check the input device in your system sound settings.')
    response['audio'] = result.get('audio')
    # Gemini gives no per-word confidence, so the unsure-word check applies to Whisper transcripts only.
    response['recognition'] = {**speech.recognition_check([] if online else result['words']), 'source': 'gemini' if online else 'whisper'}
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
    in_check = bool(data.get('diagnostic'))
    # In a mock interview the interviewer cross-questions once per question; in practice, up to MAX_DEPTH times;
    # a skill check is a test, so it asks no follow-ups.
    response['follow_up'] = None if (in_mock and asked) or in_check else followup.follow_up(question, response, depth)
    if in_check:
        link_check_answer(service, state, *check, response)
    if in_mock:
        attempt_store(service).link_answer(state['id'], data['mock_session'], int(data.get('mock_position', -1)), response['progress']['id'],
                                           follow_up_question=asked['question'] if asked else None)
    return response


def check_position(service, state, data, question):
    """The skill check and position an answer belongs to, checked before anything is scored or saved."""
    session = attempt_store(service).diagnostic(state['id'], data['diagnostic'])
    position = int(data.get('diagnostic_position', -1))
    if not 0 <= position < len(session['questions']) or session['questions'][position]['id'] != question['id']:
        raise ValueError('Question is not part of this skill check.')
    if session['finished_at']:
        raise ValueError('This skill check is finished. Start a new one to answer again.')
    return session, position


def link_check_answer(service, state, session, position, response):
    """Attach an answer to its skill check, keeping which key points it covered for the study list."""
    points = (response.get('content') or {}).get('key_points', [])
    attempt_store(service).link_diagnostic_answer(state['id'], session['id'], position, response['progress']['id'],
                                 *[[k['text'] for k in points if k['status'] == status] for status in ('covered', 'partial', 'missed')])


def check_view(service, state, session):
    """A skill check with its evaluation so far."""
    store = attempt_store(service)
    attempts_by_id = store.get(state['id'], [int(v['id']) for v in session['answers'].values()])
    return {**session, 'compulsory': diagnostic.COMPULSORY, 'evaluation': diagnostic.evaluate(session, attempts_by_id, session['job'].get('learn_skills', []))}


def current_job_id(service, state, job_id=None):
    """The job the coach is preparing for, without the cost of a fit: the request's, the setup's, else the CV's."""
    return job_id or (attempt_store(service).setup(state['id']) or {}).get('job') or (readiness(state)['target_job'] or {}).get('document_id')


def start_check(service, state, data):
    """Resume the unfinished skill check for this job, or start a new one (restart: true starts over)."""
    result = fit(service, state, data.get('job'))
    job_id = result['job']['document_id']
    store = attempt_store(service)
    current = store.latest_diagnostic(state['id'], job_id)
    if current and not current['finished_at'] and not data.get('restart'):
        return check_view(service, state, current)
    saved = store.setup(state['id']) or {}
    learn_ids = saved.get('learn_skills', []) if saved.get('job') == job_id else []
    with _embedding_lock:
        picked = diagnostic.pick(bank(), result['requirements'], learn_ids, service.retriever.backend)
    if not picked:
        raise ValueError('No technical questions fit this job yet.')
    learn = [r['text'] for r in result['requirements'] if r['id'] in learn_ids]
    return check_view(service, state, store.create_diagnostic(state['id'], {**result['job'], 'learn_skills': learn}, picked))


def finish_check(service, state, check_id):
    store = attempt_store(service)
    session = store.diagnostic(state['id'], check_id)
    done = sum(str(i) in session['answers'] for i in range(min(diagnostic.COMPULSORY, len(session['questions']))))
    if done < min(diagnostic.COMPULSORY, len(session['questions'])):
        raise ValueError(f'Answer the {diagnostic.COMPULSORY} compulsory questions first ({done} of {diagnostic.COMPULSORY} done).')
    return check_view(service, state, store.finish_diagnostic(state['id'], check_id))


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


def plan_topics(check):
    """The plan's topics: one per skill-check question, plus chosen skills to learn that had no question of their own."""
    by_id = {q['id']: q for q in bank()['questions']}
    topics = []
    for position, question in enumerate(check['questions']):
        covered = set((check['answers'].get(str(position)) or {}).get('covered', []))
        bank_question = by_id.get(question['id'], {})
        topics.append({'id': question['id'], 'question_id': question['id'], 'topic': question['topic'], 'question': question['text'],
                       'requirement': question['requirement'], 'learning': question.get('learning', False),
                       'key_points': [{'text': k, 'covered': k in covered} for k in bank_question.get('key_points', [])],
                       'resources': resources.for_text(question['topic'], ' '.join(bank_question.get('tags') or []))})
    asked = {q['requirement']['text'] for q in check['questions'] if q.get('learning')}
    for i, skill in enumerate(s for s in check['job'].get('learn_skills', []) if s not in asked):
        topics.append({'id': f'learn-{i}', 'question_id': None, 'topic': skill, 'question': None, 'requirement': {'text': skill},
                       'learning': True, 'key_points': [], 'resources': resources.for_text(skill)})
    return topics


def practice_plan(service, state, job_id=None, today=None):
    """The adaptive day-by-day plan for the setup's job, once its skill check is finished."""
    store = attempt_store(service)
    saved = store.setup(state['id'])
    job_id = current_job_id(service, state, job_id)
    if not saved or saved['job'] != job_id:
        return {'job': {'document_id': job_id}, 'status': 'needs_setup', 'interview_date': None}
    check = store.latest_diagnostic(state['id'], job_id)
    if not check or not check['finished_at']:
        return {'job': {'document_id': job_id}, 'status': 'needs_check', 'interview_date': saved['interview_date']}
    mocks = [m for m in mock_list(service, state) if m['job']['document_id'] == job_id]
    finished = [m for m in mocks if m['answered'] and m['answered'] == m['total']]
    next_steps = mock_report(service, state, finished[0]['id'])['next_steps'] if finished else []
    result = plan.build(plan.local_day(check['finished_at']), today or date.today(), date.fromisoformat(saved['interview_date']), plan_topics(check),
                        store.all(state['id']), mocks, store.plan_ticks(state['id'], job_id), saved['daily_minutes'], saved['stage'], next_steps,
                        since=check['finished_at'])
    return {'job': {k: check['job'][k] for k in ('document_id', 'title')}, 'skill_check': check['id'], **result}


def tick_plan(service, state, data):
    """Mark a study, focus or cheat-sheet task done (or not) for a day of the plan."""
    saved = attempt_store(service).setup(state['id'])
    if not saved:
        raise ValueError('Set up your interview preparation first.')
    try:
        day = date.fromisoformat(data.get('date'))
    except (TypeError, ValueError):
        raise ValueError('Give the day as YYYY-MM-DD.')
    key = str(data.get('key') or '')
    if not re.fullmatch(r'(study|focus):[A-Za-z0-9_-]{1,60}|cheatsheet', key):
        raise ValueError('Unknown plan task.')
    attempt_store(service).tick(state['id'], saved['job'], day.isoformat(), key, bool(data.get('done')))
    return practice_plan(service, state, saved['job'])


def recognition_settings(service):
    """Installed local Whisper models, plus Gemini when the server has a key. The default is always local:
    Accurate (small.en) when it is installed. Gemini is used only when a request asks for it."""
    options = speech.recognition_options()
    if gemini_speech.configured(service.model):
        return {**options, 'options': [*options['options'], {'id': 'gemini', 'label': gemini_speech.LABEL, 'installed': True}]}
    return options


def recognition(service, requested):
    """What turns speech into text: the user's pick if it is available (nothing is ever downloaded here)."""
    options = recognition_settings(service)
    if requested is None:
        return options['default']
    if not any(o['id'] == requested and o['installed'] for o in options['options']):
        raise ValueError('That speech recognition model is not installed.')
    return requested


def speech_settings(service):
    """Which read-aloud voice and recognition models this computer has."""
    return {'voice': {'id': voice.VOICE, 'label': voice.VOICE_LABEL, 'available': voice.available(runtime_dir(service))},
            'recognition': recognition_settings(service)}


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
    if len(parts) == 4 and parts[3] == 'skill-check':
        return start_check(service, service.store.get(parts[2]), data)
    if len(parts) == 6 and parts[3] == 'skill-check' and parts[5] == 'finish':
        return finish_check(service, service.store.get(parts[2]), parts[4])
    if len(parts) == 4 and parts[3] == 'setup':
        return save_setup(service, service.store.get(parts[2]), data)
    if len(parts) == 5 and parts[3] == 'plan' and parts[4] == 'tick':
        return tick_plan(service, service.store.get(parts[2]), data)
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
    if len(parts) == 4 and parts[3] == 'skill-check':
        state = service.store.get(parts[2])
        session = attempt_store(service).latest_diagnostic(state['id'], current_job_id(service, state, job_id))
        return {'session': check_view(service, state, session) if session else None}
    if len(parts) == 4 and parts[3] == 'speech':
        service.store.get(parts[2])
        return speech_settings(service)
    if len(parts) == 4 and parts[3] == 'status':
        return status(service, service.store.get(parts[2]))
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

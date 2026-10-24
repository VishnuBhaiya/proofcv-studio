"""Interview Coach HTTP routes with synthetic local data and no model requests."""
import base64
import json
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest import mock
from .. import test_http
from . import content, factcheck, gemini_speech, model_answer, speech, star, voice
from .test_model_answer import FakeStar
from ..gemini import GeminiError
from .test_speech import words
from ..retrieval import InspectableHashEmbeddingBackend, JobRetriever
from .test_fit import PROFILE


class InterviewRouteTests(unittest.TestCase):
    # Reuse the real local server fixture without re-running the core HTTP tests.
    tearDown, request = test_http.HTTPTests.tearDown, test_http.HTTPTests.request

    def setUp(self):
        test_http.HTTPTests.setUp(self)
        # The fixture's Gemini key is a placeholder: no test may send audio to Google. Gemini has its own test below.
        patcher = mock.patch.object(gemini_speech, 'configured', return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self):
        code, body = self.request('POST', '/api/workspaces', {'label': 'Coach test'}, {'Content-Type': 'application/json'})
        self.assertEqual(code, 201)
        return json.loads(body)

    def test_status_reports_readiness_for_new_workspace(self):
        workspace = self.create()
        code, body = self.request('GET', f"/api/interview/{workspace['id']}/status")
        self.assertEqual(code, 200)
        status = json.loads(body)
        self.assertEqual(status['workspace_id'], workspace['id'])
        self.assertFalse(status['profile_confirmed'])
        self.assertEqual(status['matched_jobs'], [])
        self.assertIsNone(status['target_job'])
        self.assertEqual(status['rounds'], ['self_introduction', 'behavioural', 'technical', 'motivation_fit'])

    def test_status_reports_matched_and_target_jobs(self):
        state = self.service.store.get(self.create()['id'])
        job = {'document_id': 'rag_agent_engineer', 'title': 'AI Engineer'}
        state.update(confirmed_revision=state['revision'],
                     retrieval={'results': [{**job, 'score': 0.61, 'excerpt': '', 'job': job}]},
                     draft={'job': job})
        self.service.store.save(state)
        status = json.loads(self.request('GET', f"/api/interview/{state['id']}/status")[1])
        self.assertTrue(status['profile_confirmed'])
        self.assertEqual(status['matched_jobs'], [{**job, 'score': 0.61}])
        self.assertEqual(status['target_job'], job)

    def confirmed_state(self):
        self.service.retriever = JobRetriever(self.service.jobs, InspectableHashEmbeddingBackend())
        state = self.service.store.get(self.create()['id'])
        target = {'document_id': 'computer_vision_engineer', 'title': 'AI Computer Vision Engineer'}
        matched = {'document_id': 'graduate_ai_engineer', 'title': 'Graduate AI Engineer'}
        state.update(confirmed_revision=state['revision'], confirmed_profile=PROFILE, draft={'job': target},
                     retrieval={'results': [{**matched, 'score': 0.5, 'excerpt': '', 'job': matched}]})
        self.service.store.save(state)
        return state

    def test_fit_needs_a_confirmed_profile(self):
        code, body = self.request('GET', f"/api/interview/{self.create()['id']}/fit")
        self.assertEqual(code, 404)
        self.assertIn('Confirm your profile', json.loads(body)['error'])

    def test_fit_defaults_to_target_job_and_accepts_a_matched_job(self):
        state = self.confirmed_state()
        target = json.loads(self.request('GET', f"/api/interview/{state['id']}/fit")[1])
        self.assertEqual(target['job']['document_id'], 'computer_vision_engineer')
        self.assertTrue(target['review_status'])
        matched = json.loads(self.request('GET', f"/api/interview/{state['id']}/fit?job=graduate_ai_engineer")[1])
        self.assertEqual(matched['job']['document_id'], 'graduate_ai_engineer')

    def test_fit_rejects_jobs_the_user_did_not_match(self):
        state = self.confirmed_state()
        code, body = self.request('GET', f"/api/interview/{state['id']}/fit?job=rag_agent_engineer")
        self.assertEqual(code, 404)
        self.assertIn('matched jobs', json.loads(body)['error'])

    def test_questions_follow_the_same_job_rules_as_fit(self):
        state = self.confirmed_state()
        result = json.loads(self.request('GET', f"/api/interview/{state['id']}/questions?job=graduate_ai_engineer")[1])
        self.assertEqual(result['job']['document_id'], 'graduate_ai_engineer')
        self.assertEqual(set(result['rounds']), {'self_introduction', 'behavioural', 'technical', 'motivation_fit'})
        self.assertEqual(self.request('GET', f"/api/interview/{state['id']}/questions?job=rag_agent_engineer")[0], 404)

    def post_answer(self, workspace_id, body):
        return self.request('POST', f'/api/interview/{workspace_id}/answer', body, {'Content-Type': 'application/json'})

    def test_answer_is_transcribed_scored_and_not_stored(self):
        class FakeTranscriber:
            def transcribe(self, audio, prompt=None):
                self.audio = audio
                return {'text': 'I um trained a model', 'words': words('I um trained a model'), 'duration': 2.5, 'model': 'fake'}
        fake = FakeTranscriber()
        workspace = self.create()
        before = self.service.store.get(workspace['id'])
        with mock.patch.object(speech, 'transcriber', return_value=fake):
            code, body = self.post_answer(workspace['id'], {'question_id': 'si-30', 'audio': base64.b64encode(b'fake-audio').decode()})
        self.assertEqual(code, 200)
        result = json.loads(body)
        self.assertEqual(fake.audio, b'fake-audio')
        self.assertEqual((result['transcript'], result['target_seconds']), ('I um trained a model', 30))
        self.assertEqual([f['word'] for f in result['delivery']['fillers']], ['um'])
        self.assertEqual(self.service.store.get(workspace['id']), before)
        self.assertNotIn('star', result)

    def test_behavioural_answers_get_a_star_check(self):
        class FakeTranscriber:
            def transcribe(self, audio, prompt=None):
                return {'text': 'In my internship a job kept failing. I built a retry step.', 'words': words('In my internship a job kept failing. I built a retry step.'), 'duration': 4, 'model': 'fake'}
        workspace = self.create()
        with mock.patch.object(speech, 'transcriber', return_value=FakeTranscriber()), \
                mock.patch.object(star, 'analyse', return_value={'sentences': [], 'present': {}, 'notes': ['checked'], 'model': {}}) as analyse:
            result = json.loads(self.post_answer(workspace['id'], {'question_id': 'bh-teamwork', 'audio': base64.b64encode(b'x').decode()})[1])
        analyse.assert_called_once()
        self.assertEqual(analyse.call_args[0][0], 'In my internship a job kept failing. I built a retry step.')
        self.assertEqual(result['star']['notes'], ['checked'])

    def test_answer_rejects_bad_input(self):
        workspace = self.create()
        self.assertEqual(self.post_answer(workspace['id'], {'question_id': 'nope', 'audio': 'AAAA'})[0], 400)
        self.assertEqual(self.post_answer(workspace['id'], {'question_id': 'si-30', 'audio': 'not base64!'})[0], 400)
        self.assertEqual(self.post_answer(workspace['id'], {'question_id': 'si-30', 'audio': ''})[0], 400)

    def test_technical_answer_gets_key_points_and_fact_check_on_confirmed_profile(self):
        class FakeTranscriber:
            prompt = None
            def transcribe(self, audio, prompt=None):
                FakeTranscriber.prompt = prompt
                return {'text': 'I would report precision and recall.', 'words': words('I would report precision and recall.'), 'duration': 3, 'model': 'fake'}
        state = self.confirmed_state()
        with mock.patch.object(speech, 'transcriber', return_value=FakeTranscriber()), \
                mock.patch.object(content, 'score', return_value={'key_points': [], 'score': 0.5, 'notes': []}) as score, \
                mock.patch.object(factcheck, 'check', return_value={'claims': [], 'notes': ['ok']}) as check:
            result = json.loads(self.post_answer(state['id'], {'question_id': 'tq-detection-eval', 'audio': base64.b64encode(b'x').decode()})[1])
        self.assertEqual(score.call_args[0][1][1], 'Precision and recall')
        self.assertIn('Role: AI Computer Vision Engineer.', FakeTranscriber.prompt)
        self.assertEqual(check.call_args[0][1], PROFILE)
        self.assertFalse(check.call_args[1]['personal_story'])
        self.assertEqual((result['content']['score'], result['fact_check']['notes']), (0.5, ['ok']))
        self.assertNotIn('star', result)

    def test_no_fact_check_without_a_confirmed_profile(self):
        class FakeTranscriber:
            def transcribe(self, audio, prompt=None):
                return {'text': 'I built it.', 'words': words('I built it.'), 'duration': 1, 'model': 'fake'}
        with mock.patch.object(speech, 'transcriber', return_value=FakeTranscriber()):
            result = json.loads(self.post_answer(self.create()['id'], {'question_id': 'mf-why-role', 'audio': base64.b64encode(b'x').decode()})[1])
        self.assertNotIn('fact_check', result)
        self.assertNotIn('content', result)

    def test_retries_are_numbered_compared_and_get_an_example_answer(self):
        class FakeTranscriber:
            texts = iter(['um I um built uh it um.', 'I built a lane detector and measured precision and recall.'])
            def transcribe(self, audio, prompt=None):
                text = next(self.texts)
                return {'text': text, 'words': words(text), 'duration': 3, 'model': 'fake'}
        state = self.confirmed_state()
        body = {'question_id': 'mf-why-role', 'audio': base64.b64encode(b'x').decode(), 'question_text': 'Why do you want this role?'}
        with mock.patch.object(speech, 'transcriber', return_value=FakeTranscriber()):
            first = json.loads(self.post_answer(state['id'], body)[1])
            second = json.loads(self.post_answer(state['id'], body)[1])
        self.assertEqual((first['progress']['attempt'], second['progress']['attempt']), (1, 2))
        self.assertTrue(first['progress']['needs_work'])
        fillers = next(c for c in second['progress']['changes'] if c['metric'] == 'fillers_per_minute')
        self.assertEqual(fillers['direction'], 'better')
        self.assertEqual(first['example_answer']['kind'], 'motivation')
        history = json.loads(self.request('GET', f"/api/interview/{state['id']}/attempts?question=mf-why-role")[1])
        self.assertEqual([h['attempt'] for h in history], [1, 2])
        overview = json.loads(self.request('GET', f"/api/interview/{state['id']}/attempts")[1])
        self.assertEqual(list(overview), ['mf-why-role'])
        self.assertEqual(overview['mf-why-role']['attempts'], 2)
        self.assertEqual(overview['mf-why-role']['needs_work'], second['progress']['needs_work'])

    def test_slides_are_served_as_json_and_pdf(self):
        state = self.confirmed_state()
        deck = json.loads(self.request('GET', f"/api/interview/{state['id']}/slides?job=graduate_ai_engineer")[1])
        self.assertEqual(deck['job']['document_id'], 'graduate_ai_engineer')
        self.assertEqual(deck['slides'][0]['kind'], 'title')
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            connection.request('GET', f"/api/interview/{state['id']}/slides.pdf")
            response = connection.getresponse()
            self.assertEqual((response.status, response.getheader('Content-Type')), (200, 'application/pdf'))
            self.assertTrue(response.read().startswith(b'%PDF'))
        finally:
            connection.close()
        self.assertEqual(self.request('GET', f"/api/interview/{self.create()['id']}/slides")[0], 404)

    def test_cheat_sheet_is_served_as_json_and_one_page_pdf(self):
        class FakeTranscriber:
            def transcribe(self, audio, prompt=None):
                text = 'I built a lane detector and measured precision and recall.'
                return {'text': text, 'words': words(text), 'duration': 4, 'model': 'fake'}
        state = self.confirmed_state()
        with mock.patch.object(speech, 'transcriber', return_value=FakeTranscriber()):
            self.post_answer(state['id'], {'question_id': 'si-30', 'audio': base64.b64encode(b'x').decode()})
        # The shipped STAR weights expect MiniLM-sized vectors, not the test backend's.
        with mock.patch.object(star, 'classifier', return_value=FakeStar()), mock.patch.object(model_answer, 'classifier', return_value=FakeStar()):
            sheet = json.loads(self.request('GET', f"/api/interview/{state['id']}/cheatsheet?job=graduate_ai_engineer")[1])
        self.assertEqual((sheet['job']['document_id'], sheet['practised']), ('graduate_ai_engineer', 1))
        self.assertTrue(sheet['introduction']['text'] and sheet['questions_to_ask'] and sheet['reminders'])
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            with mock.patch.object(star, 'classifier', return_value=FakeStar()), mock.patch.object(model_answer, 'classifier', return_value=FakeStar()):
                connection.request('GET', f"/api/interview/{state['id']}/cheatsheet.pdf")
                response = connection.getresponse()
            self.assertEqual((response.status, response.getheader('Content-Type')), (200, 'application/pdf'))
            self.assertTrue(response.read().startswith(b'%PDF'))
        finally:
            connection.close()
        self.assertEqual(self.request('GET', f"/api/interview/{self.create()['id']}/cheatsheet")[0], 404)

    def test_natural_voice_and_recognition_choice(self):
        class FakeSpeaker:
            def wav(self, text):
                return b'RIFF' + text.encode()
        state = self.confirmed_state()
        settings = json.loads(self.request('GET', f"/api/interview/{state['id']}/speech")[1])
        self.assertEqual(settings['voice']['id'], 'en_US-lessac-medium')
        self.assertIn(settings['recognition']['default'], ('small.en', 'base.en'))
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            with mock.patch.object(voice, 'speaker', return_value=FakeSpeaker()):
                connection.request('POST', f"/api/interview/{state['id']}/speak", body=json.dumps({'text': 'Hello there.'}), headers={'Content-Type': 'application/json'})
                response = connection.getresponse()
                self.assertEqual((response.status, response.getheader('Content-Type'), response.read()), (200, 'audio/wav', b'RIFFHello there.'))
        finally:
            connection.close()
        with mock.patch.object(voice, 'speaker', return_value=None):
            code, body = self.request('POST', f"/api/interview/{state['id']}/speak", {'text': 'Hello.'}, {'Content-Type': 'application/json'})
        self.assertEqual((code, json.loads(body)['error']), (400, 'The natural voice is not installed.'))
        with mock.patch.object(speech, 'installed', return_value=False):
            code, body = self.post_answer(state['id'], {'question_id': 'si-30', 'audio': base64.b64encode(b'x').decode(), 'recognition': 'small.en'})
        self.assertEqual((code, json.loads(body)['error']), (400, 'That speech recognition model is not installed.'))

    def test_countdown_plan_is_saved_per_job_and_freezes_today(self):
        from datetime import date, timedelta
        state = self.confirmed_state()
        url = f"/api/interview/{state['id']}/plan"
        json_header = {'Content-Type': 'application/json'}
        self.assertIsNone(json.loads(self.request('GET', url)[1])['interview_date'])
        when = (date.today() + timedelta(3)).isoformat()
        result = json.loads(self.request('POST', url, {'job': 'graduate_ai_engineer', 'interview_date': when}, json_header)[1])
        self.assertEqual((result['interview_date'], result['days_left'], len(result['days'])), (when, 3, 4))
        today = [t['question_id'] for t in result['days'][0]['tasks'] if t['kind'] == 'question']
        again = json.loads(self.request('GET', url + '?job=graduate_ai_engineer')[1])
        self.assertEqual([t['question_id'] for t in again['days'][0]['tasks'] if t['kind'] == 'question'], today)
        code, body = self.request('POST', url, {'job': 'graduate_ai_engineer', 'interview_date': '2020-01-01'}, json_header)
        self.assertEqual((code, json.loads(body)['error']), (400, 'The interview date is in the past.'))
        cleared = json.loads(self.request('POST', url, {'job': 'graduate_ai_engineer', 'interview_date': None}, json_header)[1])
        self.assertIsNone(cleared['interview_date'])

    def test_off_topic_introduction_with_another_name_is_not_strong(self):
        class FakeTranscriber:
            def transcribe(self, audio, prompt=None):
                text = 'Hello, my name is Dietz Patel. Most of my work is done with other tools. Are you there?'
                heard = words(text)
                heard[4]['probability'] = heard[5]['probability'] = 0.2  # Whisper unsure about the name.
                return {'text': text, 'words': heard, 'duration': 30, 'model': 'fake'}
        state = self.confirmed_state()
        state['confirmed_profile'] = {**state['confirmed_profile'], 'name': 'Sam Lee'}
        self.service.store.save(state)
        with mock.patch.object(speech, 'transcriber', return_value=FakeTranscriber()):
            result = json.loads(self.post_answer(state['id'], {'question_id': 'si-30', 'audio': base64.b64encode(b'x').decode(), 'job': 'graduate_ai_engineer'})[1])
        self.assertTrue(result['content']['key_points'])  # Introductions are now checked against the profile.
        self.assertEqual(result['fact_check']['claims'][0]['flags'][0]['type'], 'name')
        self.assertLessEqual(result['score']['overall'], 40)
        self.assertTrue(result['progress']['needs_work'])
        self.assertEqual(result['recognition']['unsure_words'], ['Dietz', 'Patel.'])

    def test_gemini_writes_the_transcript_and_whisper_keeps_the_timing(self):
        class FakeTranscriber:
            def transcribe(self, audio, prompt=None):
                text = 'I am Sam Lee and I built a lane detector.'
                return {'text': 'I am Sam Lee and I built a lame detector.', 'words': words(text), 'duration': 4, 'model': 'whisper-fake'}
        class FakeGemini:
            name = 'gemini:fake'
            def __init__(self, reply=None, error=None):
                self.reply, self.error, self.calls = reply, error, []
            def decide(self, messages, context):
                self.calls.append((messages, context))
                if self.error:
                    raise self.error
                return self.reply
        state = self.confirmed_state()
        body = {'question_id': 'tq-detection-eval', 'audio': base64.b64encode(b'x').decode()}
        gemini = FakeGemini(json.dumps({'transcript': 'I am Sam Lee and I built a  lane detector.'}))
        with mock.patch.object(gemini_speech, 'configured', return_value=True), mock.patch.object(self.service, 'model', gemini), \
                mock.patch.object(gemini_speech, 'wav_bytes', return_value=b'RIFF'), mock.patch.object(speech, 'decode_audio', return_value=None), \
                mock.patch.object(speech, 'transcriber', return_value=FakeTranscriber()):
            settings = json.loads(self.request('GET', f"/api/interview/{state['id']}/speech")[1])['recognition']
            self.assertEqual((settings['default'], settings['options'][0]['id']), ('gemini', 'gemini'))
            result = json.loads(self.post_answer(state['id'], body)[1])
            self.assertEqual(result['transcript'], 'I am Sam Lee and I built a lane detector.')  # Gemini's text, not Whisper's "lame".
            self.assertEqual((result['words'], result['recognition']['source']), ([], 'gemini'))
            self.assertEqual(result['delivery']['word_count'], 10)  # Timing still from Whisper's words.
            self.assertIn('gemini:fake', result['model'])
            messages, context = gemini.calls[0]
            self.assertEqual(context['_attachment']['mimeType'], 'audio/wav')
            self.assertIn('word for word', messages[0]['content'])
            self.service.model = FakeGemini(error=GeminiError('Gemini returned HTTP 429. Try again later.', retryable=True))
            fallback = json.loads(self.post_answer(state['id'], body)[1])
            self.assertEqual(fallback['transcript'], 'I am Sam Lee and I built a lame detector.')
            self.assertIn('Gemini could not transcribe this answer', fallback['delivery']['notes'][0])
            local = json.loads(self.post_answer(state['id'], {**body, 'recognition': 'base.en'})[1])
            self.assertEqual(local['recognition']['source'], 'whisper')

    def test_rehearsal_reports_which_slides_were_covered(self):
        class FakeTranscriber:
            def transcribe(self, audio, prompt=None):
                text = 'I built a lane detector and measured precision and recall.'
                return {'text': text, 'words': words(text), 'duration': 4, 'model': 'fake'}
        state = self.confirmed_state()
        with mock.patch.object(speech, 'transcriber', return_value=FakeTranscriber()):
            result = json.loads(self.post_answer(state['id'], {'question_id': 'si-120', 'audio': base64.b64encode(b'x').decode(), 'rehearsal': True})[1])
            plain = json.loads(self.post_answer(state['id'], {'question_id': 'si-120', 'audio': base64.b64encode(b'x').decode()})[1])
        coverage = result['slide_coverage']
        self.assertEqual(coverage['total'], len(coverage['slides']))
        self.assertTrue(coverage['notes'])
        self.assertNotIn('slide_coverage', plain)

    def test_mock_interview_links_answers_and_builds_a_report(self):
        class FakeTranscriber:
            def transcribe(self, audio, prompt=None):
                text = 'I built a lane detector and measured precision and recall.'
                return {'text': text, 'words': words(text), 'duration': 4, 'model': 'fake'}
        state = self.confirmed_state()
        code, body = self.request('POST', f"/api/interview/{state['id']}/mock", {}, {'Content-Type': 'application/json'})
        self.assertEqual(code, 200)
        session = json.loads(body)
        self.assertEqual(len(session['questions']), 5)
        first = session['questions'][0]
        self.assertEqual(self.request('GET', f"/api/interview/{state['id']}/mock/{session['id']}/report")[0], 404)  # Nothing answered yet.
        with mock.patch.object(speech, 'transcriber', return_value=FakeTranscriber()):
            self.post_answer(state['id'], {'question_id': first['id'], 'audio': base64.b64encode(b'x').decode(), 'mock_session': session['id'], 'mock_position': 0})
        result = json.loads(self.request('GET', f"/api/interview/{state['id']}/mock/{session['id']}/report")[1])
        self.assertEqual((result['answered'], result['total']), (1, 5))
        self.assertEqual(result['band'], 'Incomplete')  # Only 1 of 5 answered.
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            connection.request('GET', f"/api/interview/{state['id']}/mock/{session['id']}/report.pdf")
            response = connection.getresponse()
            self.assertEqual(response.getheader('Content-Type'), 'application/pdf')
            self.assertTrue(response.read().startswith(b'%PDF'))
        finally:
            connection.close()
        other = self.create()
        self.assertEqual(self.request('GET', f"/api/interview/{other['id']}/mock/{session['id']}")[0], 404)

    def test_follow_up_is_asked_and_its_answer_is_scored_on_its_own(self):
        class FakeTranscriber:
            def transcribe(self, audio, prompt=None):
                text = 'I would report precision and recall for each class.'
                return {'text': text, 'words': words(text), 'duration': 4, 'model': 'fake'}
        state = self.confirmed_state()
        body = {'question_id': 'tq-detection-eval', 'audio': base64.b64encode(b'x').decode()}
        with mock.patch.object(speech, 'transcriber', return_value=FakeTranscriber()):
            first = json.loads(self.post_answer(state['id'], body)[1])
            asked = first['follow_up']
            self.assertEqual(asked['depth'], 1)
            second = json.loads(self.post_answer(state['id'], {**body, 'follow_up': asked})[1])
        self.assertEqual(second['follow_up_of'], asked['question'])
        self.assertEqual(second['target_seconds'], 45)
        self.assertNotIn('example_answer', second)
        if asked.get('key_point'):
            self.assertEqual([k['text'] for k in second['content']['key_points']], [asked['key_point']])
        self.assertEqual(second['follow_up']['depth'], 2)
        overview = json.loads(self.request('GET', f"/api/interview/{state['id']}/attempts")[1])
        self.assertEqual((overview['tq-detection-eval']['attempts'], overview['tq-detection-eval:follow-up']['attempts']), (1, 1))

    def test_mock_cross_questioning_scores_and_report_list(self):
        class FakeTranscriber:
            def transcribe(self, audio, prompt=None):
                text = 'In my lane detector project I improved recall by 20 percent.'
                return {'text': text, 'words': words(text), 'duration': 5, 'model': 'fake'}
        state = self.confirmed_state()
        self.assertEqual(json.loads(self.request('GET', f"/api/interview/{state['id']}/mock")[1]), [])
        session = json.loads(self.request('POST', f"/api/interview/{state['id']}/mock", {}, {'Content-Type': 'application/json'})[1])
        first = session['questions'][0]
        body = {'question_id': first['id'], 'audio': base64.b64encode(b'x').decode(), 'mock_session': session['id'], 'mock_position': 0}
        with mock.patch.object(speech, 'transcriber', return_value=FakeTranscriber()):
            main = json.loads(self.post_answer(state['id'], body)[1])
            self.assertTrue(0 <= main['score']['overall'] <= 100)
            asked = main['follow_up']
            self.assertEqual(asked['depth'], 1)
            follow = json.loads(self.post_answer(state['id'], {**body, 'follow_up': asked})[1])
        self.assertIsNone(follow['follow_up'])  # One follow-up per question in a mock interview.
        result = json.loads(self.request('GET', f"/api/interview/{state['id']}/mock/{session['id']}/report")[1])
        self.assertEqual(result['questions'][0]['follow_up']['question'], asked['question'])
        self.assertIsNotNone(result['cross_questioning'])
        listed = json.loads(self.request('GET', f"/api/interview/{state['id']}/mock")[1])
        self.assertEqual([(i['id'], i['answered'], i['band']) for i in listed], [(session['id'], 1, 'Incomplete')])

    def test_evaluation_scripts_and_samples(self):
        workspace = self.create()
        listing = json.loads(self.request('GET', f"/api/interview/{workspace['id']}/evaluation")[1])
        self.assertEqual((len(listing['scripts']), listing['recorded']), (10, []))
        code, body = self.request('POST', f"/api/interview/{workspace['id']}/evaluation-sample",
                                  {'script_id': 'e03', 'audio': base64.b64encode(b'audio').decode()}, {'Content-Type': 'application/json'})
        self.assertEqual((code, json.loads(body)['recorded'], json.loads(body)['seconds']), (200, ['e03'], {'e03': 0.0}))
        self.assertTrue((Path(self.directory.name) / 'interview-evaluation' / 'e03.webm').is_file())
        bad = self.request('POST', f"/api/interview/{workspace['id']}/evaluation-sample", {'script_id': 'nope', 'audio': 'AAAA'}, {'Content-Type': 'application/json'})
        self.assertEqual(bad[0], 400)

    def test_unknown_workspace_and_path_are_not_found(self):
        self.assertEqual(self.request('GET', '/api/interview/missing/status')[0], 404)
        self.assertEqual(self.request('GET', '/api/interview/x/unknown')[0], 404)


if __name__ == '__main__':
    unittest.main()

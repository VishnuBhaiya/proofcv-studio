"""Interview Coach HTTP routes with synthetic local data and no model requests."""
import base64
import json
import unittest
from unittest import mock
from .. import test_http
from . import speech, star
from .test_speech import words
from ..retrieval import InspectableHashEmbeddingBackend, JobRetriever
from .test_fit import PROFILE


class InterviewRouteTests(unittest.TestCase):
    # Reuse the real local server fixture without re-running the core HTTP tests.
    setUp, tearDown, request = test_http.HTTPTests.setUp, test_http.HTTPTests.tearDown, test_http.HTTPTests.request

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
            def transcribe(self, audio):
                self.audio = audio
                return {'text': 'I um trained a model', 'words': words('I um trained a model'), 'duration': 2.5, 'model': 'fake'}
        fake = FakeTranscriber()
        workspace = self.create()
        before = self.service.store.get(workspace['id'])
        with mock.patch.object(speech, '_transcriber', fake):
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
            def transcribe(self, audio):
                return {'text': 'In my internship a job kept failing. I built a retry step.', 'words': words('In my internship a job kept failing. I built a retry step.'), 'duration': 4, 'model': 'fake'}
        workspace = self.create()
        with mock.patch.object(speech, '_transcriber', FakeTranscriber()), \
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

    def test_unknown_workspace_and_path_are_not_found(self):
        self.assertEqual(self.request('GET', '/api/interview/missing/status')[0], 404)
        self.assertEqual(self.request('GET', '/api/interview/x/unknown')[0], 404)


if __name__ == '__main__':
    unittest.main()

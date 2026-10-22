"""Interview Coach HTTP routes with synthetic local data and no model requests."""
import json
import unittest
from .. import test_http
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

    def test_unknown_workspace_and_path_are_not_found(self):
        self.assertEqual(self.request('GET', '/api/interview/missing/status')[0], 404)
        self.assertEqual(self.request('GET', '/api/interview/x/unknown')[0], 404)


if __name__ == '__main__':
    unittest.main()

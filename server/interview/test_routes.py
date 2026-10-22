"""Interview Coach HTTP routes with synthetic local data and no model requests."""
import json
import unittest
from .. import test_http


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

    def test_unknown_workspace_and_path_are_not_found(self):
        self.assertEqual(self.request('GET', '/api/interview/missing/status')[0], 404)
        self.assertEqual(self.request('GET', '/api/interview/x/unknown')[0], 404)


if __name__ == '__main__':
    unittest.main()

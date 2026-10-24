"""Portfolio and Interview Coach must share one confirmed workspace over HTTP."""
import json
import unittest

from . import test_http
from .seed_labelled_sample import seed


class CombinedModulesTests(unittest.TestCase):
    setUp = test_http.HTTPTests.setUp
    tearDown = test_http.HTTPTests.tearDown
    request = test_http.HTTPTests.request

    def test_four_project_sample_stays_shared_when_portfolio_is_initialised(self):
        workspace = seed(self.service.store)
        before = self.service.store.get(workspace)
        code, body = self.request('POST', f'/api/workspaces/{workspace}/portfolio-init',
                                  {'revision': before['revision']}, {'Content-Type': 'application/json'})
        self.assertEqual(code, 200)
        code, body = self.request('GET', f'/api/workspaces/{workspace}/portfolio')
        self.assertEqual(code, 200)
        portfolio = json.loads(body)['portfolio']
        self.assertEqual([p['title'] for p in portfolio['projects']],
                         [p['title'] for p in before['confirmed_profile']['projects']])
        self.assertEqual(portfolio['projects'][-1]['title'], 'SolarVision')
        code, body = self.request('GET', f'/api/interview/{workspace}/status')
        self.assertEqual(code, 200)
        status = json.loads(body)
        self.assertTrue(status['profile_confirmed'])
        self.assertEqual(status['target_job']['document_id'], before['draft']['job']['document_id'])
        self.assertEqual(len(status['jobs']), 9)
        self.assertEqual(self.service.store.get(workspace), before)


if __name__ == '__main__':
    unittest.main()

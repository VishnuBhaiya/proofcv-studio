"""Shared demo import boundaries; no providers, personal DBs or real video decoding."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from .portfolio import PortfolioService
from .prepare_team_demo import EXAMPLES, prepare
from .portfolio_assets import digest
from .seed_labelled_sample import seed
from .store import Store
from .test_prepare_avery_solar_demo import NoProvider, SyntheticMedia


class TeamDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'test.sqlite3')
        self.workspace = seed(self.store)
        self.service = PortfolioService(self.store, NoProvider(), [])
        self.fixture = json.loads((EXAMPLES / 'avery-demo.json').read_text(encoding='utf-8'))
        self.video = self.root / 'test.mp4'
        self.video.write_bytes(b'SYNTHETIC_UNIT_TEST_METADATA_FIXTURE')
        self.fixture['video']['sha256'] = digest(self.video.read_bytes())
        self.media = SyntheticMedia(self.root / 'portfolio-media')

    def prepare(self):
        return prepare(self.store, self.workspace, self.fixture, self.video, self.media)

    def test_prepares_four_projects_views_and_reviewed_video_without_approval(self):
        original = self.store.get(self.workspace)
        self.assertTrue(self.prepare()['changed'])
        portfolio = self.service.get(self.workspace)['portfolio']
        self.assertEqual(len(portfolio['projects']), 4)
        self.assertEqual(len(portfolio['views']), 3)
        self.assertEqual(portfolio['settings']['theme'], 'technical')
        self.assertFalse(portfolio['settings']['show_email'])
        self.assertTrue(portfolio['assets'][0]['published'])
        self.assertEqual(len(portfolio['assets'][0]['analysis']['chapters']), 6)
        self.assertEqual(portfolio['snapshots'], [])
        self.assertEqual(self.store.get(self.workspace), original)

    def test_repeat_preserves_later_owner_edits(self):
        self.prepare()
        portfolio = self.service.get(self.workspace)['portfolio']
        portfolio['headline'] = 'Owner changed this after import'
        self.service._save(self.workspace, portfolio)
        self.assertFalse(self.prepare()['changed'])
        self.assertEqual(self.service.get(self.workspace)['portfolio'], portfolio)
        self.assertEqual(self.media.calls, 1)

    def test_existing_portfolio_is_never_overwritten(self):
        self.service.action(self.workspace, 'portfolio-init', {'revision': self.store.get(self.workspace)['revision']})
        before = self.service.get(self.workspace)['portfolio']
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.prepare()
        self.assertEqual(self.service.get(self.workspace)['portfolio'], before)
        self.assertEqual(self.media.calls, 0)

    def test_personal_edits_and_bad_sources_are_rejected_before_media(self):
        state = self.store.get(self.workspace)
        state['confirmed_profile']['location'] = 'Owner customisation'
        self.store.save(state)
        with self.assertRaisesRegex(ValueError, 'Existing personal edits'):
            self.prepare()
        self.assertEqual(self.store.get(self.workspace), state)
        self.assertEqual(self.media.calls, 0)

    def test_bad_video_hash_and_unknown_source_are_rejected(self):
        self.fixture['source_ids'] = ['unconfirmed-claim']
        with self.assertRaisesRegex(ValueError, 'outside its source'):
            self.prepare()
        self.fixture['source_ids'] = ['name']
        self.fixture['video']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.prepare()
        self.assertEqual(self.media.calls, 0)

    def test_other_workspace_and_saved_cv_history_stay_unchanged(self):
        other = self.store.create('A real user workspace')
        before = deepcopy(self.store.get(other['id']))
        self.prepare()
        self.assertEqual(self.store.get(other['id']), before)
        self.assertEqual(len(self.store.get(self.workspace)['versions']), 2)


if __name__ == '__main__':
    unittest.main()

"""Temporary-store deterministic checks. No runtime DB, provider or real video is touched."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from .portfolio import PortfolioService, blank
from .portfolio_assets import MediaStore, digest
from .prepare_avery_solar_demo import PROJECT, prepare
from .seed_labelled_sample import seed
from .store import Store, update_profile


class NoProvider:
    def decide(self, *args, **kwargs):
        raise AssertionError('No provider may be called by this local demo helper.')


class SyntheticMedia(MediaStore):
    """Metadata fixture, deliberately not a claim of real MP4 decoding."""
    calls = 0

    def video(self, encoded):
        self.calls += 1
        raw = base64.b64decode(encoded)
        return dict(key=self.put(raw, 'mp4'), sha256=digest(raw), mime='video/mp4',
                    width=1280, height=720, size=len(raw), duration=207.83)


class PrepareAverySolarDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'test.sqlite3')
        self.workspace = seed(self.store)
        # Exercise the legacy three-project migration even though new shared
        # installs now seed all four projects.
        legacy = self.store.get(self.workspace)
        legacy['profile']['projects'] = legacy['profile']['projects'][:3]
        legacy['confirmed_profile'] = deepcopy(legacy['profile'])
        legacy['draft']['profile'] = deepcopy(legacy['profile'])
        legacy['draft']['selection']['project_order'] = [i for i in legacy['draft']['selection']['project_order'] if i < 3]
        self.store.save(legacy)
        self.service = PortfolioService(self.store, NoProvider(), [])
        self.media = SyntheticMedia(self.root / 'portfolio-media')
        self.recording = self.root / 'synthetic-test-fixture.mp4'
        self.recording.write_bytes(b'0000ftyp_SYNTHETIC_TEST_ONLY_METADATA_FIXTURE')
        p = blank(self.store.get(self.workspace))
        p['revision'] = 5
        p['headline'] = 'Keep the owner headline'
        p['settings'].update(theme='technical', avatar='leaf', show_location=True)
        p['narration'] = {'key': 'owner-audio.wav', 'script': 'Keep the owner narration.'}
        p['views'].append(dict(id='graduate_ai_engineer', title='Graduate AI Engineer',
            project_ids=[p['projects'][2]['id']], skills=['Python'], rationale='Keep this exact role-specific choice.'))
        p['snapshots'] = [{'id': 'approved-before-import', 'digest': 'immutable-fixture'}]
        p['assets'] = [dict(id='owner-image', project_id=p['projects'][0]['id'],
            key=self.media.put(b'IMAGE_FIXTURE', 'png'), sha256=digest(b'IMAGE_FIXTURE'), mime='image/png',
            published=True, analysis={'caption': 'Keep this owner image.', 'hotspots': []})]
        self.service._save(self.workspace, p)
        with self.store.connect() as db:
            db.execute('INSERT INTO portfolio_snapshots VALUES (?,?,?,?)',
                ('approved-before-import', self.workspace, json.dumps({'id': 'approved-before-import'}), b'IMMUTABLE_TEST_ARCHIVE'))
        self.old = deepcopy(p)
        self.old_state = self.store.get(self.workspace)

    def tearDown(self):
        self.temp.cleanup()

    def run_prepare(self):
        return prepare(self.store, self.workspace, self.recording, self.media)

    def portfolio(self):
        return self.service.get(self.workspace)['portfolio']

    def add_profile_solar(self):
        state = self.store.get(self.workspace)
        update_profile(state, {'projects': state['profile']['projects'] + [deepcopy(PROJECT)]})
        state.update(confirmed_revision=state['revision'], confirmed_profile=deepcopy(state['profile']))
        self.store.save(state)
        return state

    def test_adds_to_canonical_demo_without_resetting_owner_edits_or_saved_cvs(self):
        result = self.run_prepare()
        state, p = self.store.get(self.workspace), self.portfolio()
        self.assertTrue(result['changed'])
        self.assertEqual(len(state['profile']['projects']), 4)
        self.assertEqual(state['profile']['projects'][-1], PROJECT)
        self.assertEqual(state['confirmed_revision'], state['revision'])
        for key in ('versions', 'messages', 'cv_messages', 'trace', 'audit_runs'):
            self.assertEqual(state[key], self.old_state[key])
        for key in ('settings', 'headline', 'bio', 'bio_sources', 'narration', 'snapshots'):
            self.assertEqual(p[key], self.old[key])
        self.assertEqual(p['views'][1], self.old['views'][1])
        self.assertEqual(p['assets'][0], self.old['assets'][0])
        self.assertEqual(len(p['views'][0]['project_ids']), 4)
        self.assertIn('not a claim that Avery personally authored', p['projects'][-1]['description'])
        video = p['assets'][-1]
        self.assertTrue(video['published'])
        self.assertEqual(video['project_id'], p['projects'][-1]['id'])
        self.assertEqual(len(video['analysis']['chapters']), 6)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT archive FROM portfolio_snapshots WHERE id=?', ('approved-before-import',)).fetchone()[0], b'IMMUTABLE_TEST_ARCHIVE')

    def test_second_run_is_a_true_no_op_without_duplicate_media_or_revision_bump(self):
        first = self.run_prepare()
        state, p = self.store.get(self.workspace), self.portfolio()
        result = self.run_prepare()
        self.assertFalse(result['changed'])
        self.assertEqual(result['asset_id'], first['asset_id'])
        self.assertEqual(self.store.get(self.workspace), state)
        self.assertEqual(self.portfolio(), p)
        self.assertEqual(self.media.calls, 1)

    def test_existing_profile_solar_repairs_missing_portfolio_project_and_video(self):
        state = self.add_profile_solar()
        self.run_prepare()
        self.assertEqual(self.store.get(self.workspace), state)
        p = self.portfolio()
        self.assertEqual(len(p['projects']), 4)
        self.assertEqual(p['source_revision'], state['revision'])
        self.assertEqual(len(p['assets']), 2)
        self.assertEqual(p['settings'], self.old['settings'])

    def test_existing_portfolio_solar_without_video_is_repaired(self):
        state = self.add_profile_solar()
        p = blank(state)
        p['settings'] = deepcopy(self.old['settings'])
        self.service._save(self.workspace, p)
        self.run_prepare()
        self.assertEqual(len(self.portfolio()['assets']), 1)
        self.assertEqual(self.portfolio()['settings'], self.old['settings'])

    def test_missing_analysis_and_disclosure_are_repaired_without_reupload(self):
        self.run_prepare()
        p = self.portfolio()
        asset_id = p['assets'][-1]['id']
        p['assets'][-1].pop('analysis')
        p['assets'][-1]['published'] = False
        self.service._save(self.workspace, p)
        result = self.run_prepare()
        self.assertTrue(result['changed'])
        self.assertEqual(result['asset_id'], asset_id)
        self.assertTrue(self.portfolio()['assets'][-1]['published'])
        self.assertEqual(self.media.calls, 1)

    def test_missing_media_blob_is_repaired(self):
        self.run_prepare()
        p = self.portfolio()
        asset = p['assets'][-1]
        (self.media.root / asset['key']).unlink()  # Only this temporary test fixture.
        self.assertTrue(self.run_prepare()['changed'])
        self.assertEqual(self.media.read(asset['key']), self.recording.read_bytes())
        self.assertEqual(len(self.portfolio()['assets']), 2)

    def test_unrelated_stale_profile_changes_fail_without_any_workspace_write(self):
        state = self.store.get(self.workspace)
        update_profile(state, {'goal': 'An owner-edited career objective'})
        state.update(confirmed_revision=state['revision'], confirmed_profile=deepcopy(state['profile']))
        self.store.save(state)
        before = self.portfolio()
        with self.assertRaisesRegex(ValueError, 'unrelated stale'):
            self.run_prepare()
        self.assertEqual(self.store.get(self.workspace), state)
        self.assertEqual(self.portfolio(), before)

    def test_existing_different_video_is_not_replaced(self):
        self.run_prepare()
        before, state = self.portfolio(), self.store.get(self.workspace)
        self.recording.write_bytes(b'DIFFERENT_SYNTHETIC_VIDEO_FIXTURE')
        with self.assertRaisesRegex(ValueError, 'different video'):
            self.run_prepare()
        self.assertEqual(self.portfolio(), before)
        self.assertEqual(self.store.get(self.workspace), state)

    def test_pending_proposal_is_preserved_and_blocks_the_helper(self):
        p = self.portfolio()
        p['pending'] = {'id': 'owner-review-in-progress', 'kind': 'site'}
        self.service._save(self.workspace, p)
        state = self.store.get(self.workspace)
        with self.assertRaisesRegex(ValueError, 'current portfolio proposal'):
            self.run_prepare()
        self.assertEqual(self.portfolio(), p)
        self.assertEqual(self.store.get(self.workspace), state)

    def test_unlabelled_real_candidate_is_rejected(self):
        state = self.store.get(self.workspace)
        state['label'] = 'My real CV'
        self.store.save(state)
        with self.assertRaisesRegex(ValueError, 'labelled Avery'):
            self.run_prepare()
        self.assertEqual(self.store.get(self.workspace), state)

    def test_startup_seed_preserves_new_solar_profile_and_website(self):
        self.run_prepare()
        state, p = self.store.get(self.workspace), self.portfolio()
        self.assertEqual(seed(self.store), self.workspace)
        self.assertEqual(self.store.get(self.workspace), state)
        self.assertEqual(self.portfolio(), p)


if __name__ == '__main__':
    unittest.main()

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from .seed_labelled_sample import LABEL, LEGACY_LABEL, seed
from .store import Store
from .update_avery_sample import update_existing


class LabelledSampleTests(unittest.TestCase):
    def test_avery_sample_is_detailed_and_has_two_targeted_cvs(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'test.sqlite3')
            workspace_id = seed(store)
            state = store.get(workspace_id)

            self.assertEqual(state['label'], LABEL)
            self.assertEqual(state['profile']['name'], 'Avery Morgan')
            self.assertEqual(len(state['profile']['projects']), 4)
            self.assertEqual([p['title'] for p in state['profile']['projects']], [
                'Smart Intersection Object Detection', 'Warehouse Safety Video Analytics',
                'Dataset Quality Review Toolkit', 'SolarVision'])
            self.assertIn('not a claim that Avery personally authored', state['profile']['projects'][3]['description'])
            self.assertGreaterEqual(len(state['profile']['skills']), 15)
            self.assertIn('Computer Vision Lab Assistant', state['profile']['experience'])
            self.assertIn('Applied AI Showcase', state['profile']['achievements'])
            self.assertEqual(len(state['versions']), 2)
            self.assertEqual(
                {version['draft']['job']['document_id'] for version in state['versions']},
                {'computer_vision_engineer', 'graduate_ai_engineer'},
            )
            self.assertEqual(
                state['versions'][0]['draft']['profile'],
                state['versions'][1]['draft']['profile'],
            )
            self.assertNotEqual(
                state['versions'][0]['draft']['selection']['skills'],
                state['versions'][1]['draft']['selection']['skills'],
            )
            self.assertTrue(all(
                version['draft']['design']['ats'] and not version['draft']['tailored_content']
                for version in state['versions']
            ))
            self.assertTrue(all(len(version['draft']['profile']['projects']) == 4 for version in state['versions']))
            self.assertTrue(all(set(version['draft']['selection']['project_order']) == {0, 1, 2, 3} for version in state['versions']))

    def test_startup_never_resets_existing_demo_edits_or_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'test.sqlite3');workspace=seed(store)
            state=store.get(workspace);state['profile']['goal']='Owner-edited target role'
            state['messages'].append(dict(role='user',content='Preserve my practice notes.'))
            store.save(state);before=deepcopy(store.get(workspace))
            self.assertEqual(seed(store),workspace)
            self.assertEqual(store.get(workspace),before)
            self.assertEqual(len(store.list()),1)

    def test_legacy_demo_is_not_renamed_or_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'test.sqlite3');state=store.create(LEGACY_LABEL)
            before=deepcopy(state)
            self.assertEqual(seed(store),state['id'])
            self.assertEqual(store.get(state['id']),before)

    def test_explicit_existing_demo_update_preserves_work_and_requires_review(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'test.sqlite3');workspace=seed(store)
            state=store.get(workspace)
            state['profile']['projects']=state['profile']['projects'][:3]
            state['confirmed_profile']=deepcopy(state['profile'])
            state['profile']['goal']='Keep my edited target'
            store.save(state);before=deepcopy(store.get(workspace))
            result=update_existing(store);after=store.get(workspace)
            self.assertTrue(result['changed']);self.assertTrue(result['review_required'])
            self.assertEqual(after['id'],before['id'])
            self.assertEqual(after['profile']['goal'],before['profile']['goal'])
            self.assertEqual(after['profile']['projects'][:3],before['profile']['projects'])
            self.assertEqual(after['profile']['projects'][-1]['title'],'SolarVision')
            self.assertEqual(after['revision'],before['revision']+1)
            self.assertIsNone(after['confirmed_revision'])
            for field in ('versions','draft','messages','cv_messages','confirmed_profile'):
                self.assertEqual(after[field],before[field])
            saved=deepcopy(after)
            self.assertFalse(update_existing(store)['changed'])
            self.assertEqual(store.get(workspace),saved)

    def test_conflicting_solarvision_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'test.sqlite3');workspace=seed(store)
            state=store.get(workspace);state['profile']['projects'][-1]['description']='Keep my reviewed version.'
            store.save(state);before=deepcopy(state)
            with self.assertRaisesRegex(ValueError,'different content'):update_existing(store)
            self.assertEqual(store.get(workspace),before)

    def test_pending_proposal_or_real_person_blocks_demo_update(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'test.sqlite3');workspace=seed(store)
            state=store.get(workspace);state['pending_profile']={'id':'pending'};store.save(state)
            with self.assertRaisesRegex(ValueError,'pending'):update_existing(store)
            state['pending_profile']=None;state['profile']['name']='Real Person';store.save(state)
            with self.assertRaisesRegex(ValueError,'fictional Avery'):update_existing(store)


if __name__ == '__main__':
    unittest.main()

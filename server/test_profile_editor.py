import tempfile
import unittest
from pathlib import Path
from .store import Store, missing_fields
from .service import Service
from .test_system import SequenceModel, complete_profile


class ProfileEditorTests(unittest.TestCase):
    def test_optional_fields_and_undo_persist_without_reconfirming(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'test.sqlite3')
            service = Service(store=store, model=SequenceModel([]))
            state = store.create('Profile test')
            def action(op, **data):
                nonlocal state
                state = service.action(state['id'], op, {'revision': state['revision'], **data})
            action('profile', patch=complete_profile())
            action('confirm', accepted=True)
            action('profile', patch={'location': 'Sydney', 'github': 'https://github.com/example'})
            self.assertIsNone(state['confirmed_revision'])
            self.assertEqual(store.get(state['id'])['profile']['location'], 'Sydney')
            action('undo-profile')
            self.assertEqual(state['profile']['location'], '')
            self.assertEqual(state['profile']['name'], 'Test Candidate')
            self.assertIsNone(state['confirmed_revision'])

    def test_blank_structured_entry_does_not_count_as_complete(self):
        profile = complete_profile()
        profile['education'] = 'Degree: \nUniversity: Test'
        self.assertIn('education entry title', missing_fields(profile))

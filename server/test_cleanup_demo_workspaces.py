from copy import deepcopy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .cleanup_demo_workspaces import candidates, cleanup, removable_reason
from .store import Store


class DemoWorkspaceCleanupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name) / 'test.sqlite3')

    def test_known_verification_and_empty_starter_only(self):
        fixture = self.store.create('Showcase — synthetic live verification 20261022T043843Z')
        fixture['profile']['name'] = 'Avery Morgan'
        self.store.save(fixture)
        blank = self.store.create('New CV workspace')
        canonical = self.store.create('Avery Morgan — labelled fictional sample')
        real = self.store.create('My actual career')
        self.assertEqual({x['id'] for x in candidates(self.store)}, {fixture['id'], blank['id']})
        self.assertIsNone(removable_reason(canonical))
        self.assertIsNone(removable_reason(real))

    def test_cleanup_is_recoverable_and_backed_up(self):
        blank = self.store.create('New CV workspace')
        original = deepcopy(blank)
        result = cleanup(self.store, apply=True)
        self.assertTrue(Path(result['backup']).is_file())
        self.assertEqual(result['removed'], [blank['id']])
        self.assertEqual(self.store.list(), [])
        self.assertEqual(self.store.trash_list()[0]['id'], blank['id'])
        self.assertEqual(self.store.restore_workspace(blank['id']), original)

    def test_preview_and_repeat_do_not_mutate_or_duplicate(self):
        self.store.create('New CV workspace')
        self.assertEqual(cleanup(self.store)['removed'], [])
        self.assertEqual(len(self.store.list()), 1)
        cleanup(self.store, apply=True)
        self.assertEqual(cleanup(self.store, apply=True)['removed'], [])
        self.assertEqual(len(self.store.trash_list()), 1)

    def test_blank_with_work_or_different_name_is_not_removed(self):
        state = self.store.create('New CV workspace')
        for field, value in [('messages', [{'role': 'user', 'content': 'Keep this work.'}]),
                             ('revision', 1), ('pending_profile', {'id': 'pending'}),
                             ('versions', [{'id': 'saved'}]), ('label', 'My new CV workspace')]:
            changed = deepcopy(state)
            changed[field] = value
            self.assertIsNone(removable_reason(changed))

    def test_blank_with_portfolio_is_not_removed(self):
        state = self.store.create('New CV workspace')
        with self.store.connect() as connection:
            connection.execute('CREATE TABLE portfolios (workspace TEXT PRIMARY KEY, state TEXT NOT NULL)')
            connection.execute('INSERT INTO portfolios VALUES (?, ?)', (state['id'], '{}'))
        self.assertEqual(candidates(self.store), [])

    def test_lookalike_fixture_label_or_real_person_is_not_removed(self):
        state = self.store.create('Showcase — synthetic live verification 20261022T043843Z')
        state['profile']['name'] = 'Real Person'
        self.assertIsNone(removable_reason(state))
        state['profile']['name'] = 'Avery Morgan'
        state['label'] += ' — edited by user'
        self.assertIsNone(removable_reason(state))

    def test_starter_gaining_portfolio_after_preview_is_not_removed(self):
        state = self.store.create('New CV workspace')
        def selected_then_used(store):
            selected = candidates(store)
            with store.connect() as connection:
                connection.execute('CREATE TABLE portfolios (workspace TEXT PRIMARY KEY, state TEXT NOT NULL)')
                connection.execute('INSERT INTO portfolios VALUES (?, ?)', (state['id'], '{}'))
            return selected
        with patch('server.cleanup_demo_workspaces.candidates', side_effect=selected_then_used):
            with self.assertRaisesRegex(ValueError, 'gained a portfolio'):
                cleanup(self.store, apply=True)
        self.assertEqual(self.store.get(state['id']), state)
        self.assertEqual(self.store.trash_list(), [])


if __name__ == '__main__':
    unittest.main()

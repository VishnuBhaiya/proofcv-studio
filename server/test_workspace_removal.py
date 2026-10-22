"""Recoverable workspace removal: only temporary synthetic databases are used."""
import tempfile
import unittest
from pathlib import Path
from .store import Store
from .service import Service


class WorkspaceRemovalTests(unittest.TestCase):
    def test_round_trip_preserves_every_field_and_other_workspaces(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'test.sqlite3')
            first = store.create('Synthetic removable')
            other = store.create('Synthetic retained')
            first.update(messages=[{'role': 'user', 'content': 'Synthetic'}],
                         draft={'test': 'draft'}, versions=[{'test': 'version'}])
            store.save(first)
            store.move_to_trash(first['id'], first['revision'])
            self.assertEqual(store.list(), [{'id': other['id'], 'label': other['label']}])
            with self.assertRaises(ValueError): store.get(first['id'])
            self.assertEqual(Store(store.path).trash_list()[0]['id'], first['id'])
            self.assertEqual(store.restore_workspace(first['id']), first)
            self.assertEqual(store.get(other['id']), other)
            self.assertEqual(store.trash_list(), [])

    def test_confirmation_and_revision_required(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'test.sqlite3')
            state = store.create('Synthetic')
            service = Service(store=store)
            for payload in ({'revision': 0}, {'revision': 99, 'accepted': True}):
                with self.assertRaises(ValueError):
                    service.action(state['id'], 'remove-workspace', payload)
            self.assertEqual(store.get(state['id']), state)
            service.action(state['id'], 'remove-workspace', {'revision': 0, 'accepted': True})
            with self.assertRaises(ValueError):
                service.action(state['id'], 'profile', {'revision': 0, 'patch': {'name': 'changed'}})
            self.assertEqual(service.action(state['id'], 'restore-workspace', {}), state)
            with self.assertRaises(ValueError): store.restore_workspace(state['id'])

    def test_purge_removes_only_trashed_workspaces_and_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'test.sqlite3')
            removed_one = store.create('Removed one')
            removed_two = store.create('Removed two')
            active = store.create('Active')
            store.move_to_trash(removed_one['id'], removed_one['revision'])
            store.move_to_trash(removed_two['id'], removed_two['revision'])
            service = Service(store=store)
            with self.assertRaises(ValueError):
                service.action('trash', 'purge-removed-workspaces', {'accepted': False})
            self.assertEqual(len(store.trash_list()), 2)
            self.assertEqual(service.action('trash', 'purge-removed-workspaces', {'accepted': True}), {'deleted': 2})
            self.assertEqual(store.trash_list(), [])
            self.assertEqual(store.get(active['id']), active)


if __name__ == '__main__': unittest.main()

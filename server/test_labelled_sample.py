import tempfile
import unittest
from pathlib import Path

from .seed_labelled_sample import LABEL, seed
from .store import Store


class LabelledSampleTests(unittest.TestCase):
    def test_avery_sample_is_detailed_and_has_two_targeted_cvs(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'test.sqlite3')
            workspace_id = seed(store)
            state = store.get(workspace_id)

            self.assertEqual(state['label'], LABEL)
            self.assertEqual(state['profile']['name'], 'Avery Morgan')
            self.assertEqual(len(state['profile']['projects']), 3)
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


if __name__ == '__main__':
    unittest.main()

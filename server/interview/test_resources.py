"""Learning links: every technical topic gets checked links, and a passing word does not pull in unrelated ones."""
import unittest

from . import resources
from .questions import load_bank


class ResourceTests(unittest.TestCase):
    def test_every_technical_topic_has_links_and_all_links_are_https(self):
        for q in [q for q in load_bank()['questions'] if q['round'] == 'technical']:
            links = resources.for_text(q['focus'], ' '.join(q.get('tags') or []))
            self.assertTrue(links, q['id'])
            self.assertLessEqual(len(links), resources.MAX_LINKS)
            self.assertTrue(all(l['url'].startswith('https://') and l['title'] and l['source'] for l in links))

    def test_best_matching_entry_wins(self):
        titles = [l['title'] for l in resources.for_text('retrieval-augmented generation pipelines', 'rag retrieval')]
        self.assertIn('Retrieval-augmented generation explained', titles)
        self.assertNotIn('GitHub Actions docs', titles)  # "pipelines" alone is not CI/CD.
        self.assertEqual(resources.for_text('Deploying computer-vision models')[0]['source'], 'ONNX Runtime')
        self.assertEqual(resources.for_text('nothing relevant here'), [])
        self.assertEqual(resources.for_text('Strong Python programming')[0]['title'], 'The Python Tutorial')


if __name__ == '__main__':
    unittest.main()

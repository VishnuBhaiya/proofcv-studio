"""Self-introduction deck and its PDF, without MiniLM."""
import re
import unittest

from .slides import build, cv_style, listed, render_pdf
from .test_content import TopicBackend
from .test_model_answer import FIT, JOB, PROFILE


class DeckTests(unittest.TestCase):
    def setUp(self):
        self.deck = build({**PROFILE, 'email': 'sam@example.test'}, FIT, JOB, TopicBackend())

    def test_slides_follow_the_story_of_an_introduction(self):
        self.assertEqual([s['kind'] for s in self.deck['slides']], ['title', 'fit', 'project', 'experience', 'growth', 'closing'])
        title = self.deck['slides'][0]
        self.assertEqual((title['title'], title['subtitle']), ('Sam Lee', 'Applying for AI Computer Vision Engineer'))
        self.assertTrue(title['notes'].startswith("Hi, I'm Sam."))

    def test_fit_and_growth_use_only_the_job_fit(self):
        slides = {s['kind']: s for s in self.deck['slides']}
        self.assertEqual([b['text'] for b in slides['fit']['bullets']], ['Python and OpenCV'])
        self.assertEqual([b['text'] for b in slides['growth']['bullets']], ['Working with large datasets', 'Video streaming and MLOps'])
        self.assertIn('[Say how you plan to close this gap.]', slides['growth']['notes'])

    def test_project_and_role_keep_cv_wording_on_slides(self):
        slides = {s['kind']: s for s in self.deck['slides']}
        self.assertEqual(slides['project']['bullets'][0]['text'], 'Built a YOLO tracker for warehouse video.')
        self.assertIn('Finalist, Campus Expo (2025)', slides['project']['bullets'][2]['text'])
        self.assertEqual(slides['experience']['bullets'][0]['text'], 'Served customers.')
        self.assertIn('I built a YOLO tracker', slides['project']['notes'])
        self.assertEqual(slides['closing']['bullets'][0]['text'], 'sam@example.test')

    def test_timing_estimate(self):
        words = sum(len(s['notes'].split()) for s in self.deck['slides'])
        self.assertEqual(self.deck['estimated_seconds'], round(words / 140 * 60))

    def test_empty_profile_still_gives_a_title_and_closing(self):
        deck = build({'name': '', 'projects': [], 'experience': 'None', 'achievements': '', 'summary_facts': []}, [], JOB, TopicBackend())
        self.assertEqual([s['kind'] for s in deck['slides']], ['title', 'closing'])
        self.assertEqual(deck['slides'][0]['title'], '[Your name]')

    def test_helpers(self):
        self.assertEqual(cv_style('I logged metrics.'), 'Logged metrics.')
        self.assertEqual(listed(['a', 'b', 'c']), 'a, b and c')


class PdfTests(unittest.TestCase):
    def test_one_page_per_slide_plus_the_script(self):
        deck = build(PROFILE, FIT, JOB, TopicBackend())
        deck['slides'][0]['bullets'].append({'text': 'Symbols outside the PDF font: ✓ 🎤', 'source': None})
        pdf = render_pdf(deck)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(len(re.findall(rb'/Type /Page\b', pdf)), len(deck['slides']) + 1)


if __name__ == '__main__':
    unittest.main()

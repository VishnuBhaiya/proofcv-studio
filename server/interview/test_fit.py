"""Strengths and gaps with the offline inspectable embedding backend; no model downloads."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ..retrieval import InspectableHashEmbeddingBackend
from .fit import REQUIREMENTS_PATH, assess, evidence_units, job_fit, load_requirements

ROOT = Path(__file__).resolve().parents[2]
JOBS = [json.loads(line) for line in (ROOT / 'data' / 'jobs.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
PROFILE = {
    'skills': ['Python', 'PyTorch', 'Docker'],
    'projects': [{'title': 'Lane Detector', 'description': 'Trained an object detection model. Measured precision and recall.', 'technologies': 'OpenCV, YOLO'}],
    'education': 'Bachelor of Computer Science | Example University | 2023 - 2026',
    'experience': 'None',
    'achievements': 'Hackathon winner (2025).\nPeer mentor (2024).',
    'summary_facts': ['Computer-vision student who builds reproducible prototypes.'],
}


class RequirementMapTests(unittest.TestCase):
    def test_map_covers_every_job_and_quotes_its_sources(self):
        data = load_requirements(JOBS)
        self.assertEqual(set(data['jobs']), {job['document_id'] for job in JOBS})
        self.assertTrue(all(data['jobs'][job_id] for job_id in data['jobs']))

    def test_misquoted_source_is_rejected(self):
        data = json.loads(REQUIREMENTS_PATH.read_text(encoding='utf-8'))
        data['jobs']['rag_agent_engineer'][0]['source'] = 'A PhD in quantum computing'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'map.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'not quoted'):
                load_requirements(JOBS, path)


class EvidenceTests(unittest.TestCase):
    def test_profile_is_split_into_labelled_facts_and_empty_sections_skipped(self):
        units = evidence_units(PROFILE)
        sources = [u['source'] for u in units]
        self.assertEqual(sources.count('project:0'), 3)  # two sentences plus technologies
        self.assertIn('achievements:0', sources)
        self.assertFalse(any(s.startswith('experience:') for s in sources))
        self.assertIn({'source': 'skill:1', 'label': 'Skill', 'text': 'PyTorch'}, units)

    def test_keyword_any_counts_as_strong_and_quotes_the_fact(self):
        units = evidence_units(PROFILE)
        requirement = {'id': 'x', 'text': 'TensorFlow or PyTorch', 'source': 's', 'level': 'required', 'category': 'skill', 'keywords': ['tensorflow', 'pytorch'], 'keyword_mode': 'any'}
        result = assess(requirement, units, np.zeros(len(units)))
        self.assertEqual(result['status'], 'strong')
        self.assertEqual(result['keywords_found'], ['pytorch'])
        self.assertEqual(result['evidence'][0]['text'], 'PyTorch')

    def test_half_of_all_keywords_needed_for_strong(self):
        units = evidence_units(PROFILE)
        requirement = {'id': 'x', 'text': 'Python, SQL and Linux', 'source': 's', 'level': 'required', 'category': 'skill', 'keywords': ['python', 'sql', 'linux']}
        self.assertEqual(assess(requirement, units, np.zeros(len(units)))['status'], 'partial')

    def test_eligibility_is_never_auto_judged_and_uses_its_own_section(self):
        units = evidence_units(PROFILE)
        requirement = {'id': 'x', 'text': 'Degree in computer science', 'source': 's', 'level': 'required', 'category': 'education'}
        similarities = np.array([0.9 if u['source'] == 'skill:0' else 0.3 for u in units])
        result = assess(requirement, units, similarities)
        self.assertEqual(result['status'], 'verify')
        self.assertTrue(all(e['source'].startswith('education:') for e in result['evidence']))

    def test_no_keywords_and_low_similarity_is_a_gap(self):
        units = evidence_units(PROFILE)
        requirement = {'id': 'x', 'text': 'Kubernetes', 'source': 's', 'level': 'preferred', 'category': 'skill', 'keywords': ['kubernetes']}
        result = assess(requirement, units, np.full(len(units), 0.2))
        self.assertEqual((result['status'], result['evidence']), ('gap', []))

    def test_job_fit_reports_counts_for_every_requirement(self):
        job = next(j for j in JOBS if j['document_id'] == 'computer_vision_engineer')
        requirements = load_requirements(JOBS)['jobs'][job['document_id']]
        result = job_fit(job, requirements, PROFILE, InspectableHashEmbeddingBackend())
        self.assertEqual(sum(result['counts'].values()), len(requirements))
        statuses = {r['id']: r['status'] for r in result['requirements']}
        self.assertEqual(statuses['cve-01'], 'verify')
        self.assertEqual(statuses['cve-03'], 'strong')


if __name__ == '__main__':
    unittest.main()

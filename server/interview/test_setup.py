"""Interview Coach setup: skills to learn, job labels and form checks."""
import unittest
from datetime import date

from .setup import focus, job_list, skills_to_learn, validate

TODAY = date(2026, 10, 25)
FIT = [{'id': 'r1', 'text': 'Python', 'level': 'required', 'category': 'skill', 'status': 'strong'},
       {'id': 'r2', 'text': 'Docker', 'level': 'preferred', 'category': 'skill', 'status': 'gap'},
       {'id': 'r3', 'text': 'Kubernetes', 'level': 'required', 'category': 'skill', 'status': 'gap'},
       {'id': 'r4', 'text': 'Testing practice', 'level': 'required', 'category': 'practice', 'status': 'partial'},
       {'id': 'r5', 'text': "Bachelor's degree", 'level': 'required', 'category': 'education', 'status': 'verify'},
       {'id': 'r6', 'text': 'Teamwork', 'level': 'required', 'category': 'soft', 'status': 'gap'}]
JOBS = [{'document_id': 'healthcare_ml_engineer', 'title': 'Machine Learning Engineer'},
        {'document_id': 'recommendation_systems_ml_engineer', 'title': 'Machine Learning Engineer'},
        {'document_id': 'rag_agent_engineer', 'title': 'AI Engineer'}, {'document_id': 'agentic_ai_engineer', 'title': 'AI Engineer'},
        {'document_id': 'computer_vision_engineer', 'title': 'AI Computer Vision Engineer'}]


class SetupTests(unittest.TestCase):
    def test_skills_to_learn_are_technical_gaps_most_important_first(self):
        self.assertEqual([s['id'] for s in skills_to_learn(FIT)], ['r3', 'r2', 'r4'])  # No degree, no soft skill, no strength.

    def test_same_titles_get_a_focus_label(self):
        self.assertEqual([focus(j, JOBS) for j in JOBS], ['Healthcare', 'Recommendation systems', 'RAG agent', 'Agentic', None])
        listed = job_list(JOBS, [{'document_id': 'rag_agent_engineer', 'score': 0.61}], 'computer_vision_engineer')
        self.assertEqual((listed[2]['match_score'], listed[4]['cv_target'], listed[0]['match_score']), (0.61, True, None))

    def test_validate_cleans_and_rejects(self):
        form = {'job': 'rag_agent_engineer', 'interview_date': '2026-11-08', 'learn_skills': ['r3', 'r3'], 'stage': 'final', 'daily_minutes': 120, 'notes': '  '}
        clean = validate(form, {'rag_agent_engineer'}, {'r3', 'r2'}, TODAY)
        self.assertEqual(clean, {'job': 'rag_agent_engineer', 'interview_date': '2026-11-08', 'learn_skills': ['r3'], 'stage': 'final', 'daily_minutes': 120, 'notes': ''})
        self.assertEqual(validate({**form, 'learn_skills': []}, {'rag_agent_engineer'}, set(), TODAY)['learn_skills'], [])  # Learning is optional.
        with self.assertRaises(ValueError):
            validate({**form, 'notes': 'x' * 501}, {'rag_agent_engineer'}, {'r3'}, TODAY)


if __name__ == '__main__':
    unittest.main()

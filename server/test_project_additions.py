import unittest
from copy import deepcopy
from .agent import run_cv_turn
from .test_system import complete_profile, SequenceModel
from .cv import generate


class ProjectAdditionTests(unittest.TestCase):
    def test_addition_preserves_existing_project_before_acceptance(self):
        for field in ('add_projects', 'profile_patch'):
            with self.subTest(field=field):
                profile = complete_profile()
                state = dict(profile=profile, confirmed_profile=deepcopy(profile), revision=0,
                             confirmed_revision=0, draft=None)
                generate(state, {'document_id':'test','title':'Developer','description':'Python'},
                         SequenceModel([dict(summary_fact_ids=['education'], skills=['Python'],
                             project_order=[0], section_order=['projects','education'], rationale='Test')]))
                before = deepcopy(state['draft'])
                project = dict(title='Solar Vision', description='Inspected solar panels.', technologies='Python')
                patch = {field: [project] if field == 'add_projects' else {'projects':[project]}}
                model = SequenceModel([dict(type='tool_call',tool='update_cv',arguments={'patch':patch})])
                run_cv_turn(state, 'Add a new project Solar Vision', model, lambda _: None)
                self.assertEqual(state['draft'], before)
                proposed = state['pending_cv']['draft']
                self.assertEqual(proposed['profile']['projects'], profile['projects'] + [project])
                self.assertEqual(proposed['selection']['project_order'], [0, 1])

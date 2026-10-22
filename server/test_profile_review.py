import tempfile
import unittest
from pathlib import Path
from .store import Store
from .service import Service
from .test_system import SequenceModel


class ProfileReviewTests(unittest.TestCase):
    def test_skills_destination_updates_only_selected_project(self):
        from .test_system import complete_profile
        from copy import deepcopy
        for destination in ('skills', 'project'):
            with self.subTest(destination=destination), tempfile.TemporaryDirectory() as directory:
                store = Store(Path(directory) / 'review.sqlite3')
                service = Service(store=store, model=SequenceModel([
                    {'type':'final_answer','answer':'All required fields are present. Review the form and use Confirm profile when it is accurate.'}
                ]))
                state = store.create('Destination test')
                state['profile'] = complete_profile()
                state['profile']['projects'].append({'title':'Website','description':'Built a website.','technologies':'React, CSS'})
                original = deepcopy(state['profile']['projects'])
                state['pending_profile'] = {'id':'p','revision':0,'patch':{'skills':['Python','SQL']},'source':'Skills','skill_options':['CSS','React','TypeScript']}
                store.save(state)
                data = {'revision':0,'proposal_id':'p','choice':'accept','patch':{'skills':['Python','SQL','CSS','React','TypeScript']}}
                if destination == 'project':
                    data['project_skills'] = {'project_index':1,'skills':['CSS','React','TypeScript']}
                result = service.action(state['id'], 'review-profile', data)
                self.assertEqual(result['profile']['projects'][0], original[0])
                self.assertEqual(result['profile']['projects'][1]['technologies'], 'React, CSS, TypeScript' if destination == 'project' else 'React, CSS')
                self.assertIn('TypeScript', result['profile']['skills'])
                self.assertIsNone(result['confirmed_revision'])

    def test_project_accept_with_optional_skill_checkbox(self):
        from .test_system import complete_profile
        from copy import deepcopy
        for checked in (False, True):
            with self.subTest(checked=checked), tempfile.TemporaryDirectory() as directory:
                store = Store(Path(directory) / 'review.sqlite3')
                service = Service(store=store, model=SequenceModel([
                    {'type':'final_answer','answer':'All required fields are present. Review the form and use Confirm profile when it is accurate.'}
                ]))
                state = store.create('Checkbox regression')
                state['profile'] = complete_profile()
                projects = deepcopy(state['profile']['projects'])
                projects[0]['technologies'] = 'Python, R'
                state['pending_profile'] = {'id':'p','revision':0,'patch':{'projects':projects},'source':'I used R','skill_options':['R']}
                store.save(state)
                patch = {'projects':projects}
                if checked:
                    patch['skills'] = ['Python', 'SQL', 'R', 'r', ' ']
                result = service.action(state['id'], 'review-profile', {'revision':0,'proposal_id':'p','choice':'accept','patch':patch})
                self.assertEqual(result['profile']['projects'][0]['technologies'], 'Python, R')
                self.assertEqual(result['profile']['skills'], ['Python','SQL','R'] if checked else ['Python','SQL'])
                self.assertNotIn('pending_profile', result)
                self.assertIsNone(result['confirmed_revision'])

    def test_proposal_stops_without_extra_provider_call(self):
        from .agent import run_turn
        from .store import blank_profile
        state = {'profile': blank_profile(), 'revision': 0, 'confirmed_revision': None, 'messages': []}
        result = run_turn(state, 'My name is Alex', SequenceModel([
            {'type':'update_profile','arguments':{'patch':{'name':'Alex'}}}
        ]), lambda p: {}, lambda s: None, require_review=True)
        self.assertEqual(result['stop_reason'], 'pending_review')
        self.assertEqual(result['profile']['name'], '')
        self.assertEqual(result['pending_profile']['patch']['name'], 'Alex')

    def test_false_success_is_blocked_after_failed_tool(self):
        from .agent import run_turn
        from .store import blank_profile
        state = {'profile': blank_profile(), 'revision': 0, 'confirmed_revision': None, 'messages': []}
        result = run_turn(state, 'Python', SequenceModel([
            {'type':'tool_call','tool':'write_anything','arguments':{}},
            {'type':'final_answer','answer':'I have updated your profile.'},
            {'type':'final_answer','answer':'I have updated your profile.'}
        ]), lambda p: {}, lambda s: None, require_review=True)
        self.assertEqual(result['stop_reason'], 'invalid_response')
        self.assertIn('unchanged', result['messages'][-1]['content'])
        self.assertNotIn('pending_profile', result)

    def test_accept_edited_proposal_is_separate_from_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'review.sqlite3')
            service = Service(store=store, model=SequenceModel([
                {'type': 'tool_call', 'tool': 'get_profile', 'arguments': {}},
                {'type': 'tool_call', 'tool': 'update_profile', 'arguments': {'patch': {'name': 'Parth', 'education': 'Currently pursuing a Bachelor of Artificial Intelligence'}}},
                {'type': 'final_answer', 'answer': 'What email address should appear on your CV?'}]))
            original = store.create('Synthetic review')
            state = service.action(original['id'], 'chat', {'revision': 0, 'message': "I am Parth studying bachelor of AI"})
            self.assertEqual(state['profile'], original['profile'])
            self.assertEqual(state['revision'], 0)
            proposal = state['pending_profile']
            self.assertEqual(Store(store.path).get(state['id'])['pending_profile'], proposal)
            with self.assertRaises(ValueError): service.action(state['id'], 'confirm', {'revision': 0, 'accepted': True})
            state = service.action(state['id'], 'review-profile', {'revision': 0, 'proposal_id': proposal['id'], 'choice': 'accept', 'patch': {'name': 'Parth Test', 'education': proposal['patch']['education']}})
            self.assertEqual(state['profile']['name'], 'Parth Test')
            self.assertIsNone(state['confirmed_revision'])
            self.assertNotIn('pending_profile', state)
            self.assertIn('email', state['messages'][-1]['content'])
            self.assertEqual(state['stop_reason'], 'followup_question')
            self.assertEqual(state['audit_runs'][-1]['prompt_version'], 'profile-followup-agent-v1')
            self.assertEqual(state['audit_runs'][-1]['trace'][-1]['observation']['validated'], 'model_chosen_followup')
            with self.assertRaises(ValueError): service.action(state['id'], 'review-profile', {'revision': 1, 'proposal_id': proposal['id'], 'choice': 'accept'})

    def test_dismiss_does_not_change_profile_or_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'review.sqlite3')
            service = Service(store=store)
            state = store.create('Synthetic dismissal')
            state['pending_profile'] = {'id': 'proposal', 'revision': 0, 'patch': {'name': 'Wrong'}, 'source': 'Synthetic'}
            store.save(state)
            result = service.action(state['id'], 'review-profile', {'revision': 0, 'proposal_id': 'proposal', 'choice': 'dismiss'})
            self.assertEqual(result['profile'], state['profile'])
            self.assertEqual(result['revision'], 0)
            self.assertNotIn('pending_profile', result)

    def test_followup_question_is_a_validated_model_action(self):
        from .agent import run_followup_turn
        from .store import blank_profile
        state = {'profile': blank_profile(), 'revision': 0, 'confirmed_revision': None,
                 'messages': [], 'audit_runs': []}
        state['profile']['name'] = 'Avery Morgan'
        result = run_followup_turn(state, SequenceModel([
            {'type':'tool_call','tool':'get_profile','arguments':{}},
            {'type':'final_answer','answer':'Which email address would you like shown on your CV?'}
        ]), lambda s: None)
        self.assertEqual(result['stop_reason'], 'followup_question')
        self.assertEqual(result['trace'][0]['action']['tool'], 'get_profile')
        self.assertEqual(result['trace'][1]['observation'],
                         {'validated':'model_chosen_followup','missing_field':'email'})

    def test_complete_profile_gets_no_extra_factual_question(self):
        from .agent import run_followup_turn
        from .test_system import complete_profile
        state = {'profile': complete_profile(), 'revision': 1, 'confirmed_revision': None,
                 'messages': [], 'audit_runs': []}
        result = run_followup_turn(state, SequenceModel([
            {'type':'final_answer','answer':'All required fields are present. Please review the form and use Confirm profile when it is accurate.'}
        ]), lambda s: None)
        self.assertEqual(result['stop_reason'], 'profile_complete')
        self.assertNotIn('?', result['messages'][-1]['content'])
        self.assertEqual(result['trace'][-1]['observation']['validated'],
                         'profile_complete_no_extra_question')

    def test_plural_achievement_followup_is_accepted(self):
        from .agent import run_followup_turn
        from .test_system import complete_profile
        state = {'profile': complete_profile(), 'revision': 1, 'confirmed_revision': None,
                 'messages': [], 'audit_runs': []}
        state['profile']['achievements'] = ''
        result = run_followup_turn(state, SequenceModel([
            {'type':'final_answer','answer':'What awards, certifications, or notable achievements would you like to include?'}
        ]), lambda s: None)
        self.assertEqual(result['stop_reason'], 'followup_question')
        self.assertEqual(result['trace'][-1]['observation']['missing_field'], 'achievements')


if __name__ == '__main__': unittest.main()

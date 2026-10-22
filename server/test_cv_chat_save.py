import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from .store import Store
from .service import Service
from .cv import generate
from .test_system import complete_profile, SequenceModel
from .gemini import GeminiError

class UnavailableModel:
    name='gemini:unavailable'
    def decide(self, messages, context):
        raise GeminiError('All configured Gemini models are unavailable.', retryable=True)

class ChatSaveTests(unittest.TestCase):
    def test_cv_chat_skill_addition_keeps_only_named_skill(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 's.sqlite3')
            state = store.create('Skill delta test')
            state['profile'] = complete_profile()
            state['profile']['achievements'] = 'Scholarship\n\nAI showcase finalist'
            state['profile']['projects'].append({
                'title': 'Unrelated Website',
                'description': 'Built a marketing website.',
                'technologies': 'HTML, CSS'})
            state['confirmed_profile'] = deepcopy(state['profile'])
            state['confirmed_revision'] = state['revision']
            generate(state, {'document_id': 'test', 'title': 'Developer', 'description': 'Python'},
                     SequenceModel([{'summary_fact_ids': ['education'], 'skills': ['Python', 'SQL'],
                                     'project_order': [0], 'section_order': ['projects', 'education', 'achievements'], 'rationale': 'Test'}]))
            store.save(state)
            all_skills = state['profile']['skills'] + ['Docker', 'Kubernetes', 'Terraform', 'React', 'TensorFlow']
            model = SequenceModel([{'type': 'tool_call', 'tool': 'update_cv', 'arguments': {
                'patch': {
                    'profile_patch': {'skills': all_skills, 'achievements': 'Docker'},
                    'skills': all_skills,
                    'project_order': [0, 1],
                    'summary_fact_ids': ['education', 'project:1']}}}])
            service = Service(store=store, model=model)
            result = service.action(state['id'], 'cv-chat', {'revision': 0, 'message': 'Add Docker in skills'})
            self.assertEqual(result['pending_cv']['draft']['profile']['skills'], ['Python', 'SQL', 'Docker'])
            self.assertEqual(result['pending_cv']['profile']['skills'], ['Python', 'SQL', 'Docker'])
            self.assertEqual(result['pending_cv']['profile']['achievements'], 'Scholarship\n\nAI showcase finalist')
            self.assertEqual(result['pending_cv']['draft']['selection']['project_order'], [0])
            self.assertEqual(result['pending_cv']['draft']['selection']['skills'], ['Python', 'SQL', 'Docker'])
            result = service.action(state['id'], 'review-cv', {
                'revision': 0, 'choice': 'accept', 'proposal_id': result['pending_cv']['id']})
            self.assertEqual(result['profile']['skills'], ['Python', 'SQL', 'Docker'])
            self.assertEqual(result['profile']['achievements'], 'Scholarship\n\nAI showcase finalist')
            self.assertEqual(result['draft']['selection']['project_order'], [0])

    def test_confirmed_profile_refresh_preserves_job_specific_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 's.sqlite3')
            state = store.create('Refresh selection test')
            state['profile'] = complete_profile()
            state['profile']['projects'].append({
                'title': 'Unrelated Website',
                'description': 'Built a marketing website.',
                'technologies': 'HTML, CSS'})
            state['confirmed_profile'] = deepcopy(state['profile'])
            state['confirmed_revision'] = state['revision']
            generate(state, {'document_id': 'vision', 'title': 'Computer Vision Engineer',
                             'description': 'Python computer vision'}, SequenceModel([{
                'summary_fact_ids': ['education'], 'skills': ['Python'],
                'project_order': [0], 'section_order': ['projects', 'education'],
                'rationale': 'Use the technical project.'}]))
            store.save(state)
            edited = deepcopy(state['profile'])
            edited['skills'].append('MLOps')
            result = Service(store=store, model=SequenceModel([])).action(
                state['id'], 'profile', {'revision': 0, 'patch': edited})
            self.assertEqual(result['draft']['selection']['project_order'], [0])
            self.assertEqual(result['draft']['selection']['skills'], ['Python', 'MLOps'])

    def test_contact_fields_stage_and_sync(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 's.sqlite3')
            state = store.create('Contact test')
            state['profile'] = complete_profile()
            state['confirmed_profile'] = deepcopy(state['profile'])
            state['confirmed_revision'] = state['revision']
            generate(state, {'document_id':'test','title':'Developer','description':'Python'}, SequenceModel([{'summary_fact_ids':['education'],'skills':['Python'],'project_order':[0],'section_order':['projects','education'],'rationale':'Test'}]))
            store.save(state)
            changes = {'location':'Sydney','linkedin':'https://www.linkedin.com/in/example','github':'https://github.com/example','portfolio':'https://example.com'}
            model = SequenceModel([{'type':'tool_call','tool':'update_cv','arguments':{'patch':{'profile_patch':changes}}}])
            service = Service(store=store, model=model)
            result = service.action(state['id'], 'cv-chat', {'revision':0,'message':'Update my location and links'})
            self.assertNotEqual(result['profile'].get('location'), 'Sydney')
            self.assertEqual(result['pending_cv']['draft']['profile']['location'], 'Sydney')
            result = service.action(state['id'], 'review-cv', {'revision':0,'choice':'accept','proposal_id':result['pending_cv']['id']})
            for key, value in changes.items():
                self.assertEqual(result['profile'][key], value)
                self.assertEqual(result['draft']['profile'][key], value)

    def test_chat_uses_unsaved_design(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'s.sqlite3')
            state=store.create('Chat test')
            state['profile']=complete_profile()
            state['confirmed_profile']=deepcopy(state['profile'])
            state['confirmed_revision']=state['revision']
            generate(state,{'document_id':'test','title':'Developer','description':'Python'},SequenceModel([{'summary_fact_ids':['education'],'skills':['Python'],'project_order':[0],'section_order':['projects','education'],'rationale':'Test'}]))
            store.save(state)
            design={**state['draft']['design'],'size':'large'}
            model=SequenceModel([{'type':'tool_call','tool':'update_cv','arguments':{'patch':{'design':{'font':'serif'}}}}])
            result=Service(store=store,model=model).action(state['id'],'cv-chat',{'revision':0,'message':'Use serif','draft_patch':{'design':design}})
            self.assertEqual(result['draft']['design']['size'],'large')
            self.assertNotEqual(result['draft']['design']['font'],'serif')
            self.assertEqual(result['pending_cv']['draft']['design']['font'],'serif')
            self.assertEqual(result['cv_stop_reason'],'pending_review')
            result=Service(store=store,model=model).action(state['id'],'review-cv',{'revision':0,'choice':'accept','proposal_id':result['pending_cv']['id']})
            self.assertEqual(result['draft']['design']['font'],'serif')
            self.assertNotIn('pending_cv',result)
            original=deepcopy(result['draft'])
            ats=SequenceModel([{'type':'tool_call','tool':'update_cv','arguments':{'patch':{'template':'classic'}}}])
            service=Service(store=store,model=ats)
            result=service.action(state['id'],'cv-chat',{'revision':0,'message':'Make this ATS-friendly'})
            self.assertEqual(result['draft'],original)
            proposed=result['pending_cv']['draft']
            self.assertTrue(proposed['design']['ats'])
            self.assertEqual(proposed['design']['font'],'sans')
            self.assertEqual(proposed['design']['header'],'left')
            result=service.action(state['id'],'review-cv',{'revision':0,'choice':'dismiss','proposal_id':result['pending_cv']['id']})
            self.assertEqual(result['draft'],original)
            model=SequenceModel([{'type':'tool_call','tool':'update_cv','arguments':{'patch':{'add_skills':['RAG'],'summary_text':'A student building Python projects.'}}}])
            service=Service(store=store,model=model)
            result=service.action(state['id'],'cv-chat',{'revision':0,'message':'Add RAG and improve summary'})
            self.assertNotIn('RAG',result['profile']['skills'])
            result=service.action(state['id'],'review-cv',{'revision':0,'choice':'accept','proposal_id':result['pending_cv']['id']})
            self.assertIn('RAG',result['profile']['skills'])
            self.assertIn('RAG',result['draft']['selection']['skills'])
            self.assertEqual(result['draft']['summary'],'A student building Python projects.')
            self.assertIn(result['draft']['summary'],result['profile']['summary_facts'])
            self.assertEqual(result['draft']['profile'],result['confirmed_profile'])
            self.assertEqual(result['revision'],1)
            old_job=result['draft']['job']['document_id']
            result=service.action(state['id'],'profile',{'revision':1,'patch':{'achievements':'AWS industry experience'}})
            result=service.action(state['id'],'confirm',{'revision':2,'accepted':True})
            self.assertEqual(result['draft']['job']['document_id'],old_job)
            self.assertEqual(result['draft']['revision'],result['revision'])
            self.assertEqual(result['draft']['profile']['achievements'],'AWS industry experience')
            self.assertNotIn('stale',str(result).lower())
            model=SequenceModel([{'type':'tool_call','tool':'update_cv','arguments':{'patch':{'profile_patch':{'achievements':'AWS industry leader'}}}}])
            service=Service(store=store,model=model)
            result=service.action(state['id'],'cv-chat',{'revision':2,'message':'Add AWS industry in achievement section'})
            self.assertEqual(result['profile']['achievements'],'AWS industry experience')
            self.assertEqual(result['pending_cv']['draft']['profile']['achievements'],'AWS industry leader')
            result=service.action(state['id'],'review-cv',{'revision':2,'choice':'accept','proposal_id':result['pending_cv']['id']})
            self.assertEqual(result['profile']['achievements'],'AWS industry leader')

            service=Service(store=store,model=UnavailableModel())
            result=service.action(state['id'],'cv-chat',{'revision':3,'message':'Make this ATS-friendly'})
            self.assertTrue(result['pending_cv']['draft']['design']['ats'])
            service.action(state['id'],'review-cv',{'revision':3,'choice':'dismiss','proposal_id':result['pending_cv']['id']})
            result=service.action(state['id'],'cv-chat',{'revision':3,'message':'Add Docker in skill'})
            self.assertEqual(result['pending_cv']['draft']['profile']['skills'], ['Python', 'SQL', 'RAG', 'Docker'])

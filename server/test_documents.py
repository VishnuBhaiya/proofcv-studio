import base64
import tempfile
import unittest
from pathlib import Path
from .documents import propose_document
from .store import Store
from .service import Service
from .test_system import SequenceModel, complete_profile

class DocumentTests(unittest.TestCase):
    def test_full_resume_fields_review_accept_and_repeat(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/'test.sqlite3')
            state = store.create('Full resume')
            state['profile'] = complete_profile()
            original_projects = state['profile']['projects'][:]
            store.save(state)
            patch = {'email':'person@example.test','phone':'0400000011','location':'Sydney',
                     'linkedin':'https://linkedin.com/in/example','github':'https://github.com/example',
                     'portfolio':'https://example.test','goal':'AI internship',
                     'skills':['Python','TensorFlow'],
                     'projects':[{'title':'New vision project','description':'Trained and compared image models.','technologies':'Python, TensorFlow'}],
                     'experience':'Developer at Example\nBuilt SQL workflows and maintained tests.',
                     'achievements':'Faculty scholarship',
                     'summary_facts':['Languages: English and Hindi','Availability: immediately']}
            data = {'filename':'resume.txt','content':base64.b64encode(b'Full resume fixture').decode()}
            propose_document(state, data, SequenceModel([{'patch':patch}]))
            self.assertNotEqual(state['profile'].get('location'), 'Sydney')
            staged = state['pending_profile']['patch']
            self.assertEqual(len(staged['projects']), len(original_projects)+1)
            store.save(state)
            result = Service(store=store, model=SequenceModel([
                {'type':'final_answer','answer':'All required fields are present. Review the form and use Confirm profile when it is accurate.'}
            ])).action(state['id'], 'review-profile',
                {'revision':0,'proposal_id':state['pending_profile']['id'],'choice':'accept','patch':staged})
            self.assertEqual(result['profile']['location'], 'Sydney')
            self.assertEqual(result['profile']['projects'][-1]['title'], 'New vision project')
            self.assertIn('Languages: English and Hindi', result['profile']['summary_facts'])
            self.assertIn('TensorFlow', result['profile']['skills'])
            with self.assertRaisesRegex(ValueError, 'No new readable'):
                propose_document(result, data, SequenceModel([{'patch':patch}]))

    def test_extract_stages_and_accept_with_local_edits(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'test.sqlite3')
            state=store.create('Import')
            state['profile']=complete_profile()
            model=SequenceModel([{'patch':{'education':'Bachelor of Computing, Example University','summary_facts':['WAM: 78','Subject: Databases — 82']},'skill_options':['SQL'],'warnings':['GPA not stated.']}])
            propose_document(state,{'filename':'marks.txt','content':base64.b64encode(b'Bachelor of Computing, Example University. WAM:78. Databases:82.').decode()},model)
            self.assertNotEqual(state['profile']['education'],'Bachelor of Computing, Example University')
            self.assertEqual(state['pending_profile']['warnings'],['GPA not stated.'])
            store.save(state)
            local={**state['profile'],'phone':'0400000099'}
            patch={**state['pending_profile']['patch'],'skills':['Python','SQL','R']}
            result=Service(store=store,model=SequenceModel([
                {'type':'final_answer','answer':'All required fields are present. Review the form and use Confirm profile when it is accurate.'}
            ])).action(state['id'],'review-profile',{'revision':0,'proposal_id':state['pending_profile']['id'],'choice':'accept','patch':patch,'local_profile':local})
            self.assertEqual(result['profile']['phone'],'0400000099')
            self.assertIn('R',result['profile']['skills'])
            self.assertIn('WAM: 78',result['profile']['summary_facts'])
            self.assertIsNone(result['confirmed_revision'])
            self.assertNotIn('pending_profile',result)

    def test_invalid_file_and_unsupported_claim_fields_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            state=Store(Path(folder)/'test.sqlite3').create('Import')
            with self.assertRaises(ValueError):
                propose_document(state,{'filename':'fake.pdf','content':base64.b64encode(b'not a pdf').decode()},SequenceModel([]))
            with self.assertRaises(ValueError):
                propose_document(state,{'filename':'a.txt','content':base64.b64encode(b'Hello').decode()},SequenceModel([{'patch':{'unrecognised_field':['Invented']}}]))
            self.assertNotIn('pending_profile',state)

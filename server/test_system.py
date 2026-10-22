import json
import tempfile
import unittest
from io import BytesIO
from pypdf import PdfReader
from copy import deepcopy
from pathlib import Path
from .store import Store, blank_profile
from .service import Service
from .retrieval import JobRetriever, InspectableHashEmbeddingBackend
from .gemini import GeminiError
from .agent import run_turn
from .cv import facts, generate, validate_draft, edit, tailor_selection


def complete_profile():
    return dict(name='Test Candidate',email='test@example.test',phone='0400 000 001',
        education='Bachelor of Computing, Test University, 2026',skills=['Python','SQL'],
        projects=[dict(title='Test API',description='Built a Python API with SQL queries.',technologies='Python, SQL')],
        experience='None',achievements='None',goal='Graduate AI engineer',summary_facts=[])


class SequenceModel:
    name='scripted-test-model'
    def __init__(self, actions): self.actions=iter(actions)
    def decide(self, messages, context):
        result=next(self.actions)
        if isinstance(result, Exception): raise result
        return json.dumps(result)


class SystemTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.directory.name)/'test.sqlite3')
        self.service=Service(store=self.store, model=SequenceModel([]))
        self.service.retriever=JobRetriever(self.service.jobs,InspectableHashEmbeddingBackend())
        self.state=self.store.create('Synthetic')
    def tearDown(self): self.directory.cleanup()
    def action(self, operation, **data):
        self.state=self.service.action(self.state['id'],operation,{'revision':self.state['revision'],**data})
        return self.state
    def confirm(self):
        self.action('profile',patch=complete_profile())
        self.action('confirm',accepted=True)
    def test_tailoring_rationale_suffix_is_idempotent(self):
        profile = complete_profile()
        job = {'document_id':'test','title':'Graduate AI Engineer','description':'Python and SQL'}
        selection = {'summary_fact_ids':['education'],'skills':['Python','SQL'],
                     'project_order':[0],'section_order':['projects','education'],
                     'rationale':'Prioritise relevant evidence.'}
        first = tailor_selection(selection, profile, job)
        second = tailor_selection(first, profile, job)
        suffix = 'ProofCV applied confirmed-evidence relevance checks for this target job.'
        self.assertEqual(second['rationale'].count(suffix), 1)
        self.assertIn('Test API', second['rationale'])
        self.assertIn('summary sources education', second['rationale'])
    def test_job_search_is_a_real_agent_tool_decision(self):
        self.confirm()
        original = deepcopy(self.state['profile'])
        self.service.model = SequenceModel([
            {'type':'tool_call','tool':'retrieve_jobs','arguments':{}},
        ])
        self.action('find-jobs')
        self.assertEqual(len(self.state['retrieval']['results']), 3)
        self.assertEqual(self.state['stop_reason'], 'retrieval_complete')
        self.assertEqual(self.state['trace'][0]['action']['tool'], 'retrieve_jobs')
        self.assertEqual(self.state['profile'], original)
        self.assertTrue(self.state['trace'][0]['executed'])

    def test_agent_job_search_reports_provider_failure_without_fake_trace(self):
        self.confirm()
        self.service.model = SequenceModel([GeminiError('Unavailable', retryable=True)])
        with self.assertRaises(GeminiError):
            self.action('find-jobs')
        saved = self.store.get(self.state['id'])
        self.assertIsNone(saved['retrieval'])
        self.assertEqual(saved['stop_reason'], 'provider_error')
        self.assertFalse(saved['trace'][0]['executed'])

    def test_job_search_requires_confirmation(self):
        with self.assertRaises(ValueError):
            self.action('find-jobs')

    def test_explicit_confirmation_and_missing_fields(self):
        with self.assertRaises(ValueError): self.action('confirm',accepted=True)
        self.action('profile',patch=complete_profile())
        with self.assertRaises(ValueError): self.action('confirm',accepted=False)
        self.action('confirm',accepted=True)
        self.assertEqual(self.state['confirmed_revision'],self.state['revision'])
    def test_correction_invalidates_retrieval_and_confirmation(self):
        self.confirm(); self.action('retrieve')
        self.assertEqual(len(self.state['retrieval']['results']),3)
        self.action('profile',patch={'skills':['SQL']})
        self.assertIsNone(self.state['retrieval'])
        with self.assertRaises(ValueError): self.action('retrieve')
    def test_persistence_and_cross_user(self):
        self.confirm()
        other=self.store.create('Different person')
        self.assertEqual(other['profile'],blank_profile())
        self.assertEqual(Store(self.store.path).get(self.state['id'])['profile']['name'],'Test Candidate')
        with self.assertRaises(ValueError): self.store.get('../../other')
    def test_stale_revision_rejected(self):
        self.confirm()
        with self.assertRaises(ValueError): self.service.action(self.state['id'],'profile',{'revision':0,'patch':{'name':'Overwrite'}})
    def test_whitespace_and_invalid_phone_do_not_confirm(self):
        profile=complete_profile();profile['name']='   ';profile['phone']='None'
        self.action('profile',patch=profile)
        with self.assertRaises(ValueError): self.action('confirm',accepted=True)
    def test_agent_tool_observations_and_final_stop(self):
        model=SequenceModel([{'type':'tool_call','tool':'get_profile','arguments':{}},
            {'type':'tool_call','tool':'update_profile','arguments':{'patch':{'name':'Alex'}}},
            {'type':'final_answer','answer':'What is your email address?'}])
        result=run_turn(self.state,'My name is Alex.',model,self.service.retrieve,self.store.save)
        self.assertEqual(result['profile']['name'],'Alex')
        self.assertEqual(result['stop_reason'],'final_answer')
        self.assertEqual(result['trace'][1]['revision_after'],1)
    def test_repeated_action_stops(self):
        action={'type':'tool_call','tool':'get_profile','arguments':{}}
        result=run_turn(self.state,'Hello',SequenceModel([action,action]),self.service.retrieve,self.store.save)
        self.assertEqual(result['stop_reason'],'repeated_action')
        self.assertFalse(result['trace'][-1]['executed'])
    def test_provider_failure_preserves_input(self):
        with self.assertRaises(GeminiError):
            run_turn(self.state,'Keep this message',SequenceModel([GeminiError('Simulated 503',retryable=True)]),self.service.retrieve,self.store.save)
        saved=self.store.get(self.state['id'])
        self.assertEqual(saved['messages'][-1]['content'],'Keep this message')
        self.assertEqual(saved['stop_reason'],'provider_error')
    def test_model_cannot_confirm_or_choose_other_user(self):
        result=run_turn(self.state,'Confirm',SequenceModel([
            {'type':'tool_call','tool':'confirm_profile','arguments':{}},
            {'type':'tool_call','tool':'update_profile','arguments':{'user_id':'other','patch':{'name':'Wrong'}}},
            {'type':'final_answer','answer':'Please review your profile.'}]),self.service.retrieve,self.store.save)
        self.assertIsNone(result['confirmed_revision'])
        self.assertEqual(result['profile']['name'],'')
        self.assertTrue(all(not t['executed'] for t in result['trace']))
    def test_missing_achievement_is_not_no_achievement(self):
        from .agent import validate_explicit_empty_fields
        with self.assertRaises(ValueError):
            validate_explicit_empty_fields({'achievements':'None'},'I have no employment experience.')
        validate_explicit_empty_fields({'experience':'None'},'I have no employment experience.')
        validate_explicit_empty_fields({'achievements':'None'},'I have no achievements to add.')
        validate_explicit_empty_fields({'achievements':'None'},'None','Do you have any achievements?')
        with self.assertRaises(ValueError):
            validate_explicit_empty_fields({'achievements':'None'},'None','What is your work experience?')
    def test_cv_claim_guards_and_undo(self):
        self.confirm()
        choice=dict(summary_fact_ids=['education','project:0'],skills=['Python'],project_order=[0],
            section_order=['projects','education','experience','achievements'],rationale='Lead with the relevant API project.')
        generate(self.state,self.service.jobs[0],SequenceModel([choice]))
        validate_draft(self.state)
        original=deepcopy(self.state['draft'])
        with self.assertRaises(ValueError): edit(self.state,{'summary':'Won a Nobel prize.'})
        self.assertEqual(self.state['draft'],original)
        edit(self.state,{'accent':'#343e67'})
        self.assertEqual(self.state['undo'],original)
        self.store.save(self.state)
        self.action('undo')
        self.assertEqual(self.state['draft'],original)

    def test_restore_rebinds_saved_version_to_current_profile(self):
        self.confirm()
        choice = dict(summary_fact_ids=['education', 'project:0'], skills=['Python'], project_order=[0],
                      section_order=['projects', 'education'], rationale='Saved role emphasis.')
        generate(self.state, self.service.jobs[0], SequenceModel([choice]))
        self.store.save(self.state)
        self.action('edit', patch={'accent': '#343e67'})
        saved_summary = self.state['draft']['summary']
        saved_job = self.state['draft']['job']['document_id']
        self.action('save')
        version_id = self.state['versions'][0]['id']
        self.action('edit', patch={'accent': '#935345'})

        updated_profile = deepcopy(self.state['profile'])
        updated_profile['skills'].append('Docker')
        self.action('profile', patch=updated_profile)
        self.assertEqual(self.state['confirmed_revision'], self.state['revision'])

        self.action('restore', version_id=version_id)
        self.assertEqual(self.state['draft']['revision'], self.state['revision'])
        self.assertEqual(self.state['draft']['profile'], self.state['confirmed_profile'])
        self.assertEqual(self.state['draft']['job']['document_id'], saved_job)
        self.assertEqual(self.state['draft']['summary'], saved_summary)
        self.assertEqual(self.state['draft']['accent'], '#343e67')
        self.assertIn('Docker', self.state['draft']['selection']['skills'])
        validate_draft(self.state)

    def test_different_jobs_apply_different_evidence_emphasis(self):
        profile = complete_profile()
        profile['skills'] = ['Python', 'Computer Vision', 'YOLO', 'NLP', 'scikit-learn', 'Git']
        profile['projects'] = [
            dict(title='SolarVision', description='Built an image and video computer vision pipeline. Trained a YOLO object detection model.', technologies='Python, YOLO'),
            dict(title='Fake News Detection', description='Built an NLP text classification application. Evaluated sentiment and language models.', technologies='Python, NLP'),
            dict(title='Business Website', description='Built a responsive website for a textile business.', technologies='HTML, CSS')]
        profile['achievements'] = 'High Distinction in Data Analytics.'
        profile['experience'] = ('Software Developer | Test Company | 2022 - 2024\n'
            'Built Python and SQL business software. Deployed and maintained production workflows. '
            'Worked with users to gather requirements and improve processes. Added automated tests and documentation.')
        self.action('profile', patch=profile)
        self.action('confirm', accepted=True)
        choice = dict(summary_fact_ids=['education','project:0'], skills=profile['skills'],
            project_order=[0,1,2], section_order=['projects','education','experience','achievements'],
            rationale='Model selection.')
        jobs = {job['document_id']: job for job in self.service.jobs}
        generate(self.state, jobs['computer_vision_engineer'], SequenceModel([choice]))
        vision = deepcopy(self.state['draft'])
        generate(self.state, jobs['nlp_multimodal_ml_engineer'], SequenceModel([choice]))
        nlp = deepcopy(self.state['draft'])
        generate(self.state, jobs['graduate_ai_engineer'], SequenceModel([choice]))
        graduate = deepcopy(self.state['draft'])
        self.assertEqual(vision['selection']['project_order'][0], 0)
        self.assertEqual(nlp['selection']['project_order'][0], 1)
        self.assertIn('NLP text classification', nlp['summary'])
        self.assertEqual(graduate['selection']['section_order'][0], 'education')
        self.assertEqual(graduate['design']['visible_sections'], graduate['selection']['section_order'])
        self.assertEqual(vision['selection']['project_order'], [0])
        self.assertEqual(nlp['selection']['project_order'][0], 1)
        self.assertLessEqual(len(graduate['selection']['project_order']), 2)
        self.assertNotEqual(vision['selection']['project_order'], graduate['selection']['project_order'])
        self.assertEqual(vision['suggestion_status'], 'accepted')
        self.assertNotEqual(vision['summary'], nlp['summary'])
        self.assertEqual(vision['template'], 'classic')
        self.assertTrue(vision['design']['ats'])
        self.assertEqual(vision['design']['header'], 'left')
        self.assertEqual(vision['design']['page'], 'one')
        self.assertIn('experience', vision['design']['visible_sections'])
        self.assertTrue(vision['experience_excerpt'])
        self.assertNotEqual(vision['experience_excerpt'], graduate['experience_excerpt'])
        self.assertTrue(vision['project_excerpts']['0']['text'])
        self.assertEqual(vision['profile'], nlp['profile'])

    def test_dismiss_emphasis_preserves_job_specific_evidence_subset(self):
        profile = complete_profile()
        profile['projects'] = [
            dict(title='Vision Project', description='Built an object detector.', technologies='Python, YOLO'),
            dict(title='NLP Project', description='Built a text classifier.', technologies='Python, NLP'),
            dict(title='Website', description='Built a business website.', technologies='HTML, CSS')]
        profile['skills'] = ['Python', 'YOLO', 'NLP', 'HTML']
        self.action('profile', patch=profile)
        self.action('confirm', accepted=True)
        choice = dict(summary_fact_ids=['education', 'project:2'], skills=['Python', 'HTML'],
                      project_order=[2, 0], section_order=['education', 'projects', 'experience'],
                      rationale='Lead with the selected evidence.')
        generate(self.state, self.service.jobs[0], SequenceModel([choice]))
        selected_skills = deepcopy(self.state['draft']['selection']['skills'])
        selected_projects = deepcopy(self.state['draft']['selection']['project_order'])
        selected_sections = deepcopy(self.state['draft']['selection']['section_order'])
        self.assertLess(len(selected_projects), len(profile['projects']))
        self.store.save(self.state)

        self.action('suggestion', choice='dismissed')

        self.assertEqual(self.state['draft']['selection']['project_order'], sorted(selected_projects))
        self.assertEqual(set(self.state['draft']['selection']['project_order']), set(selected_projects))
        self.assertEqual(self.state['draft']['selection']['skills'], selected_skills)
        self.assertEqual(self.state['draft']['selection']['section_order'],
                         [section for section in ['projects', 'education', 'experience', 'achievements']
                          if section in selected_sections])
        self.assertEqual(self.state['draft']['design']['visible_sections'],
                         self.state['draft']['selection']['section_order'])
        validate_draft(self.state)
    def test_invented_ai_source_rejected(self):
        self.confirm()
        choice=dict(summary_fact_ids=['fake-award'],skills=['Python'],project_order=[0],
            section_order=['projects','education','experience','achievements'],rationale='Invented')
        with self.assertRaises(ValueError): generate(self.state,self.service.jobs[0],SequenceModel([choice]))
    def test_empty_sections_can_be_omitted_but_real_experience_cannot(self):
        from .cv import validate_selection
        profile=complete_profile()
        choice=dict(summary_fact_ids=['education'],skills=['Python'],project_order=[0],
                    section_order=['projects','education'],rationale='No empty sections.')
        validate_selection(choice,profile)
        profile['experience']='Worked as a Python developer.'
        with self.assertRaises(ValueError):validate_selection(choice,profile)
    def test_multi_page_pdf_retains_text_and_job_id(self):
        from .pdf import render
        profile=complete_profile()
        profile['projects'][0]['description']='Built a Python API and documented validation checks. '*65
        self.action('profile',patch=profile);self.action('confirm',accepted=True)
        choice=dict(summary_fact_ids=['education'],skills=['Python'],project_order=[0],
            section_order=['projects','education','experience','achievements'],rationale='Pagination test.')
        generate(self.state,self.service.jobs[0],SequenceModel([choice]))
        reader=PdfReader(BytesIO(render(self.state)))
        self.assertGreaterEqual(len(reader.pages),1)
        text='\n'.join(p.extract_text() for p in reader.pages)
        self.assertIn('Test Candidate',text)
        self.assertEqual(' '.join(text.split()).count('Built a Python API'),65)
        self.assertEqual(self.state['confirmed_profile']['projects'][0]['description'].count('Built a Python API'),65)
        self.assertTrue(all('graduate_ai_engineer' in p.extract_text() for p in reader.pages))

    def test_design_controls_are_validated_and_exported(self):
        self.confirm()
        choice=dict(summary_fact_ids=['education'],skills=['Python'],project_order=[0],
            section_order=['projects','education','experience','achievements'],rationale='Design test.')
        generate(self.state,self.service.jobs[0],SequenceModel([choice]))
        edit(self.state, {'design': {'font':'serif','size':'large','spacing':'spacious','header':'left',
            'skills':'grouped','page':'two','ats':False,'visible_sections':['education','projects']}})
        validate_draft(self.state)
        from .pdf import render
        reader=PdfReader(BytesIO(render(self.state)))
        self.assertGreaterEqual(len(reader.pages), 2)
        with self.assertRaises(ValueError):
            edit(self.state, {'design': {'font':'sans','size':'standard','spacing':'comfortable','header':'center',
                'skills':'inline','page':'auto','ats':False,'visible_sections':['experience','education']}})


if __name__=='__main__': unittest.main()

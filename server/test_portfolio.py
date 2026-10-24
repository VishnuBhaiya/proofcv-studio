"""Deterministic boundary tests, NOT evidence of live Gemini generation."""
import base64
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image
from .store import Store, update_profile
from .portfolio import PortfolioService, validate_analysis, safe_link, hashed
from .portfolio_export import public_projection, package
from .portfolio_reader import Reader, install_snapshot, guide_sources
from .test_system import complete_profile, SequenceModel
from .gemini import GeminiError


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'test.sqlite3')
        self.state = self.store.create('Explicit synthetic portfolio test')
        profile = complete_profile()
        profile.update(experience='Built SQL reporting tools for a test employer.',
                       achievements='Test scholarship.',summary_facts=['Built a Python API with SQL queries.'])
        update_profile(self.state, profile)
        self.state.update(confirmed_revision=self.state['revision'], confirmed_profile=deepcopy(self.state['profile']))
        self.store.save(self.state)
        self.model = SequenceModel([])
        self.service = PortfolioService(self.store,self.model,[dict(document_id='job1',title='AI developer',description='Python SQL')])
        self.p = self.action('portfolio-init')['portfolio']

    def tearDown(self):
        self.temp.cleanup()

    def test_narration_can_be_removed_without_changing_approved_snapshot(self):
        raw=b'SYNTHETIC_WAV_FIXTURE_NOT_REAL_AUDIO'
        import hashlib
        self.p['narration']=dict(key=self.service.media.put(raw,'wav'),script='Synthetic test narration.',sha256=hashlib.sha256(raw).hexdigest(),mime='audio/wav')
        self.service._save(self.state['id'],self.p)
        self.action('portfolio-approve',accepted=True)
        sid=self.p['snapshots'][-1]['id']
        archive=self.service.archive(self.state['id'],sid)
        self.action('portfolio-remove-narration')
        self.assertIsNone(self.p['narration'])
        self.assertEqual(self.service.archive(self.state['id'],sid),archive)
        self.assertIsNotNone(self.service.snapshot(self.state['id'],sid)['narration'])

    def test_narration_removal_cannot_discard_pending_proposal(self):
        self.action('portfolio-edit-site')
        pending=deepcopy(self.p['pending'])
        with self.assertRaisesRegex(ValueError,'current proposal'):
            self.action('portfolio-remove-narration')
        self.assertEqual(self.service.get(self.state['id'])['portfolio']['pending'],pending)

    def test_new_snapshot_records_project_and_source_revision_counts(self):
        self.action('portfolio-approve',accepted=True)
        saved=self.p['snapshots'][-1]
        self.assertEqual(saved['project_count'],len(self.p['projects']))
        self.assertEqual(saved['source_revision'],self.state['revision'])
        self.assertEqual(saved['portfolio_revision'],self.p['revision'])

    def action(self, operation, **data):
        result = self.service.action(self.state['id'],operation,
            dict(revision=self.state['revision'],portfolio_revision=getattr(self,'p',{}).get('revision'),**data))
        if 'portfolio' in result: self.p=result['portfolio']
        return result

    def upload(self):
        stream=io.BytesIO();Image.new('RGB',(160,100),'green').save(stream,format='PNG')
        self.action('portfolio-upload',authorised=True,kind='image',project_id=self.p['projects'][0]['id'],
                    filename='Synthetic test.png',content=base64.b64encode(stream.getvalue()).decode())
        return self.p['assets'][-1]

    def analysis(self):
        return dict(caption='Synthetic API screen',alt='A green test image',description='A synthetic screenshot fixture.',
            hotspots=[dict(title='API area',rect=[0.1,0.1,0.5,0.5],visible='A green area.',contribution='Built a Python API with SQL queries.',outcome='',source_ids=[self.p['projects'][0]['id']])],
            chapters=[],transcript='',questions=[],warnings=['Synthetic test input; not a real product.'])

    def plan(self):
        return dict(headline='AI developer',bio='Built a Python API with SQL queries.',source_ids=['s0'],views=[
            dict(id='general',title='ignored',project_ids=[],skills=[],rationale='Complete facts.'),
            dict(id='job1',title='ignored',project_ids=[self.p['projects'][0]['id']],skills=['Python'],rationale='Python evidence first.')])

    def approve_media(self):
        asset=self.upload();self.model.actions=iter([self.analysis()])
        self.action('portfolio-analyse',asset_id=asset['id'])
        self.action('portfolio-review',proposal_id=self.p['pending']['id'],choice='accept')
        self.action('portfolio-save',published_assets=[asset['id']])
        return asset

    def test_init_requires_confirmation(self):
        state=self.store.create('Unconfirmed')
        with self.assertRaises(ValueError): self.service.action(state['id'],'portfolio-init',{'revision':0})

    def test_upload_does_not_change_confirmed_profile(self):
        original=deepcopy(self.store.get(self.state['id']))
        self.upload()
        self.assertEqual(self.store.get(self.state['id']),original)
        self.assertFalse(self.p['assets'][0]['published'])

    def test_upload_requires_rights_and_decodable_image(self):
        with self.assertRaises(ValueError):self.action('portfolio-upload',project_id=self.p['projects'][0]['id'],content='')
        with self.assertRaises(ValueError):self.action('portfolio-upload',authorised=True,project_id=self.p['projects'][0]['id'],content=base64.b64encode(b'not an image').decode())

    def test_analysis_staged_and_acceptance_round_trip(self):
        asset=self.upload();self.model.actions=iter([self.analysis()])
        self.action('portfolio-analyse',asset_id=asset['id'])
        self.assertNotIn('analysis',self.p['assets'][0])
        self.assertEqual(self.p['pending']['kind'],'analysis')
        self.action('portfolio-review',proposal_id=self.p['pending']['id'],choice='accept')
        self.assertEqual(self.p['assets'][0]['analysis']['hotspots'][0]['id'],'h0')
        self.assertFalse(self.p['assets'][0]['published'])

    def test_media_acceptance_disclosure_is_explicit_not_automatic(self):
        asset=self.upload();self.model.actions=iter([self.analysis()])
        self.action('portfolio-analyse',asset_id=asset['id'])
        proposal=self.p['pending']['id']
        with self.assertRaises(ValueError):self.action('portfolio-review',proposal_id=proposal,choice='accept',publish_media='true')
        self.action('portfolio-review',proposal_id=proposal,choice='accept',publish_media=True)
        self.assertTrue(self.p['assets'][0]['published'])
        self.assertEqual(len(public_projection(self.p)['assets']),1)

    def test_saved_design_preserves_role_selections_and_profile(self):
        self.model.actions=iter([self.plan()]);self.action('portfolio-propose',job_ids=['job1'])
        self.action('portfolio-review',proposal_id=self.p['pending']['id'],choice='accept')
        views=deepcopy(self.p['views']);profile=deepcopy(self.store.get(self.state['id']))
        self.action('portfolio-save',settings={**self.p['settings'],'theme':'technical'})
        self.assertEqual(self.p['views'],views);self.assertEqual(self.store.get(self.state['id']),profile)
        self.assertEqual(self.p['events'][-1]['kind'],'display-saved')

    def test_owner_can_edit_reviewed_media_without_provider_and_without_publishing(self):
        asset=self.approve_media();self.model.actions=iter([])
        self.action('portfolio-edit-analysis',asset_id=asset['id'])
        self.assertIn('no model call',self.p['pending']['model'])
        value=deepcopy(self.p['pending']['value']);value['caption']='Owner-corrected caption.'
        self.action('portfolio-review',choice='accept',proposal_id=self.p['pending']['id'],value=value)
        self.assertEqual(self.p['assets'][0]['analysis']['caption'],'Owner-corrected caption.')
        self.assertTrue(self.p['assets'][0]['published'])

    def test_owner_story_edit_keeps_draft_unchanged_until_review(self):
        before=self.p['headline'];self.action('portfolio-edit-site')
        value=deepcopy(self.p['pending']['value']);value['headline']='Owner-reviewed headline.'
        self.assertEqual(self.p['headline'],before)
        self.action('portfolio-review',choice='accept',proposal_id=self.p['pending']['id'],value=value)
        self.assertEqual(self.p['headline'],'Owner-reviewed headline.')

    def test_first_owner_media_explanation_is_staged_without_publishing_or_provider(self):
        asset=self.upload();self.model.actions=iter([])
        self.action('portfolio-edit-analysis',asset_id=asset['id'])
        self.assertIsNone(self.p['assets'][0].get('analysis'))
        self.assertFalse(self.p['assets'][0]['published'])
        self.assertEqual(self.p['pending']['value']['chapters'],[])
        value=deepcopy(self.p['pending']['value']);value['caption']='Owner supplied recording.'
        self.action('portfolio-review',choice='accept',proposal_id=self.p['pending']['id'],value=value)
        self.assertEqual(self.p['assets'][0]['analysis']['caption'],'Owner supplied recording.')
        self.assertFalse(self.p['assets'][0]['published'])

    def test_longer_recording_metadata_is_bounded_to_five_minutes(self):
        from types import SimpleNamespace
        raw=b'0000ftyp'+b'0'*24
        encoded=base64.b64encode(raw).decode()
        info=b'Duration: 00:03:27.83, start: 0.000000\nVideo: h264, yuv420p, 1280x720, 30 fps'
        with patch('server.portfolio_assets.subprocess.run',return_value=SimpleNamespace(returncode=0,stderr=info)):
            meta=self.service.media.video(encoded)
            self.assertAlmostEqual(meta['duration'],207.83)
        too_long=info.replace(b'00:03:27.83',b'00:05:00.01')
        with patch('server.portfolio_assets.subprocess.run',return_value=SimpleNamespace(returncode=0,stderr=too_long)):
            with self.assertRaisesRegex(ValueError,'5 minutes'):self.service.media.video(encoded)

    def test_dismissal_preserves_site(self):
        before=self.p['bio'];self.model.actions=iter([self.plan()])
        self.action('portfolio-propose',job_ids=['job1'])
        self.action('portfolio-review',proposal_id=self.p['pending']['id'],choice='dismiss')
        self.assertEqual(self.p['bio'],before)
        self.assertEqual(len(self.p['views']),1)

    def test_role_views_keep_complete_view_and_experience(self):
        self.model.actions=iter([self.plan()]);self.action('portfolio-propose',job_ids=['job1'])
        self.action('portfolio-review',proposal_id=self.p['pending']['id'],choice='accept')
        self.assertEqual(self.p['views'][0]['project_ids'],[self.p['projects'][0]['id']])
        self.assertEqual(self.p['views'][0]['skills'],['Python','SQL'])
        self.assertEqual(self.p['views'][1]['skills'],['Python'])
        self.assertIn('SQL reporting',public_projection(self.p)['person']['experience'])

    def test_model_cannot_introduce_unknown_skill(self):
        value=self.plan();value['views'][1]['skills']=['Invented expert skill']
        self.model.actions=iter([value,value])
        with self.assertRaises(ValueError):self.action('portfolio-propose',job_ids=['job1'])
        self.assertIsNone(self.service.get(self.state['id'])['portfolio']['pending'])

    def test_provider_failure_records_no_success(self):
        self.model.actions=iter([GeminiError('Synthetic provider failure')])
        with self.assertRaises(GeminiError):self.action('portfolio-propose',job_ids=[])
        p=self.service.get(self.state['id'])['portfolio']
        self.assertIsNone(p['pending']);self.assertEqual(p['events'][-1]['kind'],'generation-failed')

    def test_one_bounded_model_repair_is_recorded(self):
        invalid=self.plan();invalid['views'][1]['skills']=['Invented skill']
        self.model.actions=iter([invalid,self.plan()])
        self.action('portfolio-propose',job_ids=['job1'])
        attempts=self.p['events'][-1]['attempts']
        self.assertEqual([a['valid'] for a in attempts],[False,True])
        self.assertIsNotNone(self.p['pending'])

    def test_source_sync_invalidates_accepted_narration(self):
        self.model.settings=object()
        with patch('server.portfolio_narration.narrate',return_value=(b'fixture-audio','synthetic-tts')):
            self.action('portfolio-narrate')
        self.action('portfolio-review',choice='accept',proposal_id=self.p['pending']['id'])
        self.assertIsNotNone(self.p['narration'])
        self.action('portfolio-init');self.assertIsNone(self.p['narration'])

    def test_optional_cv_attachment_requires_valid_current_draft(self):
        with self.assertRaises((ValueError,TypeError,KeyError)):
            self.action('portfolio-approve',accepted=True,include_cv=True)

    def test_optional_cv_is_the_real_reviewed_pdf_and_separately_disclosed(self):
        from .cv import generate
        from pypdf import PdfReader
        state=self.store.get(self.state['id'])
        model=SequenceModel([dict(summary_fact_ids=['education'],skills=['Python'],project_order=[0],
            section_order=['education','projects','experience','achievements'],rationale='Explicit synthetic selection.')])
        generate(state,dict(document_id='job1',title='AI developer',description='Python SQL'),model)
        self.store.save(state)
        self.action('portfolio-approve',accepted=True,include_cv=True)
        snap=self.p['snapshots'][-1]
        with zipfile.ZipFile(io.BytesIO(self.service.archive(self.state['id'],snap['id']))) as archive:
            pdf=archive.read('resume.pdf')
            contents=' '.join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
            self.assertIn('Test Candidate',contents);self.assertIn('test@example.test',contents)
            public=self.service.snapshot(self.state['id'],snap['id'])
            self.assertNotIn('email',public['person']);self.assertEqual(public['cv_url'],'resume.pdf')

    def test_snapshot_escapes_embedded_script_text(self):
        p=deepcopy(self.p);p['headline']='</script><script>alert(1)</script>'
        public=public_projection(p);public['id']='a'*32
        with zipfile.ZipFile(io.BytesIO(package(public,self.service.media))) as archive:
            html=archive.read('index.html').decode()
            self.assertNotIn('</script><script>alert(1)',html)
            self.assertIn('\\u003c/script',html)

    def test_unknown_source_and_out_of_bounds_region_rejected(self):
        asset=self.upload();value=self.analysis();value['hotspots'][0]['source_ids']=['private-secret']
        with self.assertRaises(ValueError):validate_analysis(value,asset,self.p['sources'])
        value=self.analysis();value['hotspots'][0]['rect']=[.9,0,.4,.3]
        with self.assertRaises(ValueError):validate_analysis(value,asset,self.p['sources'])
        value=self.analysis();value['hotspots'][0]['outcome']='Improved performance by 99%.'
        with self.assertRaises(ValueError):validate_analysis(value,asset,self.p['sources'])

    def test_video_chapters_must_be_ordered_and_in_bounds(self):
        asset={'mime':'video/mp4','duration':4};value=self.analysis();value['hotspots']=[]
        value['chapters']=[dict(time=4,title='End',description='Outside')]
        with self.assertRaises(ValueError):validate_analysis(value,asset,self.p['sources'])
        value['chapters']=[dict(time=0,title='Start',description='Visible workflow')]
        self.assertEqual(validate_analysis(value,asset,self.p['sources'])['chapters'][0]['time'],0)

    def test_unreviewed_media_cannot_publish(self):
        asset=self.upload()
        with self.assertRaises(ValueError):self.action('portfolio-save',published_assets=[asset['id']])

    def test_pending_proposal_cannot_be_silently_discarded(self):
        self.model.actions=iter([self.plan()]);self.action('portfolio-propose',job_ids=['job1'])
        with self.assertRaises(ValueError):self.action('portfolio-save',settings=self.p['settings'])

    def test_stale_portfolio_and_old_revision_blocked(self):
        rev=self.p['revision'];self.upload()
        with self.assertRaises(ValueError):self.service.action(self.state['id'],'portfolio-save',dict(revision=self.state['revision'],portfolio_revision=rev))
        update_profile(self.state,{'goal':'Changed goal'});self.store.save(self.state)
        with self.assertRaises(ValueError):self.action('portfolio-save')

    def test_source_sync_drops_analysis_and_disclosure(self):
        self.approve_media()
        update_profile(self.state,{'goal':'Changed goal'});self.state.update(confirmed_revision=self.state['revision'],confirmed_profile=deepcopy(self.state['profile']));self.store.save(self.state)
        self.action('portfolio-init')
        self.assertEqual(len(self.p['assets']),1);self.assertNotIn('analysis',self.p['assets'][0]);self.assertFalse(self.p['assets'][0]['published'])

    def test_project_change_never_reassigns_media_by_position(self):
        self.upload();profile=deepcopy(self.state['profile']);profile['projects'][0]['description']='Different source project.'
        update_profile(self.state,profile);self.state.update(confirmed_revision=self.state['revision'],confirmed_profile=deepcopy(self.state['profile']));self.store.save(self.state)
        self.action('portfolio-init');self.assertEqual(self.p['assets'],[])

    def test_contact_redaction_and_approved_disclosure(self):
        public=public_projection(self.p)
        self.assertNotIn('email',public['person']);self.assertNotIn(self.p['profile']['email'],json.dumps(public))
        settings={**self.p['settings'],'show_email':True};self.action('portfolio-save',settings=settings)
        self.assertEqual(public_projection(self.p)['person']['email'],'test@example.test')

    def test_asset_ownership_and_paths(self):
        asset=self.upload();other=self.store.create('Another person')
        with self.assertRaises(ValueError):self.service.asset(other['id'],asset['id'])
        with self.assertRaises(ValueError):self.service.media.read('../test.sqlite3')

    def test_model_result_discarded_after_concurrent_change(self):
        service=self.service;workspace=self.state['id'];plan=self.plan()
        class Race:
            name='deterministic-race-test'
            def decide(_,messages,context):
                state,p=service._get(workspace);p['revision']+=1;service._save(workspace,p)
                return json.dumps(plan)
        self.service.model=Race()
        with self.assertRaisesRegex(ValueError,'changed while'):self.action('portfolio-propose',job_ids=['job1'])
        self.assertIsNone(self.service.get(workspace)['portfolio']['pending'])

    def test_narration_is_reviewed_and_cannot_be_substituted(self):
        self.model.settings=object()
        with patch('server.portfolio_narration.narrate',return_value=(b'fixture-audio','synthetic-tts')):
            self.action('portfolio-narrate')
        pending=self.p['pending'];self.assertIsNone(self.p['narration'])
        with self.assertRaises(ValueError):self.action('portfolio-review',choice='accept',proposal_id=pending['id'],value={'key':'../other'})
        self.action('portfolio-review',choice='accept',proposal_id=pending['id'])
        self.assertEqual(self.service.audio(self.state['id'],'accepted')[0],b'fixture-audio')

    def test_export_immutable_and_has_no_owner_data(self):
        self.approve_media();self.action('portfolio-approve',accepted=True)
        snap=self.p['snapshots'][-1];raw=self.service.archive(self.state['id'],snap['id'])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertIn('portfolio.js',archive.namelist());self.assertIn('manifest.json',archive.namelist())
            self.assertFalse(any('.env' in x or 'sqlite' in x or 'server/' in x for x in archive.namelist()))
            html=archive.read('index.html').decode();self.assertNotIn('test@example.test',html)
        self.action('portfolio-save',settings={**self.p['settings'],'theme':'technical'})
        self.assertEqual(self.service.archive(self.state['id'],snap['id']),raw)
        root=Path(self.temp.name)/'reader-public';install_snapshot(snap['id'],raw,root)
        reader=Reader(root,SequenceModel([dict(answer='Built a Python API.',sources=[self.p['projects'][0]['id']],project_id=self.p['projects'][0]['id'])]))
        token=reader.session(snap['id']);answer=reader.chat(snap['id'],token,'What was built?','test-client')
        self.assertTrue(answer['sources']);self.assertNotIn('email',reader.public(snap['id'])['person'])

    def test_guide_sources_include_exact_approved_tools_and_listed_skills(self):
        public=public_projection(self.p);before=deepcopy(public)
        sources=guide_sources(public);project=public['projects'][0]
        self.assertEqual(sources['project-tools:'+project['id']], 'Project: '+project['title']+'\nListed technologies: '+project['technologies'])
        self.assertEqual(sources['profile-listed-skills'],'Profile-listed skills (not independent verification): '+', '.join(public['person']['skills']))
        self.assertEqual(public,before)
        self.assertNotIn('test@example.test',json.dumps(sources))

    def test_missing_approved_tools_or_skills_cannot_be_invented(self):
        public=public_projection(self.p);public['person']['skills']=[]
        for project in public['projects']:project['technologies']=''
        sources=guide_sources(public)
        self.assertNotIn('profile-listed-skills',sources)
        self.assertFalse(any(key.startswith('project-tools:') for key in sources))

    def test_reader_cites_frozen_tool_metadata_even_after_private_draft_changes(self):
        self.action('portfolio-approve',accepted=True);sid=self.p['snapshots'][-1]['id']
        raw=self.service.archive(self.state['id'],sid)
        root=Path(self.temp.name)/'reader-public';install_snapshot(sid,raw,root)
        project=self.p['projects'][0];source_id='project-tools:'+project['id']
        reader=Reader(root,SequenceModel([dict(answer='Python and SQL are listed.',sources=[source_id],project_id=project['id'])]))
        self.p['projects'][0]['technologies']='PRIVATE_UNAPPROVED_TOOL'
        self.service._save(self.state['id'],self.p)
        answer=reader.chat(sid,reader.session(sid),'Which tools are listed?','metadata-test')
        self.assertEqual(answer['sources'][0]['id'],source_id)
        self.assertIn('Python, SQL',answer['sources'][0]['text'])
        self.assertNotIn('PRIVATE_UNAPPROVED_TOOL',json.dumps(answer))
        self.assertEqual(self.service.archive(self.state['id'],sid),raw)

    def test_world_runtime_and_licences_are_portable_and_integrity_checked(self):
        self.action('portfolio-approve',accepted=True)
        snap=self.p['snapshots'][-1]
        raw=self.service.archive(self.state['id'],snap['id'])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            notice=archive.read('THIRD_PARTY_NOTICES.txt').decode()
            self.assertIn('three.js authors',notice)
            self.assertIn('Meta Platforms',notice)
            self.assertIn('THE SOFTWARE IS PROVIDED',notice)
            self.assertIn(b'Living Exhibition',archive.read('portfolio.js'))
            self.assertIn(b'Why this project?',archive.read('portfolio.js'))
            self.assertIn('showcase-6.6',archive.read('index.html').decode())
            self.assertIn(b'Purple floating-island tour',archive.read('portfolio.js'))
            self.assertIn(b'Enter the project world',archive.read('portfolio.js'))
            self.assertIn(b'Standard view',archive.read('portfolio.js'))
            self.assertIn(b'WebGL',archive.read('README.txt'))
            manifest=json.loads(archive.read('manifest.json'))
            import hashlib
            self.assertEqual(manifest['files']['THIRD_PARTY_NOTICES.txt'],hashlib.sha256(archive.read('THIRD_PARTY_NOTICES.txt')).hexdigest())
        root=Path(self.temp.name)/'world-reader'
        install_snapshot(snap['id'],raw,root)
        self.assertEqual((root/snap['id']/'THIRD_PARTY_NOTICES.txt').read_bytes(),notice.encode())

    def test_reviewer_approval_required(self):
        with self.assertRaises(ValueError):self.action('portfolio-approve')

    def test_reader_requires_session_and_never_accepts_unknown_sources(self):
        self.action('portfolio-approve',accepted=True);snap=self.p['snapshots'][-1]
        root=Path(self.temp.name)/'public';install_snapshot(snap['id'],self.service.archive(self.state['id'],snap['id']),root)
        reader=Reader(root,SequenceModel([dict(answer='Invented.',sources=['private'],project_id='')]))
        with self.assertRaises(ValueError):reader.chat(snap['id'],'invalid','Question','client')
        token=reader.session(snap['id'])
        with self.assertRaises(ValueError):reader.chat(snap['id'],token,'Question','client')
        self.assertFalse((root/'.env').exists())

    def test_reader_abstains_without_evidence_and_enforces_budget(self):
        self.action('portfolio-approve',accepted=True);snap=self.p['snapshots'][-1]
        root=Path(self.temp.name)/'public';install_snapshot(snap['id'],self.service.archive(self.state['id'],snap['id']),root)
        reader=Reader(root,SequenceModel([dict(answer='An unsupported promise.',sources=[],project_id='')]*6))
        token=reader.session(snap['id']);answer=reader.chat(snap['id'],token,'Salary?','client')
        self.assertIn('not stated',answer['answer'])
        for _ in range(4):reader.chat(snap['id'],token,'Salary?','client')
        with self.assertRaisesRegex(ValueError,'budget'):reader.chat(snap['id'],token,'Salary?','client')

    def test_professional_link_rejects_unsafe_schemes_and_credentials(self):
        for link in ('javascript:alert(1)','https://user:password@example.com','https://bad host.com','https://example.com:bad'):
            with self.assertRaises(ValueError):safe_link(link)
        self.assertEqual(safe_link('github.com/example'),'https://github.com/example')

    def test_trashed_workspace_asset_blocked_and_restorable(self):
        asset=self.upload();self.store.move_to_trash(self.state['id'],self.state['revision'])
        with self.assertRaises(ValueError):self.service.asset(self.state['id'],asset['id'])
        self.store.restore_workspace(self.state['id']);self.assertTrue(self.service.asset(self.state['id'],asset['id'])[0])


if __name__=='__main__':unittest.main()

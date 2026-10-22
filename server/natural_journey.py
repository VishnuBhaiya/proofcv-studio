"""Additional live free-text interview with different education and a CV goal."""
import json
import time
from datetime import datetime, timezone
from copy import deepcopy
from .service import ROOT, Service
from .store import Store
from .gemini import GeminiDecisionModel, GeminiSettings, GeminiError
from .pdf import render

INTRO = ('My name is Avery Morgan. I am completing a Diploma of Information Technology '
         'at Harbour Technical College in 2026. I use Python, OpenCV and PyTorch. '
         'For my coursework object-detection project, I prepared labelled images and '
         'evaluated a small detector. It was a coursework prototype, not a production '
         'deployment. I am aiming for junior computer vision roles.')
ANSWERS = ['My email is avery.morgan@example.test and my phone is 0400 000 010. '
           'I have no employment experience.', 'I have no achievements to add.']

if __name__=='__main__':
    output=ROOT/'runtime'/'natural-evaluation'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True,exist_ok=True)
    prediction={'expected_job':'computer_vision_engineer','reason':'OpenCV, PyTorch and object-detection coursework directly overlap computer-vision work; a diploma does not establish degree or seniority eligibility.'}
    (output/'prediction.json').write_text(json.dumps(prediction,indent=2),encoding='utf-8')
    class PacedModel(GeminiDecisionModel):
        last=0.0
        def decide(self,messages,context):
            time.sleep(max(0,13-(time.monotonic()-self.last)));self.last=time.monotonic()
            return super().decide(messages,context)
    service=Service(store=Store(output/'journey.sqlite3'),model=PacedModel(GeminiSettings.load()))
    state=service.store.create('Avery Morgan - additional synthetic free-text test')
    result={'evidence_version':'final-proposal-boundary-v1','model':service.model.name,
            'prediction':prediction,'introduction':INTRO,'answers':ANSWERS,'turns':[],
            'note':'Live final-code run. Profile writes occur only after recorded proposal acceptance.'}
    def act(operation,**data):
        global state
        state=service.action(state['id'],operation,{'revision':state['revision'],**data})
        (output/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
        print(operation+' completed',flush=True)
    try:
        for turn,message in enumerate([INTRO,*ANSWERS]):
            before_revision=state['revision']
            act('chat',message=message)
            chat_response=state['messages'][-1]['content']
            proposal=deepcopy(state.get('pending_profile'))
            if not proposal:
                raise AssertionError('Expected a reviewable profile proposal from the live model.')
            chat_run=deepcopy(state.get('audit_runs', [])[-1])
            act('review-profile',proposal_id=proposal['id'],choice='accept')
            result['turns'].append({
                'turn':turn+1,'user_message':message,'revision_before':before_revision,
                'chat_response':chat_response,'model_run':chat_run,'proposal':proposal,
                'review':{'choice':'accept','revision_after':state['revision']},
                'assistant_after_acceptance':state['messages'][-1]['content'],
                'profile_after_acceptance':deepcopy(state['profile'])})
            if turn < 2:
                assert state['profile']['achievements']=='', 'Achievements must remain unknown until the user explicitly answers.'
                assert '?' in state['messages'][-1]['content'], 'An incomplete profile needs a useful follow-up question.'
        assert 'Diploma' in state['profile']['education'] and 'Bachelor' not in state['profile']['education']
        assert state['profile']['name']=='Avery Morgan'
        act('confirm',accepted=True);snapshot=deepcopy(state['confirmed_profile'])
        act('chat',message='Find the three most relevant jobs for my confirmed profile.')
        result['retrieval']=state['retrieval']
        actual=[j['document_id'] for j in state['retrieval']['results']]
        result['expected_in_top_three']=prediction['expected_job'] in actual
        act('generate',job_id=actual[0]);act('suggestion',choice='accepted');act('save')
        path=output/'avery-morgan.pdf';path.write_bytes(render(state));result['pdf']=str(path)
        assert state['confirmed_profile']==snapshot
        act('profile',patch={'phone':'0400 000 011'})
        try:render(state);raise AssertionError('Stale export incorrectly allowed')
        except ValueError:result['correction_blocks_stale_export']=True
        result['status']='passed'
    except Exception as error:
        result.update(status='failed',error=str(error))
        if isinstance(error,GeminiError):result['quota_details']=error.quota_details
    if (output/'state.json').exists():
        result['final_state_file']='state.json'
    result['complete_turn_trace_file']='turns.json'
    (output/'turns.json').write_text(json.dumps(result.get('turns',[]),ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(result['status']+': '+str(output),flush=True)

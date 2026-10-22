"""Explicit live evaluation using only supplied synthetic profiles.

Predictions below are fixed before retrieval. Outputs are development evidence,
not a report. Each provider failure is recorded and stops that profile's journey.
"""
import json
import time
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone
from .service import Service, ROOT
from .store import Store
from .gemini import GeminiError
from .gemini import GeminiFallbackModel, GeminiSettings
from .pdf import render

PREDICTIONS = {
    'Maya Chen': {'expected':['graduate_ai_engineer','agentic_ai_engineer'], 'reason':'Python APIs and a coursework tool-calling agent support graduate or agentic engineering relevance, not senior eligibility.'},
    'Liam Patel': {'expected':['nlp_multimodal_ml_engineer','graduate_ai_engineer'], 'reason':'NLP coursework and Python ML skills should match NLP or graduate AI jobs.'},
    'Sofia Williams': {'expected':['graduate_ai_engineer','healthcare_ml_engineer'], 'reason':'Data preparation and analytical work overlap graduate AI or applied data-driven ML.'},
    'Noah Ibrahim': {'expected':['trust_safety_ml_engineer','agentic_ai_engineer'], 'reason':'Cybersecurity, testing and Python overlap safety systems or Python engineering.'},
    'Ethan Nguyen': {'expected':['agentic_ai_engineer','rag_agent_engineer'], 'reason':'Backend and cloud engineering foundations overlap deployed agent and retrieval systems.'},
}


def supplied_profile(raw, index):
    def item_text(item):
        return ' · '.join(str(value) for value in item.values() if isinstance(value,str))
    return dict(name=raw['name'],email=f'candidate{index}@example.test',phone=f'0400 000 00{index}',
        education=f"{raw['degree']}, {raw['institution']}. {raw['expected_graduation']}.",
        skills=raw['technical_skills'], projects=[dict(title=p['title'],description=p['description'],
            technologies=', '.join(p.get('technologies',[]))) for p in raw['projects']],
        experience='\n'.join(item_text(e) for e in raw.get('experience',[])) or 'None',
        achievements='None',goal=', '.join(raw['target_roles']),summary_facts=[raw['summary']])


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=5)
    parser.add_argument('--start',type=int,default=1,help='First supplied profile number (1–5); use 2 to skip already-tested Maya.')
    args=parser.parse_args()
    if not 1 <= args.start <= args.limit <= 5:
        parser.error('Require 1 <= start <= limit <= 5')
    output=ROOT/'runtime'/'evaluation'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S');output.mkdir(parents=True,exist_ok=True)
    (output/'predictions.json').write_text(json.dumps(PREDICTIONS,indent=2),encoding='utf-8')
    class PacedModel(GeminiFallbackModel):
        last_call=0.0
        def decide(self,messages,context):
            # Evaluation-only pacing. Every decision still comes from one of
            # the configured live Gemini models and all attempts are observable.
            time.sleep(max(0,13-(time.monotonic()-self.last_call)))
            self.last_call=time.monotonic()
            return super().decide(messages,context)
    service=Service(store=Store(output/'journeys.sqlite3'),model=PacedModel(GeminiSettings.load()))
    raw_profiles=[json.loads(line) for line in (ROOT/'data'/'student_profiles.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    results=[]
    for index,raw in enumerate(raw_profiles[:args.limit],1):
        if index < args.start:
            continue
        state=service.store.create(raw['name']+' live evaluation')
        profile=supplied_profile(raw,index)
        record={'name':raw['name'],'expected':PREDICTIONS[raw['name']], 'mode':'live-gemini', 'started':datetime.now(timezone.utc).isoformat()}
        def act(operation,**data):
            global state
            state=service.action(state['id'],operation,{'revision':state['revision'],**data})
            (output/f'candidate-{index}-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
            print(raw['name']+': '+operation+' completed',flush=True)
            return state
        def accept_pending():
            if state.get('pending_profile'):
                proposal = state['pending_profile']
                act('review-profile', proposal_id=proposal['id'], choice='accept')
        try:
            if index==1:
                intro={k:v for k,v in profile.items() if k not in ('email','phone','experience','achievements')}
                act('chat',message='These are my actual synthetic test profile facts. Please record them: '+json.dumps(intro))
                accept_pending()
                record['first_followup']=state['messages'][-1]['content']
                act('chat',message='My email is '+profile['email']+' and my phone is '+profile['phone']+'. My experience is: '+profile['experience'])
                accept_pending()
                record['second_followup']=state['messages'][-1]['content']
                act('chat',message='I have no achievements to add. Record achievements as None.')
                accept_pending()
            else:
                act('chat',message='This is my complete synthetic test profile. Record these exact facts and tell me to review it: '+json.dumps(profile))
                accept_pending()
            record['profile_trace']=deepcopy(state['trace'])
            act('confirm',accepted=True)
            snapshot=deepcopy(state['confirmed_profile'])
            act('chat',message='Find the three most relevant jobs for my confirmed profile.')
            record['retrieval']=deepcopy(state['retrieval'])
            record['retrieval_trace']=deepcopy(state['trace'])
            if not state['retrieval']: raise ValueError('Agent did not retrieve jobs.')
            actual=[r['document_id'] for r in state['retrieval']['results']]
            record['expected_in_top_three']=bool(set(actual)&set(record['expected']['expected']))
            record['pdfs']=[]
            for job_id in actual[:2 if index==1 else 1]:
                act('generate',job_id=job_id)
                act('edit',patch={'accent':'#343e67'})
                act('undo')
                act('save')
                path=output/f'candidate-{index}-{job_id}.pdf'
                path.write_bytes(render(state))
                record['pdfs'].append(str(path))
                assert state['confirmed_profile']==snapshot
            record['confirmed_profile_unchanged']=True
            record['messages']=deepcopy(state.get('messages', []))
            record['agent_runs']=deepcopy(state.get('audit_runs', []))
            record['models_tried']=list(getattr(service.model, 'models_tried', []))
            record['active_model']=service.model.name
            record['status']='passed'
            print(raw['name']+': profile-to-PDF passed; expected top-three='+str(record['expected_in_top_three']),flush=True)
        except Exception as error:
            record['status']='failed';record['error']=str(error)
            record['messages']=deepcopy(state.get('messages', []))
            record['agent_runs']=deepcopy(state.get('audit_runs', []))
            record['models_tried']=list(getattr(service.model, 'models_tried', []))
            record['active_model']=service.model.name
            if isinstance(error, GeminiError) and error.quota_details:
                record['quota_details']=error.quota_details
                print('Structured quota details: '+json.dumps(error.quota_details),flush=True)
            print(raw['name']+': FAILED: '+str(error),flush=True)
        results.append(record)
        (output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        if record['status']=='failed' and 'HTTP 429' in record.get('error',''):
            print('Quota stop: remaining profiles were not attempted. Resume after quota becomes available.',flush=True)
            break
    print('Results: '+str(output/'results.json'),flush=True)

"""Five offline application journeys with REAL MiniLM and SCRIPTED model selections.

These test local plumbing and PDF invariants; they are NOT live Gemini evidence.
"""
import json
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from pypdf import PdfReader
from .service import Service, ROOT
from .store import Store
from .live_journeys import PREDICTIONS, supplied_profile
from .test_system import SequenceModel
from .cv import facts
from .pdf import render

if __name__=='__main__':
    output=ROOT/'runtime'/'local-evaluation'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True,exist_ok=True)
    (output/'predictions.json').write_text(json.dumps(PREDICTIONS,indent=2),encoding='utf-8')
    service=Service(store=Store(output/'journeys.sqlite3'),model=SequenceModel([]))
    profiles=[json.loads(s) for s in (ROOT/'data'/'student_profiles.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    results=[]
    for index,raw in enumerate(profiles,1):
        state=service.store.create(raw['name']+' local fixture test')
        def act(operation,**data):
            global state
            state=service.action(state['id'],operation,{'revision':state['revision'],**data})
        profile=supplied_profile(raw,index)
        record={'name':raw['name'],'model_mode':'SCRIPTED_FIXTURE_NOT_LIVE','prediction':PREDICTIONS[raw['name']]}
        try:
            act('profile',patch=profile);act('confirm',accepted=True);act('retrieve')
            before=deepcopy(state['confirmed_profile'])
            actual=[j['document_id'] for j in state['retrieval']['results']]
            record['retrieval']=state['retrieval'];record['expected_in_top_three']=bool(set(actual)&set(PREDICTIONS[raw['name']]['expected']))
            record['pdfs']=[]
            for job_id in actual[:2 if index==1 else 1]:
                choice=dict(summary_fact_ids=['summary:0','project:0'],skills=profile['skills'],
                    project_order=list(reversed(range(len(profile['projects'])))),
                    section_order=['education','projects','experience','achievements'],rationale='Scripted fixture: exercise reorder acceptance.')
                service.model=SequenceModel([choice])
                act('generate',job_id=job_id)
                source_order=deepcopy(state['draft']['selection'])
                act('suggestion',choice='accepted')
                assert state['draft']['selection']['project_order']==choice['project_order']
                act('undo');assert state['draft']['selection']==source_order
                act('suggestion',choice='dismissed');act('undo')
                act('edit',patch={'template':'classic' if index%2==0 else 'editorial','accent':'#2c6554'})
                act('save');act('restore',version_id=state['versions'][0]['id'])
                pdf=render(state);reader=PdfReader(BytesIO(pdf));text='\n'.join(p.extract_text() for p in reader.pages)
                assert profile['name'] in text and job_id in text
                assert state['confirmed_profile']==before
                path=output/f'candidate-{index}-{job_id}.pdf';path.write_bytes(pdf)
                record['pdfs'].append({'path':str(path),'pages':len(reader.pages)})
            act('profile',patch={'name':profile['name']+' Corrected'})
            try: render(state);raise AssertionError('Stale export incorrectly allowed')
            except ValueError: pass
            record['stale_export_blocked']=True;record['status']='passed'
        except Exception as error:
            record['status']='failed';record['error']=str(error)
        results.append(record)
        print(raw['name']+': '+record['status']+'; expected top-three='+str(record.get('expected_in_top_three')),flush=True)
        (output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(str(output),flush=True)

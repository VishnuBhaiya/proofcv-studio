"""Resume generation from saved live confirmed profiles; preserve failed evidence."""
import argparse
import json
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from io import BytesIO
from pypdf import PdfReader
from .service import Service, ROOT
from .store import Store
from .gemini import GeminiDecisionModel, GeminiSettings, GeminiError
from .pdf import render

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source_run');args=parser.parse_args()
    source=Path(args.source_run).resolve()
    if not source.is_relative_to((ROOT/'runtime'/'evaluation').resolve()):
        parser.error('Source must be a saved synthetic evaluation run.')
    output=ROOT/'runtime'/'evaluation'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True,exist_ok=True)
    class PacedModel(GeminiDecisionModel):
        last=0.0
        def decide(self,messages,context):
            time.sleep(max(0,13-(time.monotonic()-self.last)));self.last=time.monotonic()
            return super().decide(messages,context)
    service=Service(store=Store(output/'journeys.sqlite3'),model=PacedModel(GeminiSettings.load()))
    predictions=json.loads((source/'predictions.json').read_text(encoding='utf-8'))
    (output/'predictions.json').write_text(json.dumps(predictions,indent=2),encoding='utf-8')
    results=[]
    for index in range(2,6):
        state=json.loads((source/f'candidate-{index}-state.json').read_text(encoding='utf-8'))
        service.store.save(state)
        name=state['profile']['name'];snapshot=deepcopy(state['confirmed_profile'])
        result=dict(name=name,model=service.model.name,source_live_run=str(source),
                    source_profile_revision=state['revision'],prediction=predictions[name],
                    retrieval=state['retrieval'])
        def act(operation,**data):
            global state
            state=service.action(state['id'],operation,{'revision':state['revision'],**data})
        try:
            job_id=state['retrieval']['results'][0]['document_id']
            act('generate',job_id=job_id)
            act('suggestion',choice='accepted')
            accepted=deepcopy(state['draft'])
            act('suggestion',choice='dismissed');act('undo')
            assert state['draft']==accepted
            act('edit',patch={'accent':'#343e67'});act('undo');act('save')
            pdf=render(state);path=output/f'candidate-{index}-{job_id}.pdf';path.write_bytes(pdf)
            reader=PdfReader(BytesIO(pdf));text='\n'.join(p.extract_text() for p in reader.pages)
            assert name in text and job_id in text
            assert state['confirmed_profile']==snapshot
            other_names=set(predictions)-{name}
            assert not any(other in text for other in other_names)
            actual={j['document_id'] for j in state['retrieval']['results']}
            result.update(status='passed',pdf=str(path),pages=len(reader.pages),
                expected_in_top_three=bool(actual&set(predictions[name]['expected'])),
                confirmed_profile_unchanged=True,other_user_names_absent=True)
            (output/f'candidate-{index}-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception as error:
            result.update(status='failed',error=str(error))
            if isinstance(error,GeminiError):result['quota_details']=error.quota_details
        results.append(result)
        (output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name+': '+result['status']+(' - '+result.get('error','') if result['status']=='failed' else ''),flush=True)
        if 'HTTP 429' in result.get('error',''):break
    print(str(output),flush=True)

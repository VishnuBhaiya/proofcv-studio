"""Explicit live retry for an existing SYNTHETIC evaluation workspace only."""
import json
from pathlib import Path
from datetime import datetime, timezone
from .gemini import GeminiSettings, GeminiFallbackModel, GeminiError
from .portfolio import PortfolioService
from .service import ROOT
from .store import Store


def main():
    result=sorted((ROOT/'runtime'/'evaluation').glob('showcase-live-*/result.json'))[-1]
    evidence=json.loads(result.read_text(encoding='utf-8'))
    if evidence.get('kind')!='LIVE_PROVIDER_SYNTHETIC_INPUTS':raise ValueError('Synthetic evaluation only.')
    store=Store(ROOT/'runtime'/'proofcv.sqlite3');state=store.get(evidence['workspace'])
    if not state['label'].startswith('Showcase — synthetic live verification '):raise ValueError('Synthetic workspace required.')
    model=GeminiFallbackModel(GeminiSettings.load())
    jobs=[json.loads(line) for line in (ROOT/'data'/'jobs.jsonl').read_text(encoding='utf-8').splitlines()]
    service=PortfolioService(store,model,jobs)
    def action(op,**data):
        p=service.get(state['id'])['portfolio']
        return service.action(state['id'],op,dict(revision=state['revision'],portfolio_revision=p['revision'],**data))
    step=dict(name='live_site_plan_retry',at=datetime.now(timezone.utc).isoformat())
    try:
        p=action('portfolio-propose',job_ids=['computer_vision_engineer','graduate_ai_engineer'])['portfolio']
        step['proposal']=p['pending']
        action('portfolio-review',choice='accept',proposal_id=p['pending']['id'])
        p=action('portfolio-approve',accepted=True)['portfolio'];snap=p['snapshots'][-1]
        action('portfolio-reader',snapshot_id=snap['id'])
        step.update(status='PASS',model=model.name,snapshot=snap['id'],public_url='http://127.0.0.1:8001/site/'+snap['id']+'/')
        (result.parent/'approved-synthetic-portfolio-final.zip').write_bytes(service.archive(state['id'],snap['id']))
    except Exception as error:
        step.update(status='FAIL',error=str(error),error_type=type(error).__name__)
        if isinstance(error,GeminiError):step['quota_details']=error.quota_details
    evidence['steps'].append(step);evidence['portfolio']=service.get(state['id'])['portfolio']
    result.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in step.items() if k!='proposal'},indent=2))


if __name__=='__main__':main()

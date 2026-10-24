"""One opt-in live input-sensitivity check using a different synthetic image."""
import base64
from datetime import datetime, timezone
import io
import json
from PIL import Image,ImageDraw,ImageFont
from .service import ROOT
from .store import Store
from .portfolio import PortfolioService
from .gemini import GeminiSettings,GeminiFallbackModel


def main():
    original=sorted((ROOT/'runtime/evaluation').glob('showcase-live-*/result.json'))[-1]
    run=json.loads(original.read_text(encoding='utf-8'))
    store=Store(ROOT/'runtime/proofcv.sqlite3');state=store.get(run['workspace'])
    if not state['label'].startswith('Showcase — synthetic live verification '):raise ValueError('Synthetic evaluation only.')
    model=GeminiFallbackModel(GeminiSettings.load())
    jobs=[json.loads(line) for line in (ROOT/'data/jobs.jsonl').read_text().splitlines()]
    service=PortfolioService(store,model,jobs)
    def action(op,**data):
        p=service.get(state['id'])['portfolio']
        return service.action(state['id'],op,dict(revision=state['revision'],portfolio_revision=p['revision'],**data))
    image=Image.new('RGB',(1000,600),'#172c2a');draw=ImageDraw.Draw(image)
    from pathlib import Path
    font_path=Path('C:/Windows/Fonts/segoeui.ttf')
    font=ImageFont.truetype(str(font_path),28) if font_path.is_file() else ImageFont.load_default()
    draw.text((35,30),'SYNTHETIC REVIEW HISTORY — NOT A REAL APPLICATION',fill='#e6e9d5',font=font)
    for index,(label,value) in enumerate([('Run ID','TEST-012'),('Duplicate filenames','7 flagged'),('Missing annotations','3 flagged'),('Action','Review before training')]):
        y=130+index*95;draw.rectangle((40,y,960,y+70),fill='#274440')
        draw.text((65,y+15),label,fill='#b5d2ba',font=font);draw.text((570,y+15),value,fill='#f2d3a1',font=font)
    output=io.BytesIO();image.save(output,format='PNG')
    p=service.get(state['id'])['portfolio'];project=p['projects'][2]['id']
    p=action('portfolio-upload',authorised=True,project_id=project,kind='image',filename='Synthetic review history.png',content=base64.b64encode(output.getvalue()).decode())['portfolio']
    asset=p['assets'][-1]
    evidence=dict(kind='LIVE_PROVIDER_SYNTHETIC_MEDIA_CONTRAST',at=datetime.now(timezone.utc).isoformat(),
        note='Synthetic visible counts are NOT candidate outcomes. Second image stays private and is dismissed after inspection.')
    try:
        p=action('portfolio-analyse',asset_id=asset['id'])['portfolio']
        proposal=p['pending'];first=next(s['result'] for s in run['steps'] if s['name']=='live_image_analysis')['value']
        second=proposal['value']
        evidence.update(status='PASS',model=model.name,first=first,second=second,descriptions_differ=first['description']!=second['description'],
                        visible_counts_not_candidate_outcomes=all(not h['outcome'] or ('7' not in h['outcome'] and '3' not in h['outcome']) for h in second['hotspots']))
        action('portfolio-review',choice='dismiss',proposal_id=proposal['id'])
    except Exception as error:evidence.update(status='FAIL',error=str(error))
    path=ROOT/'runtime/evaluation/portfolio-media-contrast.json';path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ('first','second')},indent=2))


if __name__=='__main__':main()

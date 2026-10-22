"""Explicit live diagnostic using a previously confirmed synthetic test profile."""
import argparse
import json
from pathlib import Path
from .service import ROOT
from .gemini import GeminiDecisionModel, GeminiSettings
from .cv import facts, validate_selection
from .prompts import CV_SYSTEM

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('state_file');args=parser.parse_args()
    path=Path(args.state_file).resolve()
    if not path.is_relative_to((ROOT/'runtime'/'evaluation').resolve()):
        parser.error('Use a synthetic evaluation state file under runtime/evaluation.')
    state=json.loads(path.read_text(encoding='utf-8'))
    profile=state['confirmed_profile'];job=state['retrieval']['results'][0]['job']
    model=GeminiDecisionModel(GeminiSettings.load())
    raw=model.decide([{'role':'system','content':CV_SYSTEM},{'role':'user','content':json.dumps({'facts':facts(profile),'profile':profile,'job':job})}],{})
    output={'model':model.name,'selection':json.loads(raw)}
    try: validate_selection(output['selection'],profile);output['validation']='passed'
    except ValueError as error: output['validation']=str(error)
    path.with_name(path.stem+'-generation-diagnostic.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output,indent=2))

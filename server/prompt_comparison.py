"""Same-input live comparison of baseline vs improved prompt/output contract."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from .service import ROOT
from .gemini import GeminiDecisionModel, GeminiSettings, GeminiError
from .prompts import CV_BASELINE_SYSTEM, CV_BASELINE_VERSION, CV_SYSTEM, CV_VERSION
from .cv import facts, selection_schema, validate_selection, SECTIONS

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('state_file');args=parser.parse_args()
    path=Path(args.state_file).resolve()
    if not path.is_relative_to((ROOT/'runtime'/'evaluation').resolve()):
        parser.error('Use a synthetic evaluation state file.')
    state=json.loads(path.read_text(encoding='utf-8'))
    profile=state['confirmed_profile'];job=state['retrieval']['results'][0]['job']
    user_input=json.dumps({'facts':facts(profile),'profile':profile,'job':job})
    model=GeminiDecisionModel(GeminiSettings.load())
    output=ROOT/'runtime'/'prompt-comparison'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True,exist_ok=True)
    record={'model':model.name,'source_state':str(path),'user_input':json.loads(user_input),
            'input_sha256':hashlib.sha256(user_input.encode()).hexdigest(),
            'controlled':{'temperature':0,'same_model':True,'same_user_input':True},
            'changed':'Prompt instructions AND response schema. This is not an isolated prompt-only causal experiment.',
            'runs':[]}
    for index,(version,prompt,context) in enumerate([
        (CV_BASELINE_VERSION,CV_BASELINE_SYSTEM,{}),
        (CV_VERSION,CV_SYSTEM,{'_output_schema':selection_schema(profile)})]):
        if index:time.sleep(13)
        run={'prompt_version':version,'system_prompt':prompt,'output_schema':context.get('_output_schema')}
        try:
            value=json.loads(model.decide([{'role':'system','content':prompt},{'role':'user','content':user_input}],context))
            run['output']=value
            try:validate_selection(value,profile);run['current_validator']='passed'
            except ValueError as error:run['current_validator']=str(error)
            run['legacy_all_sections_contract']=sorted(value.get('section_order',[]))==sorted(SECTIONS)
            run['summary_fact_count']=len(value.get('summary_fact_ids',[]))
            run['status']='completed'
        except GeminiError as error:
            run.update(status='failed',error=str(error),quota_details=error.quota_details)
        record['runs'].append(run)
        (output/'comparison.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(version+': '+run['status']+'; source facts='+str(run.get('summary_fact_count')),flush=True)
        if run['status']=='failed':break
    print(str(output/'comparison.json'),flush=True)

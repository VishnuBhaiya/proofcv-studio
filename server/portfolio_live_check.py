"""Opt-in provider evaluation with FICTIONAL profile and SYNTHETIC media.

This makes billable/quotad provider calls. No real candidate data is loaded.
Acceptances in this evaluation are automated test actions, not human verification.
Failures are retained and never replaced with a fake successful AI result.
"""
import argparse
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont
from .gemini import GeminiSettings, GeminiFallbackModel
from .portfolio import PortfolioService
from .portfolio_reader import Reader
from .seed_labelled_sample import _profile
from .service import ROOT
from .store import Store


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path,default=ROOT/'.env')
    parser.add_argument('--skip-audio',action='store_true')
    args=parser.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output=ROOT/'runtime'/'evaluation'/('showcase-live-'+stamp);output.mkdir(parents=True)
    settings=GeminiSettings.load(args.env_file)
    model=GeminiFallbackModel(settings)
    store=Store(ROOT/'runtime'/'proofcv.sqlite3')
    state=store.create('Showcase — synthetic live verification '+stamp)
    profile=_profile()
    state.update(profile=profile,revision=1,confirmed_revision=1,confirmed_profile=deepcopy(profile))
    store.save(state)
    jobs=[json.loads(line) for line in (ROOT/'data'/'jobs.jsonl').read_text(encoding='utf-8').splitlines()]
    service=PortfolioService(store,model,jobs)
    portfolio=None
    evidence=dict(kind='LIVE_PROVIDER_SYNTHETIC_INPUTS',automated_test_acceptance=True,created_at=stamp,
                  workspace=state['id'],profile_label='Fictional Avery Morgan',steps=[],output_directory=str(output))
    def save():
        evidence['portfolio']=service.get(state['id'])['portfolio']
        (output/'result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    def action(op,**data):
        nonlocal portfolio
        result=service.action(state['id'],op,dict(revision=state['revision'],portfolio_revision=portfolio['revision'] if portfolio else None,**data))
        if 'portfolio' in result:portfolio=result['portfolio']
        return result
    def attempt(name,fn):
        print('Running '+name+'…',flush=True)
        try:
            result=fn();step=dict(name=name,status='PASS',model=getattr(model,'name','unknown'))
            if isinstance(result,dict):
                step['result']=result
                if '_checks' in result and not all(result['_checks'].values()):
                    step.update(status='FAIL',error='One or more expected live-output checks failed; raw result retained.')
        except Exception as error:
            step=dict(name=name,status='FAIL',error=str(error)[:600],type=type(error).__name__)
        evidence['steps'].append(step);save();print(name+': '+step['status']+((' — '+step['error']) if step['status']=='FAIL' else ''),flush=True)
        return step['status']=='PASS'
    action('portfolio-init')
    # A labelled synthetic diagram is a controlled visual test input, not a
    # screenshot of an application the candidate claims to have built.
    image=Image.new('RGB',(1000,600),'#f1f4e9');draw=ImageDraw.Draw(image)
    font_path=Path('C:/Windows/Fonts/segoeui.ttf')
    font=ImageFont.truetype(str(font_path),26) if font_path.is_file() else ImageFont.load_default()
    title=ImageFont.truetype(str(font_path),34) if font_path.is_file() else font
    draw.text((38,32),'Dataset Quality Review Toolkit',fill='#1e4734',font=title)
    draw.text((38,88),'SYNTHETIC EVALUATION DIAGRAM — NOT A PRODUCT SCREENSHOT',fill='#7a4826',font=font)
    for x,label,detail in [(40,'01 / INPUT','Images and labels'),(360,'02 / VALIDATE','Dimensions + duplicates'),(680,'03 / REVIEW','Missing labels + CSV')]:
        draw.rounded_rectangle((x,190,x+280,410),radius=16,fill='#ffffff',outline='#456b50',width=3)
        draw.text((x+18,220),label,fill='#244d38',font=font)
        words=detail.split(' + ')
        for index,word in enumerate(words):draw.text((x+18,280+index*40),word,fill='#45584a',font=font)
    draw.text((45,495),'Coursework prototype · candidate contribution comes from confirmed text',fill='#45584a',font=font)
    image_path=output/'synthetic-diagram.png';image.save(image_path)
    project=portfolio['projects'][2]['id']
    action('portfolio-upload',authorised=True,project_id=project,kind='image',filename=image_path.name,content=base64.b64encode(image_path.read_bytes()).decode())
    asset=portfolio['assets'][-1]
    def analyse():
        action('portfolio-analyse',asset_id=asset['id'])
        proposal=deepcopy(portfolio['pending'])
        action('portfolio-review',choice='accept',proposal_id=proposal['id'])
        proposal['_checks']=dict(nonempty_regions=bool(proposal['value']['hotspots']),no_video_chapters=not proposal['value']['chapters'])
        return proposal
    attempt('live_image_analysis',analyse)
    def video():
        import imageio_ffmpeg
        path=output/'synthetic-silent-tour.mp4'
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-loop','1','-i',str(image_path),'-t','6','-vf','scale=800:480','-c:v','libx264','-pix_fmt','yuv420p','-an','-movflags','+faststart',str(path)],check=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        action('portfolio-upload',authorised=True,project_id=project,kind='video',filename=path.name,content=base64.b64encode(path.read_bytes()).decode())
        asset_id=portfolio['assets'][-1]['id']
        action('portfolio-analyse',asset_id=asset_id)
        proposal=deepcopy(portfolio['pending']);action('portfolio-review',choice='accept',proposal_id=proposal['id'])
        proposal['_checks']=dict(nonempty_chapters=bool(proposal['value']['chapters']),no_image_regions=not proposal['value']['hotspots'],silent_video_no_invented_speech=not proposal['value']['transcript'])
        return proposal
    attempt('live_video_analysis',video)
    def plan():
        action('portfolio-propose',job_ids=['computer_vision_engineer','graduate_ai_engineer'])
        proposal=deepcopy(portfolio['pending']);action('portfolio-review',choice='accept',proposal_id=proposal['id'])
        views=portfolio['views'];selected={v['id']:v['project_ids'] for v in views}
        proposal['_checks']=dict(three_views=len(views)==3,different_evidence=selected.get('computer_vision_engineer')!=selected.get('graduate_ai_engineer'))
        return proposal
    attempt('live_site_plan',plan)
    if not args.skip_audio:
        def audio():
            action('portfolio-narrate');proposal=deepcopy(portfolio['pending']);action('portfolio-review',choice='accept',proposal_id=proposal['id']);return proposal
        attempt('live_stock_voice_narration',audio)
    action('portfolio-save',published_assets=[a['id'] for a in portfolio['assets'] if a.get('analysis')])
    action('portfolio-approve',accepted=True)
    snap=portfolio['snapshots'][-1]
    archive=service.archive(state['id'],snap['id'])
    (output/'approved-synthetic-portfolio.zip').write_bytes(archive)
    action('portfolio-reader',snapshot_id=snap['id'])
    evidence.update(snapshot=snap['id'],archive_sha256=hashlib.sha256(archive).hexdigest(),public_url='http://127.0.0.1:8001/site/'+snap['id']+'/')
    reader=Reader(ROOT/'runtime'/'reader-public',model)
    token=reader.session(snap['id'])
    def read_supported():
        value=reader.chat(snap['id'],token,'Which project demonstrates data quality checks and how?','live-check')
        value['_checks']=dict(cites_public_sources=bool(value['sources']),navigates_to_approved_project=value['project_id']==project)
        return value
    def read_unsupported():
        value=reader.chat(snap['id'],token,'What salary has Avery accepted and can you promise an interview tomorrow?','live-check')
        value['_checks']=dict(no_invented_sources=not value['sources'],no_navigation=not value['project_id'],clear_abstention='not stated' in value['answer'])
        return value
    attempt('live_source_backed_reader',read_supported)
    attempt('live_reader_abstention',read_unsupported)
    save();print('Evidence: '+str(output/'result.json'),flush=True)


if __name__=='__main__':main()

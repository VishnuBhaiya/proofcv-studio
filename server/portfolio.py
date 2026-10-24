"""Local Portfolio Studio: isolated model proposals, explicit review, immutable exports."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import uuid

from .store import require_confirmed
from .gemini import GeminiError
from .portfolio_assets import MediaStore
from . import portfolio_prompts as prompts


def hashed(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def text(value, maximum=2500):
    if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise ValueError('Invalid or oversized portfolio text.')
    return value.strip()


def strings(value, maximum=20):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError('Invalid portfolio list.')
    return [text(item) for item in value]


def refs(value, sources):
    result = strings(value, 12)
    if any(item not in sources for item in result):
        raise ValueError('A proposal referenced facts outside its source snapshot.')
    return list(dict.fromkeys(result))


def safe_link(value):
    value = text(value, 500)
    if not value:
        return ''
    if not re.match(r'^https?://', value, re.I):
        value = 'https://' + value
    from urllib.parse import urlsplit
    parts = urlsplit(value)
    try:
        parts.port
    except ValueError:
        raise ValueError('Use a valid http/https professional link.') from None
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or any(c.isspace() or c in '<>"' for c in value):
        raise ValueError('Use a valid http/https professional link.')
    return value


def source_profile(state):
    profile = deepcopy(state['confirmed_profile'])
    projects = []
    sources = {}
    for key in ('name', 'education', 'experience', 'achievements', 'goal'):
        if profile.get(key) and profile[key].strip().lower() not in ('none', 'no', 'n/a'):
            sources[key] = profile[key]
    for index, project in enumerate(profile['projects']):
        key = f'p{index}-' + hashed(project)[:12]
        projects.append(dict(id=key, **project))
        sources[key] = project['description']
    for index, value in enumerate(profile.get('summary_facts', [])):
        sources[f's{index}'] = value
    return profile, projects, sources


def blank(state):
    profile, projects, sources = source_profile(state)
    return dict(revision=0, source_revision=state['revision'], source_hash=hashed(profile),
                profile=profile, projects=projects, sources=sources, assets=[], pending=None,
                headline=profile['goal'], bio='\n\n'.join(profile.get('summary_facts', [])[:2]),
                bio_sources=[f's{i}' for i in range(min(2, len(profile.get('summary_facts', []))))],
                views=[dict(id='general', title='Complete profile', project_ids=[p['id'] for p in projects],
                            skills=profile['skills'][:], rationale='Complete confirmed profile. No role-specific selection.')],
                settings=dict(theme='editorial', avatar='orbit', show_email=False, show_phone=False,
                              show_location=False, show_links=False), narration=None, snapshots=[], events=[])


def validate_analysis(value, asset, sources):
    if not isinstance(value, dict) or set(value) - {'caption','alt','description','hotspots','chapters','transcript','questions','warnings'}:
        raise ValueError('Unexpected visual-analysis fields.')
    result = {key: text(value.get(key, ''), 5000 if key == 'transcript' else 2500)
              for key in ('caption','alt','description','transcript')}
    result.update(questions=strings(value.get('questions', []), 3), warnings=strings(value.get('warnings', []), 8), hotspots=[], chapters=[])
    regions = value.get('hotspots', [])
    chapters = value.get('chapters', [])
    if not isinstance(regions, list) or len(regions) > 4 or not isinstance(chapters, list) or len(chapters) > 6:
        raise ValueError('Too many media annotations.')
    if asset['mime'].startswith('video/') and regions or asset['mime'].startswith('image/') and chapters:
        raise ValueError('Use regions for images and timestamp chapters for videos.')
    for index, region in enumerate(regions):
        if not isinstance(region, dict) or set(region) - {'id','title','rect','visible','contribution','outcome','source_ids'}:
            raise ValueError('Invalid hotspot fields.')
        rect = region.get('rect')
        if not isinstance(rect, list) or len(rect) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in rect):
            raise ValueError('Hotspots need four finite normalized coordinates.')
        x, y, width, height = rect
        if min(x,y) < 0 or min(width,height) <= 0 or x + width > 1.00001 or y + height > 1.00001:
            raise ValueError('A hotspot falls outside the image.')
        item = {key: text(region.get(key, '')) for key in ('title','visible','contribution','outcome')}
        item.update(id=f'h{index}', rect=rect, source_ids=refs(region.get('source_ids', []), sources))
        if (item['contribution'] or item['outcome']) and not item['source_ids']:
            raise ValueError('Personal contributions and outcomes need confirmed source references.')
        # Numerical outcomes may not introduce new measurements.
        source_text = ' '.join(sources[key] for key in item['source_ids'])
        if any(number not in source_text for number in re.findall(r'\d+(?:\.\d+)?', item['outcome'])):
            raise ValueError('An outcome contains an unsupported measurement.')
        result['hotspots'].append(item)
    last = -1
    for chapter in chapters:
        if not isinstance(chapter, dict) or set(chapter) - {'time','title','description'}:
            raise ValueError('Invalid video chapter.')
        at = chapter.get('time')
        if type(at) not in (int, float) or not math.isfinite(at) or at < 0 or at >= asset['duration'] or at <= last:
            raise ValueError('Video chapter times must be ordered and within the video.')
        last = at
        result['chapters'].append(dict(time=at, title=text(chapter.get('title','')), description=text(chapter.get('description',''))))
    return result


def validate_site(value, portfolio, jobs):
    if not isinstance(value, dict) or set(value) - {'headline','bio','source_ids','views'}:
        raise ValueError('Unexpected website-plan fields.')
    result = dict(headline=text(value.get('headline',''), 250), bio=text(value.get('bio','')),
                  source_ids=refs(value.get('source_ids', []), portfolio['sources']), views=[])
    if result['bio'] and not result['source_ids']:
        raise ValueError('The proposed introduction needs source references.')
    views = value.get('views')
    if not isinstance(views, list) or not 1 <= len(views) <= 3:
        raise ValueError('Choose a general view and up to two job views.')
    valid_jobs = {'general': 'Complete profile', **{job['document_id']: job['title'] for job in jobs}}
    project_ids = {p['id'] for p in portfolio['projects']}
    seen = set()
    for view in views:
        if not isinstance(view, dict) or set(view) - {'id','title','project_ids','skills','rationale'}:
            raise ValueError('Invalid role-view fields.')
        key = view.get('id')
        selected = strings(view.get('project_ids', []))
        skills = strings(view.get('skills', []), 80)
        if key not in valid_jobs or key in seen or any(p not in project_ids for p in selected) or any(s not in portfolio['profile']['skills'] for s in skills):
            raise ValueError('A role view contains an unknown job, project or skill.')
        seen.add(key)
        result['views'].append(dict(id=key, title=valid_jobs[key], project_ids=list(dict.fromkeys(selected)),
                                    skills=list(dict.fromkeys(skills)), rationale=text(view.get('rationale',''))))
    if 'general' not in seen:
        raise ValueError('A complete-profile view is required.')
    general = next(v for v in result['views'] if v['id'] == 'general')
    general.update(project_ids=[p['id'] for p in portfolio['projects']], skills=portfolio['profile']['skills'][:])
    return result


def proposal_schema(portfolio, asset=None, jobs=()):
    """Provider schema narrows shape/IDs; Python validation remains authoritative."""
    def obj(properties):
        return dict(type='object',additionalProperties=False,properties=properties,required=list(properties))
    string=dict(type='string')
    def array(items,minimum=0,maximum=20):
        return dict(type='array',items=items,minItems=minimum,maxItems=maximum)
    source_ids=array(dict(type='string',enum=list(portfolio['sources'])),maximum=12)
    if asset:
        video=asset['mime'].startswith('video/')
        region=obj(dict(title=string,rect=array(dict(type='number',minimum=0,maximum=1),4,4),
                        visible=string,contribution=string,outcome=string,source_ids=source_ids))
        chapter=obj(dict(time=dict(type='number',minimum=0,maximum=asset['duration']),title=string,description=string))
        return obj(dict(caption=string,alt=string,description=string,hotspots=array(region,0,0 if video else 4),
                        chapters=array(chapter,1 if video else 0,6 if video else 0),transcript=string,
                        questions=array(string,maximum=3),warnings=array(string,maximum=8)))
    view=obj(dict(id=dict(type='string',enum=['general']+[job['document_id'] for job in jobs]),title=string,
                  project_ids=array(dict(type='string',enum=[p['id'] for p in portfolio['projects']])),
                  skills=array(dict(type='string',enum=portfolio['profile']['skills']),maximum=80),rationale=string))
    schema = obj(dict(headline=string,bio=string,source_ids=source_ids,views=array(view,len(jobs)+1,len(jobs)+1)))
    # Nested list upper bounds (especially 80 skills × 3 views) can exceed the
    # provider's constrained-decoding state budget. Enforce counts in Python;
    # retain provider enums for exact IDs and skill names.
    def simplify(value):
        if isinstance(value,dict):
            value.pop('minItems',None);value.pop('maxItems',None)
            for child in value.values():simplify(child)
        elif isinstance(value,list):
            for child in value:simplify(child)
    simplify(schema)
    return schema


class PortfolioService:
    def __init__(self, store, model, jobs):
        self.store, self.model, self.jobs = store, model, jobs
        self.media = MediaStore(store.path.parent / 'portfolio-media')
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS portfolios (workspace TEXT PRIMARY KEY, state TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS portfolio_snapshots (id TEXT PRIMARY KEY, workspace TEXT NOT NULL, state TEXT NOT NULL, archive BLOB NOT NULL)')

    def _get(self, workspace):
        state = self.store.get(workspace)
        with self.store.connect() as db:
            row = db.execute('SELECT state FROM portfolios WHERE workspace=?', (workspace,)).fetchone()
        return state, json.loads(row[0]) if row else None

    def _save(self, workspace, portfolio):
        with self.store.connect() as db:
            db.execute('INSERT INTO portfolios VALUES (?,?) ON CONFLICT(workspace) DO UPDATE SET state=excluded.state',
                       (workspace, json.dumps(portfolio)))

    def get(self, workspace):
        with self.store.lock:
            state, portfolio = self._get(workspace)
            return self.response(state, portfolio)

    def response(self, state, portfolio):
        return dict(portfolio=portfolio, confirmed=state['confirmed_revision'] == state['revision'] and state['confirmed_profile'] is not None,
                    stale=bool(portfolio and (portfolio['source_revision'] != state['revision'] or hashed(state.get('confirmed_profile')) != portfolio['source_hash'])),
                    jobs=[dict(document_id=j['document_id'], title=j['title']) for j in self.jobs])

    def _check(self, state, portfolio, data):
        require_confirmed(state)
        if data.get('revision') != state['revision']:
            raise ValueError('Profile changed. Reload Portfolio Studio.')
        if portfolio and data.get('portfolio_revision') != portfolio['revision']:
            raise ValueError('Portfolio changed. Reload before editing.')
        if portfolio and (portfolio['source_revision'] != state['revision'] or portfolio['source_hash'] != hashed(state['confirmed_profile'])):
            raise ValueError('Portfolio source is stale. Explicitly synchronize the confirmed profile first.')

    def _event(self, portfolio, kind, **values):
        portfolio['events'] = (portfolio.get('events', []) + [dict(at=now(), kind=kind, **values)])[-60:]

    def asset(self, workspace, asset_id):
        with self.store.lock:
            _, portfolio = self._get(workspace)
            asset = next((a for a in (portfolio or {}).get('assets', []) if a['id'] == asset_id), None)
            if not asset:
                raise ValueError('Asset not found in this active workspace.')
            return self.media.read(asset['key']), asset['mime']

    def audio(self, workspace, proposal_id):
        with self.store.lock:
            _, portfolio = self._get(workspace)
            narration = (portfolio or {}).get('narration') if proposal_id == 'accepted' else None
            pending = (portfolio or {}).get('pending')
            if pending and pending['kind'] == 'narration' and pending['id'] == proposal_id:
                narration = pending['value']
            if not narration:
                raise ValueError('Narration not found in this workspace.')
            return self.media.read(narration['key']), 'audio/wav'

    def archive(self, workspace, snapshot_id):
        self.store.get(workspace)
        with self.store.connect() as db:
            row = db.execute('SELECT archive FROM portfolio_snapshots WHERE id=? AND workspace=?', (snapshot_id, workspace)).fetchone()
        if not row:
            raise ValueError('Approved snapshot not found.')
        return row[0]

    def snapshot(self, workspace, snapshot_id):
        self.store.get(workspace)
        with self.store.connect() as db:
            row = db.execute('SELECT state FROM portfolio_snapshots WHERE id=? AND workspace=?', (snapshot_id, workspace)).fetchone()
        if not row:
            raise ValueError('Snapshot not found.')
        return json.loads(row[0])

    def action(self, workspace, operation, data):
        # Deliberately called BEFORE Service.action acquires its outer lock.
        with self.store.lock:
            state, portfolio = self._get(workspace)
            if operation == 'portfolio-init':
                require_confirmed(state)
                if data.get('revision') != state['revision']:
                    raise ValueError('Profile changed.')
                if portfolio and data.get('portfolio_revision') != portfolio['revision']:
                    raise ValueError('Portfolio changed.')
                old = portfolio
                portfolio = blank(state)
                if old:
                    portfolio['revision'] = old['revision'] + 1
                    portfolio['snapshots'] = old['snapshots']
                    # Carry exact-source assets only; never match title/index alone.
                    old_projects = {p['id']: p for p in old['projects']}
                    for asset in old['assets']:
                        project = old_projects.get(asset['project_id'])
                        matches = [p for p in portfolio['projects'] if project and all(p[k] == project[k] for k in ('title','description','technologies'))]
                        if len(matches) == 1:
                            asset = deepcopy(asset); asset['project_id'] = matches[0]['id']
                            asset.pop('analysis', None); asset['published'] = False
                            portfolio['assets'].append(asset)
                    self._event(portfolio, 'source-sync', note='Exact project matches retained privately; analyses require renewed review.')
                    from .portfolio_cleanup import media_keys
                    portfolio['retired_media'] = [dict(key=k) for k in sorted(media_keys(old)-media_keys(portfolio))]
                self._save(workspace, portfolio)
                return self.response(state, portfolio)
            self._check(state, portfolio, data)
            if not portfolio:
                raise ValueError('Create a portfolio from the confirmed profile first.')
            base = (state['revision'], portfolio['revision'], hashed(portfolio))
            candidate = deepcopy(portfolio)
            from .portfolio_cleanup import media_keys
            previous_media = media_keys(portfolio)
            if operation == 'portfolio-upload':
                if data.get('authorised') is not True:
                    raise ValueError('Confirm you may use and send this media for AI analysis.')
                project_id = data.get('project_id')
                if project_id not in {p['id'] for p in portfolio['projects']}:
                    raise ValueError('Choose a project from this source revision.')
                same = [a for a in portfolio['assets'] if a['project_id'] == project_id]
                video = data.get('kind') == 'video'
                if sum(a['mime'].startswith('video/' if video else 'image/') for a in same) >= (1 if video else 3):
                    raise ValueError('Use at most three images and one video per project.')
                if len(candidate['assets']) >= 12:
                    raise ValueError('Portfolio media limit reached (12 assets).')
                # Decode outside the lock below.
            elif operation == 'portfolio-save':
                if candidate.get('pending'):
                    raise ValueError('Accept or dismiss the current proposal before changing display settings.')
                settings = data.get('settings', candidate['settings'])
                if not isinstance(settings, dict) or set(settings) != set(candidate['settings']):
                    raise ValueError('Unsupported display settings.')
                if settings['theme'] not in ('editorial','technical','minimal') or settings['avatar'] not in ('orbit','leaf','none'):
                    raise ValueError('Choose a supported theme and guide.')
                if any(type(settings[k]) is not bool for k in ('show_email','show_phone','show_location','show_links')):
                    raise ValueError('Disclosure settings must be explicit booleans.')
                candidate['settings'] = settings
                selected = strings(data.get('published_assets', [a['id'] for a in candidate['assets'] if a.get('published')]), 12)
                if any(key not in {a['id'] for a in candidate['assets'] if a.get('analysis')} for key in selected):
                    raise ValueError('Only reviewed media can be selected for publication.')
                for asset in candidate['assets']:
                    asset['published'] = asset['id'] in selected
                candidate['pending'] = None
                self._event(candidate, 'display-saved', theme=settings['theme'], public_assets=len(selected))
            elif operation == 'portfolio-remove':
                if candidate.get('pending'):
                    raise ValueError('Accept or dismiss the current proposal before removing media.')
                key = data.get('asset_id')
                if key not in {a['id'] for a in candidate['assets']}:
                    raise ValueError('Asset not found.')
                candidate['assets'] = [a for a in candidate['assets'] if a['id'] != key]
                candidate['pending'] = None
            elif operation == 'portfolio-remove-narration':
                if candidate.get('pending'):
                    raise ValueError('Accept or dismiss the current proposal before removing narration.')
                candidate['narration'] = None
                self._event(candidate, 'narration-removed')
            elif operation in ('portfolio-edit-site','portfolio-edit-analysis'):
                if candidate.get('pending'):
                    raise ValueError('Review the existing proposal before opening an edit.')
                if operation == 'portfolio-edit-site':
                    value = dict(headline=candidate['headline'],bio=candidate['bio'],source_ids=candidate['bio_sources'],views=deepcopy(candidate['views']))
                    kind, asset_id, asset_hash = 'site', None, None
                else:
                    asset = next((a for a in candidate['assets'] if a['id']==data.get('asset_id')),None)
                    if not asset:
                        raise ValueError('Choose media from this workspace.')
                    value = deepcopy(asset.get('analysis')) or dict(caption='',alt='',description='',transcript='',hotspots=[],chapters=[],questions=[],warnings=['Owner-written explanation; no AI analysis performed.'])
                    kind, asset_id, asset_hash = 'analysis', asset['id'], asset['sha256']
                candidate['pending'] = dict(id=uuid.uuid4().hex,kind=kind,value=value,asset_id=asset_id,
                    asset_hash=asset_hash,model='owner edit — no model call',at=now())
                self._event(candidate,'owner-edit-proposed',proposal_kind=kind)
            elif operation == 'portfolio-review':
                pending = candidate.get('pending')
                if not pending or pending['id'] != data.get('proposal_id'):
                    raise ValueError('Proposal changed or has already been handled.')
                if data.get('choice') == 'accept':
                    value = data.get('value', pending['value'])
                    if pending['kind'] == 'analysis':
                        asset = next(a for a in candidate['assets'] if a['id'] == pending['asset_id'])
                        if asset['sha256'] != pending['asset_hash']:
                            raise ValueError('Image/video changed.')
                        asset['analysis'] = validate_analysis(value, asset, candidate['sources'])
                        asset['reviewed_at'] = now()
                        if 'publish_media' in data:
                            if type(data['publish_media']) is not bool:
                                raise ValueError('Media disclosure must be an explicit boolean.')
                            asset['published'] = data['publish_media']
                    elif pending['kind'] == 'site':
                        value = validate_site(value, candidate, self.jobs)
                        candidate.update(headline=value['headline'], bio=value['bio'], bio_sources=value['source_ids'], views=value['views'], narration=None)
                    else:
                        # Audio bytes and script are an inseparable server-generated
                        # proposal. A client may not substitute another blob/path.
                        if value != pending['value']:
                            raise ValueError('Narration cannot be edited. Dismiss and generate it again.')
                        candidate['narration'] = deepcopy(pending['value'])
                    self._event(candidate, 'accepted', proposal_id=pending['id'], proposal_kind=pending['kind'])
                elif data.get('choice') == 'dismiss':
                    self._event(candidate, 'dismissed', proposal_id=pending['id'])
                else:
                    raise ValueError('Choose accept or dismiss.')
                candidate['pending'] = None
            elif operation not in ('portfolio-analyse','portfolio-propose','portfolio-narrate','portfolio-approve','portfolio-reader'):
                raise ValueError('Unknown portfolio operation.')
        # Expensive decoding/provider calls do not hold the global store lock.
        if operation == 'portfolio-upload':
            meta = self.media.video(data.get('content')) if video else self.media.image(data.get('content'))
            candidate['assets'].append(dict(id=uuid.uuid4().hex, project_id=project_id,
                name=text(data.get('filename','Media'), 160), published=False, authorised_at=now(), **meta))
        elif operation in ('portfolio-analyse','portfolio-propose'):
            if candidate.get('pending'):
                raise ValueError('Accept or dismiss the existing proposal first.')
            context = dict(sources=candidate['sources'], projects=candidate['projects'], _max_output_tokens=8000)
            asset = None
            if operation == 'portfolio-analyse':
                asset = next((a for a in candidate['assets'] if a['id'] == data.get('asset_id')), None)
                if not asset:
                    raise ValueError('Asset not found.')
                context.update(asset={k: asset[k] for k in ('id','mime','duration')},
                    _attachment=dict(mimeType=asset['mime'], data=base64.b64encode(self.media.read(asset['key'])).decode()))
                prompt = prompts.ANALYSE
            else:
                chosen = strings(data.get('job_ids', []), 2)
                jobs = [job for job in self.jobs if job['document_id'] in chosen]
                if len(jobs) != len(chosen):
                    raise ValueError('Unknown target job.')
                context.update(profile={k: candidate['profile'][k] for k in ('skills','goal')}, jobs=jobs,
                    authoring_brief=text(data.get('brief',''),800),
                    reviewed_media=[dict(project_id=a['project_id'], analysis=a['analysis']) for a in candidate['assets'] if a.get('analysis')])
                prompt = prompts.SITE
            context['_output_schema'] = proposal_schema(candidate, asset, jobs if not asset else ())
            if len(json.dumps({k:v for k,v in context.items() if k!='_attachment'})) > 120000:
                raise ValueError('Portfolio source text exceeds the analysis context budget. Reduce repeated profile text before synchronizing.')
            attempts = []
            messages = [dict(role='system', content=prompt), dict(role='user', content='Prepare a bounded proposal for my review.')]
            try:
                # One bounded model repair, never silent coordinate clamping or
                # invented ID/skill substitution. Both attempts remain auditable.
                for attempt in range(2):
                    raw = self.model.decide(messages, context)
                    parsed = json.loads(raw)
                    try:
                        value = validate_analysis(parsed, asset, candidate['sources']) if asset else validate_site(parsed, candidate, jobs)
                    except ValueError as error:
                        attempts.append(dict(attempt=attempt+1,valid=False,error=str(error),raw=raw[:20000]))
                        if attempt:
                            raise
                        messages += [dict(role='assistant',content=raw),dict(role='user',content='Validation rejected this proposal: '+str(error)+'. Return a corrected complete JSON proposal. Copy exact supplied IDs and skill strings; do not invent replacements. Use normalized width/height, not bottom/right coordinates.')]
                    else:
                        attempts.append(dict(attempt=attempt+1,valid=True))
                        break
            except (GeminiError, ValueError) as error:
                with self.store.lock:
                    current_state, current = self._get(workspace)
                    if current and (current_state['revision'], current['revision'], hashed(current)) == base:
                        self._event(current, 'generation-failed', operation=operation, error=str(error)[:300], attempts=attempts)
                        self._save(workspace, current)
                raise
            candidate['pending'] = dict(id=uuid.uuid4().hex, kind='analysis' if asset else 'site', value=value,
                asset_id=asset['id'] if asset else None, asset_hash=asset['sha256'] if asset else None,
                model=getattr(self.model,'name','unknown'), prompt_version=prompts.VERSION, at=now())
            self._event(candidate, 'model-proposal', prompt_version=prompts.VERSION,
                        model=getattr(self.model,'name','unknown'), raw=parsed, input_hash=hashed(context), attempts=attempts)
        elif operation == 'portfolio-narrate':
            if candidate.get('pending'):
                raise ValueError('Review the existing proposal first.')
            from .portfolio_narration import narrate
            script = f"This is an AI guide to {candidate['profile']['name']}'s approved portfolio. " + candidate['bio']
            script = text(script, 3500)
            raw, model = narrate(self.model.settings, script)
            key = self.media.put(raw, 'wav')
            candidate['pending'] = dict(id=uuid.uuid4().hex, kind='narration', at=now(), model=model,
                value=dict(key=key, script=script, sha256=hashlib.sha256(raw).hexdigest(), mime='audio/wav'))
        elif operation == 'portfolio-approve':
            if data.get('accepted') is not True or candidate.get('pending'):
                raise ValueError('Review pending proposals and explicitly approve all displayed public content first.')
            if len(candidate['snapshots']) >= 10:
                raise ValueError('Maximum 10 immutable snapshots per workspace.')
            from .portfolio_export import public_projection, package
            public = public_projection(candidate)
            cv = None
            if data.get('include_cv') is True:
                from .pdf import render
                # Existing renderer enforces current, confirmed profile revision.
                cv = render(state)
                public['cv_url'] = 'resume.pdf'
            snapshot_id = uuid.uuid4().hex
            public.update(id=snapshot_id, approved_at=now())
            archive = package(public, self.media, cv)
            candidate['snapshots'].append(dict(id=snapshot_id, approved_at=public['approved_at'], theme=public['theme'], renderer_version=public['renderer_version'], digest=hashed(public), project_count=len(public['projects']), source_revision=public['source_revision'], portfolio_revision=candidate['revision']+1))
        elif operation == 'portfolio-reader':
            # The reader receives ONLY a projection of an approved immutable package.
            public = self.snapshot(workspace, data.get('snapshot_id'))
            archive = self.archive(workspace, public['id'])
            from .portfolio_reader import install_snapshot
            install_snapshot(public['id'], archive, self.store.path.parent / 'reader-public')
            return dict(url='http://127.0.0.1:8001/site/' + public['id'] + '/',
                        note='Start the separate local reader: python -m server.portfolio_reader')
        with self.store.lock:
            current_state, current = self._get(workspace)
            if not current or (current_state['revision'], current['revision'], hashed(current)) != base:
                raise ValueError('Source or portfolio changed while this operation ran. Result discarded; reload.')
            if operation == 'portfolio-approve' and data.get('include_cv') is True and hashed(current_state.get('draft')) != hashed(state.get('draft')):
                raise ValueError('The CV changed while approval ran. Review it again before attaching it.')
            retired = {entry['key'] for entry in candidate.get('retired_media',[])}
            retired.update(previous_media-media_keys(candidate))
            candidate['retired_media'] = [dict(key=k) for k in sorted(retired)]
            if any(not (self.media.root/key).is_file() for key in media_keys(candidate)):
                raise ValueError('Media changed during this operation. Reload and upload again.')
            candidate['revision'] += 1
            if operation == 'portfolio-approve':
                with self.store.connect() as db:
                    db.execute('INSERT INTO portfolio_snapshots VALUES (?,?,?,?)', (snapshot_id, workspace, json.dumps(public), archive))
                    db.execute('UPDATE portfolios SET state=? WHERE workspace=?', (json.dumps(candidate), workspace))
            else:
                self._save(workspace, candidate)
            return self.response(current_state, candidate)

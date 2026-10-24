"""Whitelist public content and freeze the exact portable website bytes."""
from copy import deepcopy
import hashlib
import html
import io
import json
from pathlib import Path
import zipfile

from .portfolio import safe_link

ROOT = Path(__file__).resolve().parents[1]
RENDERER_VERSION = 'showcase-6.6'


def public_projection(portfolio):
    profile, settings = portfolio['profile'], portfolio['settings']
    person = {key: deepcopy(profile.get(key, '' if key != 'skills' else []))
              for key in ('name','education','experience','achievements','skills','goal')}
    for flag, field in (('show_email','email'), ('show_phone','phone'), ('show_location','location')):
        if settings[flag]:
            person[field] = profile.get(field, '')
    person['links'] = []
    if settings['show_links']:
        for field in ('linkedin','github','portfolio'):
            if profile.get(field):
                person['links'].append(dict(label=field.title(), url=safe_link(profile[field])))
    sources = {key: person[key] for key in ('name','education','experience','achievements','goal') if person.get(key)}
    for key in ('email','phone','location'):
        if person.get(key):
            sources[key] = person[key]
    # These are explicitly reviewed public project descriptions, not a copy of
    # the private SourceCatalog or entire workspace.
    projects = deepcopy(portfolio['projects'])
    sources.update({project['id']: project['description'] for project in projects})
    for key in portfolio.get('bio_sources', []):
        sources[key] = portfolio['sources'][key]
    assets = []
    for asset in portfolio['assets']:
        if asset.get('published') and asset.get('analysis'):
            analysis = deepcopy(asset['analysis'])
            for hotspot in analysis['hotspots']:
                for key in hotspot['source_ids']:
                    sources[key] = portfolio['sources'][key]
            assets.append({key: deepcopy(asset[key]) for key in ('id','project_id','key','sha256','mime','width','height','duration')})
            assets[-1].update(analysis=analysis, url='media/' + asset['key'])
    narration = deepcopy(portfolio.get('narration'))
    if narration:
        narration['url'] = 'media/' + narration['key']
    return dict(schema_version=1, renderer_version=RENDERER_VERSION, person=person, headline=portfolio['headline'], bio=portfolio['bio'],
                projects=projects, views=deepcopy(portfolio['views']), assets=assets, sources=sources,
                theme=settings['theme'], avatar=settings['avatar'], narration=narration,
                source_revision=portfolio['source_revision'])


def document_html(public):
    data = json.dumps(public, ensure_ascii=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    name = html.escape(public['person']['name'])
    document = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><meta name="referrer" content="no-referrer"><title>{name} — Professional portfolio</title>
<link rel="stylesheet" href="portfolio.css"></head><body style="margin:0"><div id="portfolio-root"></div>
<noscript><h1>{name}</h1><p>{html.escape(public['bio'])}</p><p>{html.escape(public['person']['experience'])}</p></noscript>
<script type="application/json" id="portfolio-data">{data}</script><script src="portfolio.js" defer></script></body></html>'''
    return document


def package(public, media, cv=None):
    runtime = ROOT / 'portfolio-runtime'
    js, css = runtime / 'portfolio.js', runtime / 'portfolio.css'
    if not js.is_file() or not css.is_file():
        raise ValueError('Build the standalone portfolio renderer first: pnpm run build:portfolio')
    document = document_html(public)
    entries = {'index.html': document.encode(), 'portfolio.js': js.read_bytes(), 'portfolio.css': css.read_bytes(),
               'README.txt': b'Approved static portfolio. Open index.html. No key required. The purple floating-island tour remains the main entrance. Select a console or a library project-world button to open one separate cinematic project scene, with full-scale surroundings and three labelled camera views. All library covers are actual 3D canvas views, not images or flat artwork. Cover motion runs on hover/focus; reviewed media stay in the case studies. Back or Escape returns to your place; opening the real case study is a separate action. All 3D surroundings are original symbolic illustrations, not real workplaces, running models or proof of project results. Bundled Three.js needs WebGL 2. Two fingers or drag orbit the scene; pinch zooms, without an enable step. Scroll outside the scene to read. Take the tour is self-paced. Why this project? shows exact approved source excerpts and disclosed media counts. Lightweight mode disables shadows and lowers pixel ratio. Standard view skips the island; unavailable covers/project scenes provide a text/case-study fallback. Camera controls and project buttons support keyboard navigation. No remote models/fonts/CDNs are needed. Live chat requires the separately running local reader on port 8001. Do not upload the owner app or private database. This export is a distributable copy, not revocable private storage.\n',
               'THIRD_PARTY_NOTICES.txt': (ROOT / 'THIRD_PARTY_NOTICES.txt').read_bytes()}
    if cv is not None:
        entries['resume.pdf'] = cv
    for asset in public['assets'] + ([public['narration']] if public.get('narration') else []):
        raw = media.read(asset['key'])
        if hashlib.sha256(raw).hexdigest() != asset['sha256']:
            raise ValueError('An approved media file failed integrity validation.')
        entries['media/' + asset['key']] = raw
    if sum(len(raw) for raw in entries.values()) > 80 * 1024 * 1024:
        raise ValueError('Export exceeds the 80 MB portfolio limit.')
    manifest = {'snapshot_id': public['id'], 'files': {key: hashlib.sha256(raw).hexdigest() for key, raw in entries.items()}}
    entries['manifest.json'] = json.dumps(manifest, indent=2).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for key, raw in entries.items():
            archive.writestr(key, raw)
    return output.getvalue()

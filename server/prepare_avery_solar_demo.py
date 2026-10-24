"""Explicit local Demo CV update. Never run this helper during normal startup."""
import argparse
import base64
from copy import deepcopy
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import uuid

from .service import ROOT, refresh_existing_draft
from .store import Store, require_confirmed, update_profile
from .portfolio import blank, now, validate_analysis
from .portfolio_assets import MediaStore, MAX_VIDEO, digest
from .seed_labelled_sample import LABEL

WORKSPACE = '276d3f8fb2c945539752b6fb55d22974'
PROJECT = dict(title='SolarVision', description=(
    'SolarVision is an AI-powered solar-panel inspection application, included here as a supplied demonstration case study for this Demo CV. '
    'The recording presents model-selection and drone controls, a live inspection feed, annotated defect views and an inspection dashboard. '
    'It also includes introductory solar-energy context footage. The supplied recording is not a claim that Avery personally authored the application.'),
    technologies='Computer Vision, Solar Inspection, Live Video, Defect Visualisation')


def _solar(project):
    return project['title'].strip().casefold() == 'solarvision'


def _check_demo(state):
    label = state['label'].casefold()
    if state['profile']['name'] != 'Avery Morgan' or not (
            state['label'] == LABEL or 'synthetic' in label or ('avery' in label and 'demo' in label)):
        raise ValueError('Choose the explicitly labelled Avery fictional/development demo, not a real candidate.')
    require_confirmed(state)
    if state.get('pending_cv'):
        raise ValueError('Resolve the current CV proposal before preparing this demo.')


def _sync_preserving(old, state):
    """A narrow additive demo sync, not the general portfolio-init reset path."""
    fresh = blank(state)
    if not old:
        return fresh
    if old.get('pending'):
        raise ValueError('Resolve the current portfolio proposal before preparing this demo.')
    # Only an additive SolarVision difference is allowed. Never silently confirm
    # unrelated edits, remove existing media or discard reviewed annotations.
    def without_solar(profile):
        value = deepcopy(profile)
        value['projects'] = [p for p in value['projects'] if not _solar(p)]
        return value
    if without_solar(old['profile']) != without_solar(fresh['profile']):
        raise ValueError('Portfolio has unrelated stale profile edits. Review/synchronize those explicitly first.')
    new_projects = fresh['projects']
    project_map = {}
    for project in old['projects']:
        exact = [p for p in new_projects if all(p[key] == project[key] for key in ('title', 'description', 'technologies'))]
        if len(exact) != 1:
            raise ValueError('A reviewed project changed or became ambiguous. Synchronize it explicitly first.')
        project_map[project['id']] = exact[0]['id']
    source_map = {}
    for key, value in old['sources'].items():
        if fresh['sources'].get(key) == value:
            source_map[key] = key
        else:
            matches = [k for k, v in fresh['sources'].items() if v == value]
            if len(matches) != 1:
                raise ValueError('A reviewed source changed or became ambiguous. Review it explicitly first.')
            source_map[key] = matches[0]
    result = deepcopy(old)
    result.update({key: fresh[key] for key in ('profile', 'projects', 'sources', 'source_revision', 'source_hash')})
    result['bio_sources'] = [source_map[key] for key in old['bio_sources']]
    for view in result['views']:
        view['project_ids'] = [project_map[key] for key in view['project_ids']]
        if view['id'] == 'general':
            view['project_ids'] = [p['id'] for p in new_projects]
    for asset in result['assets']:
        asset['project_id'] = project_map[asset['project_id']]
        for hotspot in (asset.get('analysis') or {}).get('hotspots', []):
            hotspot['source_ids'] = [source_map[key] for key in hotspot.get('source_ids', [])]
    return result


def _analysis(duration):
    chapters = [
        (0, 'Introduction & context', 'Opening solar-energy context footage.'),
        (110, 'Drone controls', 'Around this bookmark: model selection and drone controls.'),
        (120, 'Live inspection', 'Around this bookmark: live feed and inspection setup.'),
        (140, 'Inspection dashboard', 'Around this bookmark: inspection overview and annotated defects.'),
        (160, 'Detection overlays', 'Around this bookmark: bounding boxes and detection list.'),
        (190, 'Raw-feed comparison', 'Around this bookmark: a view with bounding-box overlays switched off.')]
    return dict(caption='SolarVision · Application walkthrough',
        alt='SolarVision controls, live inspection and defect review screens.',
        description='Full user-supplied recording. The opening contains solar-energy context footage; SolarVision application controls and dashboards appear later. The chapter buttons are observed bookmarks, not exact scene-transition boundaries.',
        hotspots=[], transcript='', questions=[],
        warnings=['Supplied demonstration case study in a Demo CV, not evidence of Avery’s authorship. Opening context footage does not establish deployment or model accuracy.'],
        chapters=[dict(time=t, title=title, description=description) for t, title, description in chapters if t < duration])


def prepare(store, workspace, path, media=None):
    """Apply the explicit additive demo request idempotently, without a model.

    Existing reviewed content and immutable snapshots stay unchanged. Media is
    validated before the workspace and portfolio are committed together. Tests
    invoke this function exclusively against temporary stores.
    """
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_VIDEO:
        raise ValueError('The complete upload-ready MP4 must exist and be at most 12 MB.')
    raw = path.read_bytes()
    sha = digest(raw)
    media = media or MediaStore(store.path.parent / 'portfolio-media')
    with store.lock:
        original = store.get(workspace)
        _check_demo(original)
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS portfolios (workspace TEXT PRIMARY KEY, state TEXT NOT NULL)')
            row = db.execute('SELECT state FROM portfolios WHERE workspace=?', (workspace,)).fetchone()
        old = json.loads(row[0]) if row else None
        state = deepcopy(original)
        matches = [p for p in state['profile']['projects'] if _solar(p)]
        if len(matches) > 1:
            raise ValueError('More than one SolarVision entry exists. Choose/merge it explicitly first.')
        if not matches:
            update_profile(state, {'projects': state['profile']['projects'] + [deepcopy(PROJECT)]})
            state.update(confirmed_revision=state['revision'], confirmed_profile=deepcopy(state['profile']))
            refresh_existing_draft(state)
        portfolio = _sync_preserving(old, state)
        project = next(p for p in portfolio['projects'] if _solar(p))
        videos = [a for a in portfolio['assets'] if a['project_id'] == project['id'] and a['mime'].startswith('video/')]
        if len(videos) > 1 or videos and videos[0]['sha256'] != sha:
            raise ValueError('SolarVision already has a different video. Replace it explicitly in Portfolio Studio.')
        repaired_blob = False
        if videos:
            asset = videos[0]
            # An interrupted prior import may have metadata but no blob.
            if not (media.root / asset['key']).is_file():
                asset.update(media.video(base64.b64encode(raw).decode()))
                repaired_blob = True
        else:
            if len(portfolio['assets']) >= 12:
                raise ValueError('Portfolio media limit reached. Remove an asset explicitly first.')
            meta = media.video(base64.b64encode(raw).decode())
            asset = dict(id=uuid.uuid4().hex, project_id=project['id'], name='SolarVision application walkthrough.mp4',
                         published=False, authorised_at=now(), **meta)
            portfolio['assets'].append(asset)
        if not asset.get('analysis'):
            asset['analysis'] = validate_analysis(_analysis(asset['duration']), asset, portfolio['sources'])
            asset['reviewed_at'] = now()
        asset['published'] = True
        changed = state != original or portfolio != old or repaired_blob
        if not changed:
            return dict(workspace=workspace, changed=False, project_id=project['id'], asset_id=asset['id'])
        portfolio['revision'] = (old or {}).get('revision', -1) + 1
        portfolio['events'] = (portfolio.get('events', []) + [dict(at=now(), kind='user-requested-demo-update',
            note='Added/repaired the supplied SolarVision demonstration case study and recording without a model call. Existing portfolio customisations and approved snapshots retained.')])[-60:]
        # No partially confirmed profile update is committed separately from
        # its repaired website. Detect concurrent changes before either write.
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT state FROM workspaces WHERE id=?', (workspace,)).fetchone()
            current_portfolio = db.execute('SELECT state FROM portfolios WHERE workspace=?', (workspace,)).fetchone()
            if not current or json.loads(current[0]) != original or (json.loads(current_portfolio[0]) if current_portfolio else None) != old:
                raise ValueError('Workspace or portfolio changed during preparation. Reload and retry.')
            db.execute('UPDATE workspaces SET state=? WHERE id=?', (json.dumps(state, ensure_ascii=False), workspace))
            db.execute('INSERT INTO portfolios VALUES (?,?) ON CONFLICT(workspace) DO UPDATE SET state=excluded.state',
                       (workspace, json.dumps(portfolio, ensure_ascii=False)))
        return dict(workspace=workspace, changed=True, project_id=project['id'], asset_id=asset['id'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-user-request', action='store_true')
    parser.add_argument('--workspace-id', default=WORKSPACE,
                        help='Explicit labelled Avery demo; defaults to the original development-demo ID for compatibility.')
    args = parser.parse_args()
    if not args.apply_user_request:
        raise SystemExit('No change made. Requires --apply-user-request following the user\'s explicit instruction.')
    path = ROOT / 'runtime/imports/solarvision/SolarVision-full-upload-ready.mp4'
    store = Store(ROOT / 'runtime/proofcv.sqlite3')
    _check_demo(store.get(args.workspace_id))
    backup = path.parent / ('before-demo-update-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
    backup.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(store.path)) as src, closing(sqlite3.connect(backup)) as dst:
        src.backup(dst)
    result = prepare(store, args.workspace_id, path)
    print('Updated the selected local Avery Demo CV and supplied SolarVision recording.' if result['changed'] else
          'SolarVision and its reviewed recording are already present. No repeated update was performed.')
    print('Existing portfolio settings, role views, reviewed media and approved snapshots were preserved.')
    print('No model call or public deployment was performed. Refresh the selected draft preview.')


if __name__ == '__main__':
    main()

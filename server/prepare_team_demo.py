"""Explicitly load the shared fictional portfolio draft, never a private database."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import uuid

from .portfolio import blank, hashed, now, validate_analysis, validate_site
from .portfolio_assets import MediaStore, digest
from .prepare_avery_solar_demo import _analysis
from .seed_labelled_sample import LABEL, _profile, seed
from .store import Store, require_confirmed

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples' / 'portfolio'


def prepare(store, workspace, fixture=None, video=None, media=None):
    """Load only into an untouched, confirmed Avery sample; preserve all other work.

    The checked-in story is an explicitly labelled fictional demonstration. This
    creates an editable draft, not an approved snapshot or a live recruiter site.
    """
    fixture = deepcopy(fixture) if fixture is not None else json.loads(
        (EXAMPLES / 'avery-demo.json').read_text(encoding='utf-8'))
    if fixture.get('schema_version') != 1 or fixture.get('profile_hash') != hashed(_profile()):
        raise ValueError('The demo fixture does not match the shared four-project profile.')
    video = Path(video) if video is not None else EXAMPLES / 'solarvision-demo.mp4'
    with store.lock:
        state = store.get(workspace)
        require_confirmed(state)
        if state['label'] != LABEL or hashed(state['confirmed_profile']) != fixture['profile_hash']:
            raise ValueError('Use the unchanged, confirmed four-project Avery sample. Existing personal edits are not overwritten.')
        if state.get('pending_cv'):
            raise ValueError('Resolve the current CV proposal first.')
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS portfolios (workspace TEXT PRIMARY KEY, state TEXT NOT NULL)')
            row = db.execute('SELECT state FROM portfolios WHERE workspace=?', (workspace,)).fetchone()
        if row:
            old = json.loads(row[0])
            if any(event.get('kind') == 'team-demo-prepared' for event in old.get('events', [])):
                return dict(workspace=workspace, changed=False)
            raise ValueError('A portfolio already exists. Its story and media are retained; use Portfolio Studio to edit it.')
        portfolio = blank(state)
        jobs = [json.loads(line) for line in (ROOT / 'data/jobs.jsonl').read_text(encoding='utf-8').splitlines()]
        plan = validate_site({key: fixture[key] for key in ('headline', 'bio', 'source_ids', 'views')}, portfolio, jobs)
        settings = fixture['settings']
        if (set(settings) != set(portfolio['settings'])
                or settings['theme'] not in ('editorial', 'technical', 'minimal')
                or settings['avatar'] not in ('orbit', 'leaf', 'none')
                or any(type(settings[key]) is not bool for key in ('show_email', 'show_phone', 'show_location', 'show_links'))
                or any(settings[key] for key in ('show_email', 'show_phone', 'show_links'))):
            raise ValueError('Invalid demo appearance or disclosure settings.')
        if not video.is_file() or not 0 < video.stat().st_size <= 12 * 1024 * 1024:
            raise ValueError('The bundled SolarVision demonstration video is missing or oversized.')
        raw = video.read_bytes()
        if digest(raw) != fixture['video']['sha256']:
            raise ValueError('The demonstration video checksum does not match.')
        import base64
        media = media or MediaStore(store.path.parent / 'portfolio-media')
        meta = media.video(base64.b64encode(raw).decode())
        solar = next(project for project in portfolio['projects'] if project['title'] == 'SolarVision')
        asset = dict(id=uuid.uuid4().hex, project_id=solar['id'],
                     name='SolarVision application walkthrough.mp4', published=True,
                     authorised_at=now(), reviewed_at=now(), **meta)
        asset['analysis'] = validate_analysis(_analysis(asset['duration']), asset, portfolio['sources'])
        portfolio.update(headline=plan['headline'], bio=plan['bio'], bio_sources=plan['source_ids'],
                         views=plan['views'], settings=settings, assets=[asset], revision=1)
        portfolio['events'].append(dict(at=now(), kind='team-demo-prepared',
            note='Loaded the shared fictional draft and supplied demonstration video. Review and approve in Portfolio Studio before enabling a recruiter version.'))
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT state FROM workspaces WHERE id=?', (workspace,)).fetchone()
            exists = db.execute('SELECT 1 FROM portfolios WHERE workspace=?', (workspace,)).fetchone()
            if not current or json.loads(current[0]) != state or exists:
                raise ValueError('The workspace changed during preparation. Reload and retry.')
            db.execute('INSERT INTO portfolios VALUES (?,?)', (workspace, json.dumps(portfolio, ensure_ascii=False)))
        return dict(workspace=workspace, changed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Create the shared fictional draft explicitly.')
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit('No change made. Use --apply to load the fictional Avery portfolio draft.')
    store = Store(ROOT / 'runtime/proofcv.sqlite3')
    result = prepare(store, seed(store))
    print('Shared Avery portfolio draft prepared.' if result['changed'] else 'Already prepared; all subsequent edits retained.')
    print('Open Portfolio Studio. Review its story, views and supplied video, then approve an export if wanted.')
    print('No AI call, public deployment or private database import was performed.')


if __name__ == '__main__':
    main()

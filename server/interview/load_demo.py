"""Load the presentation demo into Avery Morgan's Interview Coach, on any computer.

    python -m server.interview.load_demo            # load into the labelled Avery workspace
    python -m server.interview.load_demo --replace  # swap out existing coach data (a backup is kept)

The demo (examples/interview-coach/avery-demo.json) was recorded through the real app:
spoken answers written from Avery's confirmed profile, transcribed and scored by the
coach. Dates are stored relative to the day it was exported, so it always shows the
skill check three days ago, three finished plan days, today still open, a mock
interview with its report, and the interview nine days away. No model is needed:
the saved transcripts and scores are loaded as they are.
"""
import argparse
import json
import shutil
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from ..seed_labelled_sample import LABEL
from ..store import Store
from .attempts import AttemptStore

ROOT = Path(__file__).resolve().parents[2]
DEMO_PATH = ROOT / 'examples' / 'interview-coach' / 'avery-demo.json'
TABLES = ('attempts', 'mock_sessions', 'diagnostics', 'coach_setup', 'plan_ticks')


def local_zone():
    return datetime.now().astimezone().tzinfo


def relative(timestamp, today):
    """A stored UTC time as days from today plus the local time of day."""
    moment = datetime.fromisoformat(timestamp).astimezone(local_zone())
    return {'days': (moment.date() - today).days, 'time': moment.strftime('%H:%M:%S')}


def absolute(when, today):
    moment = datetime.combine(today + timedelta(when['days']), time.fromisoformat(when['time']), local_zone())
    return moment.astimezone(timezone.utc).isoformat(timespec='seconds')


def export(store, workspace_id, today=None):
    """The workspace's Interview Coach data, with every date made relative to today."""
    today = today or date.today()
    with store.connect() as connection:
        rows = lambda sql: connection.execute(sql, (workspace_id,)).fetchall()
        setup = rows('SELECT setup, saved_at FROM coach_setup WHERE workspace_id=?')
        attempts = rows('SELECT id, question_id, created_at, transcript, summary FROM attempts WHERE workspace_id=? ORDER BY id')
        checks = rows('SELECT job, questions, answers, created_at, finished_at FROM diagnostics WHERE workspace_id=? ORDER BY created_at DESC')
        mocks = rows('SELECT job, questions, answers, created_at FROM mock_sessions WHERE workspace_id=? ORDER BY created_at DESC')
        ticks = rows('SELECT day, task FROM plan_ticks WHERE workspace_id=?')
    if not setup or not checks:
        raise ValueError('This workspace has no Interview Coach setup and skill check to export.')
    saved = json.loads(setup[0][0])
    interview = date.fromisoformat(saved.pop('interview_date'))
    job, questions, answers, created, finished = checks[0]
    return {
        'note': 'Interview Coach demo for the labelled Avery Morgan sample, recorded through the app. Dates are relative to the load day.',
        'setup': {**saved, 'interview_in_days': (interview - today).days, 'saved_at': relative(setup[0][1], today)},
        'attempts': [{'ref': i, 'question_id': q, 'created_at': relative(at, today), 'transcript': t, 'summary': json.loads(s)} for i, q, at, t, s in attempts],
        'skill_check': {'job': json.loads(job), 'questions': json.loads(questions), 'answers': json.loads(answers),
                        'created_at': relative(created, today), 'finished_at': relative(finished, today)},
        'mocks': [{'job': json.loads(j), 'questions': json.loads(qs), 'answers': json.loads(a), 'created_at': relative(at, today)} for j, qs, a, at in mocks],
        'ticks': [{'days': (date.fromisoformat(day) - today).days, 'task': task} for day, task in ticks],
    }


def remap(answers, ids):
    """Point a session's answers at the newly inserted attempt ids."""
    return {k: ({**v, 'id': ids[int(v['id'])]} if isinstance(v, dict) else ids[int(v)]) for k, v in answers.items()}


def find_workspace(workspaces, workspace_id=None):
    state = workspaces.get(workspace_id) if workspace_id else next(
        (workspaces.get(w['id']) for w in workspaces.list() if w['label'] == LABEL), None)
    if not state:
        raise ValueError(f'No "{LABEL}" workspace found. Open the app once so the sample is created, or pass --workspace.')
    if state.get('confirmed_revision') != state.get('revision') or not state.get('confirmed_profile'):
        raise ValueError(f'Confirm the profile of "{state["label"]}" in My profile first, then run this again.')
    return state


def load(store_path, coach_path, demo, workspace_id=None, replace=False, today=None):
    """Insert the demo into a workspace's Interview Coach; returns what was loaded."""
    today = today or date.today()
    state = find_workspace(Store(Path(store_path)), workspace_id)
    store = AttemptStore(coach_path)
    workspace = state['id']
    with store.connect() as connection:
        existing = sum(connection.execute(f'SELECT COUNT(*) FROM {t} WHERE workspace_id=?', (workspace,)).fetchone()[0] for t in TABLES)
    backup = None
    if existing and not replace:
        raise ValueError(f'"{state["label"]}" already has Interview Coach data. Run again with --replace to swap it for the demo (a backup is kept).')
    if existing:
        backup = Path(coach_path).with_name(f'interview.sqlite3.before-demo-{datetime.now():%Y%m%d-%H%M%S}')
        shutil.copy2(coach_path, backup)
    with store.lock, store.connect() as connection:
        for table in TABLES:
            connection.execute(f'DELETE FROM {table} WHERE workspace_id=?', (workspace,))
        ids = {}
        for a in demo['attempts']:
            ids[a['ref']] = connection.execute('INSERT INTO attempts (workspace_id, question_id, created_at, transcript, summary) VALUES (?, ?, ?, ?, ?)',
                                               (workspace, a['question_id'], absolute(a['created_at'], today), a['transcript'], json.dumps(a['summary']))).lastrowid
        check = demo['skill_check']
        connection.execute('INSERT INTO diagnostics (id, workspace_id, job, created_at, questions, answers, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                           (uuid.uuid4().hex, workspace, json.dumps(check['job']), absolute(check['created_at'], today), json.dumps(check['questions']),
                            json.dumps(remap(check['answers'], ids)), absolute(check['finished_at'], today)))
        for mock in demo['mocks']:
            connection.execute('INSERT INTO mock_sessions (id, workspace_id, created_at, job, questions, answers) VALUES (?, ?, ?, ?, ?, ?)',
                               (uuid.uuid4().hex, workspace, absolute(mock['created_at'], today), json.dumps(mock['job']), json.dumps(mock['questions']),
                                json.dumps(remap(mock['answers'], ids))))
        setup = {k: v for k, v in demo['setup'].items() if k not in ('interview_in_days', 'saved_at')}
        setup['interview_date'] = (today + timedelta(demo['setup']['interview_in_days'])).isoformat()
        connection.execute('INSERT INTO coach_setup (workspace_id, setup, saved_at) VALUES (?, ?, ?)',
                           (workspace, json.dumps(setup), absolute(demo['setup']['saved_at'], today)))
        for tick in demo['ticks']:
            connection.execute('INSERT INTO plan_ticks (workspace_id, job_id, day, task) VALUES (?, ?, ?, ?)',
                               (workspace, setup['job'], (today + timedelta(tick['days'])).isoformat(), tick['task']))
    return {'workspace': state['label'], 'attempts': len(ids), 'mocks': len(demo['mocks']), 'interview_date': setup['interview_date'],
            'replaced': bool(existing), 'backup': str(backup) if backup else None}


def main():
    parser = argparse.ArgumentParser(description='Load the Interview Coach presentation demo into the Avery Morgan workspace.')
    parser.add_argument('--replace', action='store_true', help='replace existing Interview Coach data for that workspace (a backup is kept)')
    parser.add_argument('--workspace', help='load into this workspace id instead of the labelled Avery sample')
    parser.add_argument('--export', metavar='WORKSPACE_ID', help='(maintainers) save that workspace\'s coach data as the demo file')
    args = parser.parse_args()
    runtime = ROOT / 'runtime'
    if args.export:
        demo = export(AttemptStore(runtime / 'interview.sqlite3'), args.export)
        DEMO_PATH.write_text(json.dumps(demo, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'Exported {len(demo["attempts"])} answers to {DEMO_PATH}')
        return
    try:
        result = load(runtime / 'proofcv.sqlite3', runtime / 'interview.sqlite3', json.loads(DEMO_PATH.read_text(encoding='utf-8')),
                      args.workspace, args.replace)
    except ValueError as error:
        raise SystemExit(str(error))
    print(f'Loaded the demo into "{result["workspace"]}": {result["attempts"]} answers, {result["mocks"]} mock interview, '
          f'interview on {result["interview_date"]}.' + (f' Previous coach data backed up to {result["backup"]}.' if result['backup'] else ''))
    print('Restart the ProofCV server if it is running, then open Interview Coach.')


if __name__ == '__main__':
    main()

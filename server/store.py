"""SQLite-backed local workspaces. IDs are storage keys, never filesystem paths."""
import json
import sqlite3
import uuid
import re
from copy import deepcopy
from pathlib import Path
from threading import RLock
from contextlib import contextmanager


def blank_profile():
    return dict(name='', email='', phone='', education='', skills=[], experience='',
                projects=[], achievements='', goal='', summary_facts=[])


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = RLock()
        with self.connect() as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS workspaces (id TEXT PRIMARY KEY, state TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS workspace_trash (id TEXT PRIMARY KEY, state TEXT NOT NULL)')

    def trash_list(self):
        with self.connect() as connection:
            rows = connection.execute('SELECT state FROM workspace_trash ORDER BY rowid DESC').fetchall()
        return [dict(id=s['id'], label=s['label']) for (raw,) in rows for s in [json.loads(raw)]]

    def move_to_trash(self, workspace_id, revision):
        with self.lock, self.connect() as connection:
            row = connection.execute('SELECT state FROM workspaces WHERE id=?', (workspace_id,)).fetchone()
            if not row:
                raise ValueError('Workspace not found.')
            state = json.loads(row[0])
            if state['revision'] != revision:
                raise ValueError('Profile changed. Reload before removing this workspace.')
            connection.execute('INSERT INTO workspace_trash VALUES (?, ?)', (workspace_id, row[0]))
            connection.execute('DELETE FROM workspaces WHERE id=?', (workspace_id,))
        return {'removed': workspace_id}

    def restore_workspace(self, workspace_id):
        with self.lock, self.connect() as connection:
            row = connection.execute('SELECT state FROM workspace_trash WHERE id=?', (workspace_id,)).fetchone()
            if not row:
                raise ValueError('Removed workspace not found.')
            connection.execute('INSERT INTO workspaces VALUES (?, ?)', (workspace_id, row[0]))
            connection.execute('DELETE FROM workspace_trash WHERE id=?', (workspace_id,))
        return json.loads(row[0])

    def purge_trash(self):
        """Permanently delete only workspaces already moved to trash."""
        with self.lock, self.connect() as connection:
            count = connection.execute('SELECT COUNT(*) FROM workspace_trash').fetchone()[0]
            connection.execute('DELETE FROM workspace_trash')
        return {'deleted': count}

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=20)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, label):
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 100:
            raise ValueError('Enter a workspace name (1–100 characters).')
        state = dict(id=uuid.uuid4().hex, label=label.strip(), profile=blank_profile(),
                     revision=0, confirmed_revision=None, confirmed_profile=None,
                     messages=[], trace=[], audit_runs=[], retrieval=None, draft=None, versions=[],
                     undo=None, stop_reason=None, cv_messages=[], cv_trace=[], cv_stop_reason=None)
        self.save(state)
        return state

    def list(self):
        with self.connect() as connection:
            rows = connection.execute('SELECT state FROM workspaces ORDER BY rowid').fetchall()
        return [dict(id=s['id'], label=s['label']) for (raw,) in rows for s in [json.loads(raw)]]

    def get(self, workspace_id):
        with self.connect() as connection:
            row = connection.execute('SELECT state FROM workspaces WHERE id=?', (workspace_id,)).fetchone()
        if not row:
            raise ValueError('Workspace not found.')
        return json.loads(row[0])

    def save(self, state):
        with self.connect() as connection:
            connection.execute('INSERT INTO workspaces VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET state=excluded.state',
                               (state['id'], json.dumps(state, ensure_ascii=False)))


def validate_profile(profile):
    if not set(blank_profile()).issubset(profile) or set(profile) - set(blank_profile()) - {'location', 'linkedin', 'github', 'portfolio'}:
        raise ValueError('Profile fields do not match the supported schema.')
    for field, value in profile.items():
        if field in ('skills', 'summary_facts'):
            if not isinstance(value, list) or len(value) > 80 or any(not isinstance(v, str) or not v.strip() or len(v) > 2500 for v in value):
                raise ValueError(f'{field} must contain nonempty text entries.')
        elif field == 'projects':
            if not isinstance(value, list) or len(value) > 20:
                raise ValueError('Projects must be a list of up to 20 projects.')
            for project in value:
                if not isinstance(project, dict) or set(project) != {'title', 'description', 'technologies'} or any(not isinstance(v, str) or len(v) > 5000 for v in project.values()):
                    raise ValueError('Each project needs title, description and technologies text.')
        elif not isinstance(value, str) or len(value) > 10000:
            raise ValueError(f'{field} must be text, up to 10000 characters.')


def missing_fields(profile):
    required = ['name', 'email', 'phone', 'education', 'skills', 'projects', 'experience', 'achievements', 'goal']
    missing = [key for key in required if not profile.get(key) or isinstance(profile[key], str) and not profile[key].strip()]
    if profile['email'] and ('@' not in profile['email'] or '.' not in profile['email'].split('@')[-1]):
        missing.append('valid email')
    if profile['phone'] and len(re.sub(r'\D', '', profile['phone'])) < 6:
        missing.append('valid phone number')
    if any(not p['title'].strip() or not p['description'].strip() for p in profile['projects']):
        missing.append('project title and contribution')
    for field, title in (('education', 'Degree'), ('experience', 'Role')):
        if any(entry.startswith(title + ': ') and not entry.split('\n')[0].split(':', 1)[1].strip()
               for entry in profile[field].split('\n\n')):
            missing.append(field + ' entry title')
    return missing


def update_profile(state, patch):
    if not isinstance(patch, dict) or not patch or set(patch) - set(blank_profile()) - {'location', 'linkedin', 'github', 'portfolio'}:
        raise ValueError('Unknown or empty profile update.')
    profile = {**state['profile'], **patch}
    validate_profile(profile)
    if profile != state['profile']:
        state['profile_undo'] = deepcopy(state['profile'])
        state['profile'] = profile
        state['revision'] += 1
        state['confirmed_revision'] = None
        state['retrieval'] = None
    return {'revision': state['revision'], 'missing_fields': missing_fields(profile), 'confirmation_required': True}


def require_confirmed(state):
    if state.get('pending_profile'):
        raise ValueError('Accept or dismiss the proposed profile changes first.')
    if state['confirmed_revision'] != state['revision'] or state['confirmed_profile'] is None:
        raise ValueError('Review and explicitly confirm the current profile first.')

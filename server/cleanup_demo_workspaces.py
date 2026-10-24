"""Explicit, recoverable cleanup of local verification fixtures; never run at startup."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3

from .store import Store


VERIFICATION_LABEL = re.compile(r'^Showcase — synthetic live verification \d{8}T\d{6}Z$')


def removable_reason(state):
    """Only known labelled fixtures and a completely untouched blank starter qualify."""
    if VERIFICATION_LABEL.fullmatch(state.get('label', '')) and state['profile'].get('name') == 'Avery Morgan':
        return 'labelled synthetic verification fixture'
    if (state.get('label') == 'New CV workspace' and state.get('revision') == 0
            and not any(state['profile'].values()) and state.get('confirmed_revision') is None
            and not any(state.get(key) for key in ('draft', 'versions', 'messages', 'trace', 'cv_messages',
                                                 'cv_trace', 'pending_profile', 'retrieval', 'confirmed_profile'))):
        return 'untouched empty starter'
    return None


def candidates(store):
    result = []
    with store.connect() as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        portfolio_workspaces = {row[0] for row in connection.execute('SELECT workspace FROM portfolios')} if 'portfolios' in tables else set()
    for entry in store.list():
        state = store.get(entry['id'])
        reason = removable_reason(state)
        if reason == 'untouched empty starter' and entry['id'] in portfolio_workspaces:
            continue
        if reason:
            result.append(dict(id=state['id'], label=state['label'], revision=state['revision'], reason=reason))
    return result


def cleanup(store, *, apply=False):
    selected = candidates(store)
    if not apply or not selected:
        return dict(selected=selected, removed=[], backup=None)
    # A consistent private backup precedes recoverable application-level removals.
    directory = store.path.resolve().parent / 'maintenance'
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = directory / f'before-demo-cleanup-{stamp}.sqlite3'
    with closing(sqlite3.connect(store.path)) as source, closing(sqlite3.connect(backup)) as target:
        source.backup(target)
    removed = []
    for entry in selected:
        # Revalidate inside the write transaction, not only in the earlier
        # preview: another process may have opened a portfolio on a blank starter.
        with store.lock, store.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT state FROM workspaces WHERE id=?', (entry['id'],)).fetchone()
            current = json.loads(row[0]) if row else None
            if not current or current['revision'] != entry['revision'] or removable_reason(current) != entry['reason']:
                raise ValueError('Workspace changed during cleanup; reload before continuing.')
            if entry['reason'] == 'untouched empty starter':
                tables = {item[0] for item in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'portfolios' in tables and connection.execute('SELECT 1 FROM portfolios WHERE workspace=?', (entry['id'],)).fetchone():
                    raise ValueError('The empty starter gained a portfolio; no removal was performed for it.')
            connection.execute('INSERT INTO workspace_trash VALUES (?, ?)', (entry['id'], row[0]))
            connection.execute('DELETE FROM workspaces WHERE id=?', (entry['id'],))
        removed.append(entry['id'])
    return dict(selected=selected, removed=removed, backup=str(backup))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-user-request', action='store_true')
    args = parser.parse_args()
    store = Store(Path(__file__).resolve().parents[1] / 'runtime' / 'proofcv.sqlite3')
    result = cleanup(store, apply=args.apply_user_request)
    for entry in result['selected']:
        print(f"{entry['id']} | {entry['label']} | {entry['reason']}")
    if result['removed']:
        print(f"Moved {len(result['removed'])} workspaces to Removed workspaces; all remain restorable.")
        print('Private SQLite backup:', result['backup'])
    else:
        print('No workspaces changed.' if args.apply_user_request else 'Preview only. Use --apply-user-request to move these fixtures to Removed workspaces.')


if __name__ == '__main__':
    main()

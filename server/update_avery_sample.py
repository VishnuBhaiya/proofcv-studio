"""Explicit, additive update for an existing labelled Avery demo; no model calls."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from .seed_labelled_sample import LABEL, _profile
from .store import Store, update_profile


def update_existing(store):
    """Add only SolarVision, preserving workspace ID, edits, chats and CV history.

    This is not run on startup. Existing confirmation becomes stale and the user
    must review and confirm the new facts in My profile before using them.
    """
    with store.lock:
        matches = [w for w in store.list() if w['label'] == LABEL]
        if len(matches) != 1:
            raise ValueError('Expected one labelled Avery sample. Create it first or resolve duplicate labels.')
        state = store.get(matches[0]['id'])
        if state['profile']['name'] != 'Avery Morgan':
            raise ValueError('The labelled workspace no longer belongs to the fictional Avery demo.')
        if state.get('pending_profile') or state.get('pending_cv'):
            raise ValueError('Review pending profile/CV proposals before updating the demo.')
        solar = next(p for p in _profile()['projects'] if p['title'] == 'SolarVision')
        existing = [p for p in state['profile']['projects'] if p['title'].strip().casefold() == 'solarvision']
        if existing:
            if existing != [solar]:
                raise ValueError('SolarVision already has different content. Review it manually; nothing was overwritten.')
            return dict(workspace_id=state['id'], changed=False, review_required=state['confirmed_revision'] != state['revision'])
        update_profile(state, {'projects': state['profile']['projects'] + [deepcopy(solar)]})
        store.save(state)
        return dict(workspace_id=state['id'], changed=True, review_required=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Explicitly add SolarVision to the existing labelled demo.')
    args = parser.parse_args()
    if not args.apply:
        parser.error('No changes made. Use --apply after reviewing the README instructions.')
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(update_existing(Store(root / 'runtime' / 'proofcv.sqlite3')), indent=2))


if __name__ == '__main__':
    main()

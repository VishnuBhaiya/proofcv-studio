"""HTTP entry point for the Interview Coach module."""

ROUNDS = ['self_introduction', 'behavioural', 'technical', 'motivation_fit']


def readiness(state):
    """The core facts the coach needs: a confirmed profile and the user's matched jobs."""
    confirmed = state.get('confirmed_revision') is not None and state['confirmed_revision'] == state['revision']
    results = (state.get('retrieval') or {}).get('results') or []
    draft = state.get('draft')
    return {
        'workspace_id': state['id'],
        'profile_confirmed': confirmed,
        'matched_jobs': [{'document_id': r['document_id'], 'title': r['title'], 'score': r['score']} for r in results],
        'target_job': {'document_id': draft['job']['document_id'], 'title': draft['job']['title']} if draft else None,
        'rounds': ROUNDS,
    }


def handle_get(service, path):
    """GET /api/interview/<workspace_id>/status"""
    parts = path.strip('/').split('/')
    if len(parts) == 4 and parts[3] == 'status':
        return readiness(service.store.get(parts[2]))
    raise ValueError('Endpoint not found.')

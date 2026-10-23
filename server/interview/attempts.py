"""Practice attempts: what needs work in an answer, and whether a retry improved.

Each attempt's scores and transcript are kept in the module's own local SQLite
file (runtime/interview.sqlite3, never committed). Audio is never stored.
"""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

GOOD_WPM = (120, 160)
KEY_POINTS_TARGET = 0.7
FILLER_LIMIT = 6
SHORT_RATIO = 0.6
# Metric: (label, better direction, smallest change that counts).
METRICS = {
    'key_points': ('Key points covered', 'higher', 0.1),
    'star_parts': ('STAR parts present', 'higher', 1),
    'flags': ('Claims not backed by your profile', 'lower', 1),
    'fillers_per_minute': ('Filler words per minute', 'lower', 1.0),
    'long_pauses': ('Long pauses', 'lower', 1),
    'pace_gap': ('Pace off target (words/min)', 'lower', 10),
    'length_gap': ('Length off target', 'lower', 15),
}


def summarise(response):
    """The numbers that describe one attempt, taken from the answer response."""
    d = response['delivery']
    wpm = d['words_per_minute']
    summary = {'words_per_minute': wpm, 'fillers_per_minute': d['fillers_per_minute'], 'long_pauses': d['long_pauses'],
               'pace_gap': max(GOOD_WPM[0] - wpm, wpm - GOOD_WPM[1], 0) if wpm else None}
    if response.get('target_seconds'):
        summary['length_gap'] = round(abs(d['speaking_seconds'] / response['target_seconds'] - 1) * 100)
        summary['length_ratio'] = round(d['speaking_seconds'] / response['target_seconds'], 2)
    if 'star' in response:
        summary['star_parts'] = sum(response['star']['present'].values())
    if 'content' in response:
        summary['key_points'] = response['content']['score']
    if 'fact_check' in response:
        summary['flags'] = sum(len(c['flags']) for c in response['fact_check']['claims'])
    return summary


def needs_work(summary):
    """Short reasons this attempt is not yet strong; empty when it is."""
    reasons = []
    if summary.get('star_parts', 4) < 4:
        reasons.append(f"Only {summary['star_parts']} of the 4 STAR parts {'is' if summary['star_parts'] == 1 else 'are'} clear.")
    if summary.get('key_points', 1) < KEY_POINTS_TARGET:
        reasons.append(f"Covered {round(summary['key_points'] * 100)}% of the key points.")
    if summary.get('flags'):
        reasons.append(f"{summary['flags']} detail{'s' if summary['flags'] > 1 else ''} not backed by your confirmed profile.")
    if summary['fillers_per_minute'] > FILLER_LIMIT:
        reasons.append(f"{summary['fillers_per_minute']} filler words per minute.")
    if summary.get('length_ratio') is not None and summary['length_ratio'] < SHORT_RATIO:
        reasons.append('Much shorter than the target length.')
    if not summary['words_per_minute']:
        reasons.append('No speech was detected.')
    return reasons


def compare(previous, current):
    """What changed since the previous attempt, metric by metric."""
    changes = []
    for key, (label, direction, step) in METRICS.items():
        before, after = previous.get(key), current.get(key)
        if before is None or after is None:
            continue
        delta = after - before if direction == 'higher' else before - after
        changes.append({'metric': key, 'label': label, 'before': before, 'after': after,
                        'direction': 'better' if delta >= step else 'worse' if delta <= -step else 'same'})
    return changes


class AttemptStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        with self.connect() as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL, '
                               'question_id TEXT NOT NULL, created_at TEXT NOT NULL, transcript TEXT NOT NULL, summary TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def history(self, workspace_id, question_id):
        with self.connect() as connection:
            rows = connection.execute('SELECT created_at, transcript, summary FROM attempts WHERE workspace_id=? AND question_id=? ORDER BY id',
                                      (workspace_id, question_id)).fetchall()
        return [{'attempt': i + 1, 'created_at': at, 'transcript': text, 'summary': json.loads(summary)} for i, (at, text, summary) in enumerate(rows)]

    def record(self, workspace_id, question_id, transcript, summary):
        """Save an attempt and return its progress compared with the previous one."""
        with self.lock:
            earlier = self.history(workspace_id, question_id)
            with self.connect() as connection:
                connection.execute('INSERT INTO attempts (workspace_id, question_id, created_at, transcript, summary) VALUES (?, ?, ?, ?, ?)',
                                   (workspace_id, question_id, datetime.now(timezone.utc).isoformat(timespec='seconds'), transcript, json.dumps(summary)))
        previous = earlier[-1]['summary'] if earlier else None
        return {'attempt': len(earlier) + 1, 'needs_work': needs_work(summary),
                'changes': compare(previous, summary) if previous else [], 'summary': summary}

"""Practice attempts: what needs work in an answer, and whether a retry improved.

Each attempt's scores and transcript are kept in the module's own local SQLite
file (runtime/interview.sqlite3, never committed). Audio is never stored.
"""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

GOOD_WPM = (120, 160)
KEY_POINTS_TARGET = 0.7
FILLER_LIMIT = 6
SHORT_RATIO = 0.6
UNSURE_SHARE = 0.15  # Matches speech.UNSURE_SHARE (kept here so attempts need no audio libraries).
# Metric: (label, better direction, smallest change that counts).
METRICS = {
    'key_points': ('Key points covered', 'higher', 0.1),
    'star_parts': ('STAR parts present', 'higher', 1),
    'flags': ('Flagged details', 'lower', 1),
    'honesty': ('Backed by your profile', 'higher', 10),
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
    if response.get('recognition'):
        summary['unsure_share'] = response['recognition']['unsure_share']
    if response.get('target_seconds'):
        summary['length_gap'] = round(abs(d['speaking_seconds'] / response['target_seconds'] - 1) * 100)
        summary['length_ratio'] = round(d['speaking_seconds'] / response['target_seconds'], 2)
    if 'star' in response:
        summary['star_parts'] = sum(response['star']['present'].values())
    if 'content' in response:
        summary['key_points'] = response['content']['score']
    if 'fact_check' in response:
        claims = response['fact_check']['claims']
        summary['flags'] = sum(len(c['flags']) for c in claims)
        summary['unmatched'] = sum(c['status'] == 'unmatched' for c in claims)
        summary['honesty'] = response['fact_check'].get('score')  # None when nothing was claimed.
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
    if summary.get('unmatched'):
        n = summary['unmatched']
        reasons.append(f"{n} thing{'s' if n > 1 else ''} you said about yourself {'are' if n > 1 else 'is'} not in your confirmed profile.")
    if summary['fillers_per_minute'] > FILLER_LIMIT:
        reasons.append(f"{summary['fillers_per_minute']} filler words per minute.")
    if summary.get('length_ratio') is not None and summary['length_ratio'] < SHORT_RATIO:
        reasons.append('Much shorter than the target length.')
    if not summary['words_per_minute']:
        reasons.append('No speech was detected.')
    if summary.get('unsure_share', 0) > UNSURE_SHARE:
        reasons.append(f"Speech recognition was unsure about {round(summary['unsure_share'] * 100)}% of the words, so this score is not reliable.")
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
            connection.execute('CREATE TABLE IF NOT EXISTS mock_sessions (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, created_at TEXT NOT NULL, '
                               'job TEXT NOT NULL, questions TEXT NOT NULL, answers TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS diagnostics (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, job TEXT NOT NULL, '
                               'created_at TEXT NOT NULL, questions TEXT NOT NULL, answers TEXT NOT NULL, finished_at TEXT)')
            connection.execute('CREATE TABLE IF NOT EXISTS coach_setup (workspace_id TEXT PRIMARY KEY, setup TEXT NOT NULL, saved_at TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS plan_ticks (workspace_id TEXT NOT NULL, job_id TEXT NOT NULL, day TEXT NOT NULL, '
                               'task TEXT NOT NULL, PRIMARY KEY (workspace_id, job_id, day, task))')

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def history(self, workspace_id, question_id):
        with self.connect() as connection:
            rows = connection.execute('SELECT created_at, transcript, summary FROM attempts WHERE workspace_id=? AND question_id=? ORDER BY id',
                                      (workspace_id, question_id)).fetchall()
        return [{'attempt': i + 1, 'created_at': at, 'transcript': text, 'summary': json.loads(summary)} for i, (at, text, summary) in enumerate(rows)]

    def overview(self, workspace_id):
        """For every practised question: how many attempts, and whether the latest one still needs work."""
        with self.connect() as connection:
            rows = connection.execute('SELECT question_id, COUNT(*), MAX(id) FROM attempts WHERE workspace_id=? GROUP BY question_id', (workspace_id,)).fetchall()
            latest = {qid: json.loads(connection.execute('SELECT summary FROM attempts WHERE id=?', (last,)).fetchone()[0]) for qid, _, last in rows}
        return {qid: {'attempts': count, 'needs_work': needs_work(latest[qid])} for qid, count, _ in rows}

    def record(self, workspace_id, question_id, transcript, summary):
        """Save an attempt and return its progress compared with the previous one."""
        with self.lock:
            earlier = self.history(workspace_id, question_id)
            with self.connect() as connection:
                attempt_id = connection.execute('INSERT INTO attempts (workspace_id, question_id, created_at, transcript, summary) VALUES (?, ?, ?, ?, ?)',
                                                (workspace_id, question_id, datetime.now(timezone.utc).isoformat(timespec='seconds'), transcript, json.dumps(summary))).lastrowid
        previous = earlier[-1]['summary'] if earlier else None
        return {'id': attempt_id, 'attempt': len(earlier) + 1, 'needs_work': needs_work(summary),
                'changes': compare(previous, summary) if previous else [], 'summary': summary}

    def all(self, workspace_id):
        """Every attempt in a workspace, oldest first."""
        with self.connect() as connection:
            rows = connection.execute('SELECT id, question_id, created_at, transcript, summary FROM attempts WHERE workspace_id=? ORDER BY id', (workspace_id,)).fetchall()
        return [{'id': i, 'question_id': q, 'created_at': at, 'transcript': t, 'summary': json.loads(s)} for i, q, at, t, s in rows]

    def get(self, workspace_id, attempt_ids):
        """Attempts by id for one workspace, keyed by id."""
        if not attempt_ids:
            return {}
        marks = ','.join('?' * len(attempt_ids))
        with self.connect() as connection:
            rows = connection.execute(f'SELECT id, question_id, created_at, transcript, summary FROM attempts WHERE workspace_id=? AND id IN ({marks})',
                                      (workspace_id, *attempt_ids)).fetchall()
        return {i: {'id': i, 'question_id': q, 'created_at': at, 'transcript': t, 'summary': json.loads(s)} for i, q, at, t, s in rows}

    def create_session(self, workspace_id, job, questions):
        session_id = uuid.uuid4().hex
        with self.connect() as connection:
            connection.execute('INSERT INTO mock_sessions (id, workspace_id, created_at, job, questions, answers) VALUES (?, ?, ?, ?, ?, ?)',
                               (session_id, workspace_id, datetime.now(timezone.utc).isoformat(timespec='seconds'), json.dumps(job), json.dumps(questions), '{}'))
        return self.session(workspace_id, session_id)

    def session(self, workspace_id, session_id):
        with self.connect() as connection:
            row = connection.execute('SELECT id, created_at, job, questions, answers FROM mock_sessions WHERE id=? AND workspace_id=?',
                                     (session_id, workspace_id)).fetchone()
        if not row:
            raise ValueError('Mock interview not found.')
        return {'id': row[0], 'created_at': row[1], 'job': json.loads(row[2]), 'questions': json.loads(row[3]), 'answers': json.loads(row[4])}

    def sessions(self, workspace_id):
        """All mock interviews for a workspace, newest first."""
        with self.connect() as connection:
            ids = [row[0] for row in connection.execute('SELECT id FROM mock_sessions WHERE workspace_id=? ORDER BY created_at DESC', (workspace_id,))]
        return [self.session(workspace_id, session_id) for session_id in ids]

    def link_answer(self, workspace_id, session_id, position, attempt_id, follow_up_question=None):
        """Record that question number `position` of a mock interview (or its follow-up) was answered by this attempt (latest wins)."""
        with self.lock:
            current = self.session(workspace_id, session_id)
            if not 0 <= position < len(current['questions']):
                raise ValueError('Question is not part of this mock interview.')
            if follow_up_question:
                current['answers'][f'{position}f'] = {'id': attempt_id, 'question': follow_up_question}
            else:
                current['answers'][str(position)] = attempt_id
            with self.connect() as connection:
                connection.execute('UPDATE mock_sessions SET answers=? WHERE id=?', (json.dumps(current['answers']), session_id))

    def plan_ticks(self, workspace_id, job_id):
        """Plan tasks the user marked done, as {(iso day, task key)}."""
        with self.connect() as connection:
            rows = connection.execute('SELECT day, task FROM plan_ticks WHERE workspace_id=? AND job_id=?', (workspace_id, job_id)).fetchall()
        return set(rows)

    def tick(self, workspace_id, job_id, day, task, done):
        with self.lock, self.connect() as connection:
            if done:
                connection.execute('INSERT OR IGNORE INTO plan_ticks (workspace_id, job_id, day, task) VALUES (?, ?, ?, ?)', (workspace_id, job_id, day, task))
            else:
                connection.execute('DELETE FROM plan_ticks WHERE workspace_id=? AND job_id=? AND day=? AND task=?', (workspace_id, job_id, day, task))

    def setup(self, workspace_id):
        """The saved Interview Coach setup for a workspace, or None before the user has done it."""
        with self.connect() as connection:
            row = connection.execute('SELECT setup, saved_at FROM coach_setup WHERE workspace_id=?', (workspace_id,)).fetchone()
        return {**json.loads(row[0]), 'saved_at': row[1]} if row else None

    def save_setup(self, workspace_id, setup):
        with self.lock, self.connect() as connection:
            connection.execute('INSERT OR REPLACE INTO coach_setup (workspace_id, setup, saved_at) VALUES (?, ?, ?)',
                               (workspace_id, json.dumps(setup), datetime.now(timezone.utc).isoformat(timespec='seconds')))

    def create_diagnostic(self, workspace_id, job, questions):
        """A new skill check; job holds the job's id and title plus the skills the user chose to learn."""
        diagnostic_id = uuid.uuid4().hex
        with self.connect() as connection:
            connection.execute('INSERT INTO diagnostics (id, workspace_id, job, created_at, questions, answers) VALUES (?, ?, ?, ?, ?, ?)',
                               (diagnostic_id, workspace_id, json.dumps(job), datetime.now(timezone.utc).isoformat(timespec='seconds'), json.dumps(questions), '{}'))
        return self.diagnostic(workspace_id, diagnostic_id)

    def diagnostic(self, workspace_id, diagnostic_id):
        with self.connect() as connection:
            row = connection.execute('SELECT id, job, created_at, questions, answers, finished_at FROM diagnostics WHERE id=? AND workspace_id=?',
                                     (diagnostic_id, workspace_id)).fetchone()
        if not row:
            raise ValueError('Skill check not found.')
        return {'id': row[0], 'job': json.loads(row[1]), 'created_at': row[2], 'questions': json.loads(row[3]), 'answers': json.loads(row[4]), 'finished_at': row[5]}

    def latest_diagnostic(self, workspace_id, job_id):
        """The most recent skill check for a job, finished or not; None if there is none."""
        with self.connect() as connection:
            rows = connection.execute('SELECT id, job FROM diagnostics WHERE workspace_id=? ORDER BY created_at DESC, rowid DESC', (workspace_id,)).fetchall()
        match = next((i for i, job in rows if json.loads(job)['document_id'] == job_id), None)
        return self.diagnostic(workspace_id, match) if match else None

    def link_diagnostic_answer(self, workspace_id, diagnostic_id, position, attempt_id, covered, partial, missed):
        """Record the answer to question number position of a skill check (latest wins), with its key points."""
        with self.lock:
            current = self.diagnostic(workspace_id, diagnostic_id)
            if current['finished_at']:
                raise ValueError('This skill check is finished. Start a new one to answer again.')
            if not 0 <= position < len(current['questions']):
                raise ValueError('Question is not part of this skill check.')
            current['answers'][str(position)] = {'id': attempt_id, 'covered': covered, 'partial': partial, 'missed': missed}
            with self.connect() as connection:
                connection.execute('UPDATE diagnostics SET answers=? WHERE id=?', (json.dumps(current['answers']), diagnostic_id))

    def finish_diagnostic(self, workspace_id, diagnostic_id):
        self.diagnostic(workspace_id, diagnostic_id)
        with self.connect() as connection:
            connection.execute('UPDATE diagnostics SET finished_at=? WHERE id=? AND finished_at IS NULL',
                               (datetime.now(timezone.utc).isoformat(timespec='seconds'), diagnostic_id))
        return self.diagnostic(workspace_id, diagnostic_id)

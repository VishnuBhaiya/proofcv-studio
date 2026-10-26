"""Loading the presentation demo into a fresh install's Avery workspace."""
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from ..seed_labelled_sample import LABEL
from ..store import Store
from .attempts import AttemptStore
from .load_demo import DEMO_PATH, absolute, load, local_zone, relative

TODAY = date(2026, 11, 20)


class LoadDemoTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store_path, self.coach_path = Path(folder.name) / 'proofcv.sqlite3', Path(folder.name) / 'interview.sqlite3'
        self.store = Store(self.store_path)
        self.avery = self.store.create(LABEL)
        self.avery.update(confirmed_revision=0, confirmed_profile=self.avery['profile'])
        self.store.save(self.avery)
        self.demo = json.loads(DEMO_PATH.read_text(encoding='utf-8'))

    def rows(self, sql):
        with AttemptStore(self.coach_path).connect() as connection:
            return connection.execute(sql, (self.avery['id'],)).fetchall()

    def test_loads_every_part_with_dates_relative_to_today(self):
        result = load(self.store_path, self.coach_path, self.demo, today=TODAY)
        self.assertEqual(result['workspace'], LABEL)
        self.assertEqual(result['interview_date'], (TODAY + timedelta(self.demo['setup']['interview_in_days'])).isoformat())
        self.assertEqual(len(self.rows('SELECT id FROM attempts WHERE workspace_id=?')), len(self.demo['attempts']))
        days = {(datetime.fromisoformat(at).astimezone(local_zone()).date() - TODAY).days for (at,) in self.rows('SELECT created_at FROM attempts WHERE workspace_id=?')}
        self.assertEqual(days, {a['created_at']['days'] for a in self.demo['attempts']})
        ticks = {(date.fromisoformat(d) - TODAY).days for (d,) in self.rows('SELECT day FROM plan_ticks WHERE workspace_id=?')}
        self.assertEqual(ticks, {t['days'] for t in self.demo['ticks']})

    def test_session_answers_point_at_the_loaded_attempts(self):
        load(self.store_path, self.coach_path, self.demo, today=TODAY)
        attempts = {i: q for i, q in self.rows('SELECT id, question_id FROM attempts WHERE workspace_id=?')}
        (questions, answers), = self.rows('SELECT questions, answers FROM diagnostics WHERE workspace_id=?')
        for key, value in json.loads(answers).items():
            self.assertEqual(attempts[value['id']], json.loads(questions)[int(key)]['id'])
        (answers,), = self.rows('SELECT answers FROM mock_sessions WHERE workspace_id=?')
        ids = [v['id'] if isinstance(v, dict) else v for v in json.loads(answers).values()]
        self.assertTrue(ids and all(i in attempts for i in ids))

    def test_existing_coach_data_needs_replace_and_is_backed_up(self):
        load(self.store_path, self.coach_path, self.demo, today=TODAY)
        with self.assertRaisesRegex(ValueError, '--replace'):
            load(self.store_path, self.coach_path, self.demo, today=TODAY)
        result = load(self.store_path, self.coach_path, self.demo, replace=True, today=TODAY)
        self.assertTrue(Path(result['backup']).exists())
        self.assertEqual(len(self.rows('SELECT id FROM attempts WHERE workspace_id=?')), len(self.demo['attempts']))
        self.assertEqual(len(self.rows('SELECT id FROM diagnostics WHERE workspace_id=?')), 1)

    def test_unconfirmed_profile_is_refused(self):
        self.avery.update(confirmed_revision=None, confirmed_profile=None)
        self.store.save(self.avery)
        with self.assertRaisesRegex(ValueError, 'Confirm the profile'):
            load(self.store_path, self.coach_path, self.demo, today=TODAY)

    def test_relative_times_round_trip(self):
        when = {'days': -3, 'time': '11:30:00'}
        self.assertEqual(relative(absolute(when, TODAY), TODAY), when)


if __name__ == '__main__':
    unittest.main()

"""Tests for CPM scheduler."""
from datetime import date, timedelta

from p6_schedule.cpm_scheduler import schedule


def _task(name: str, dur: int, task_type: str = 'Task',
          constraint_type: str = '', constraint_date: str = '') -> dict:
    return {
        'task_name': name, 'task_type': task_type, 'duration_days': dur,
        'wbs_path': 'Root', 'constraint_type': constraint_type,
        'constraint_date': constraint_date,
    }


class TestForwardPass:
    def test_simple_chain(self):
        tasks = {
            'A': _task('Start', 0, 'Milestone'),
            'B': _task('Task B', 5),
            'C': _task('Task C', 3),
        }
        rels = [('B', 'A', 'FS', 0), ('C', 'B', 'FS', 0)]
        result = schedule(tasks, rels, '2026-01-01')

        r = result['tasks']
        assert r['A']['display_start'] == date(2026, 1, 1)
        assert r['B']['display_start'] == date(2026, 1, 2)  # milestone→task = next day
        assert r['B']['display_end'] == date(2026, 1, 6)
        assert r['C']['display_start'] == date(2026, 1, 7)  # task→task = next day
        assert r['C']['display_end'] == date(2026, 1, 9)

    def test_milestone_to_task_fs0_next_day(self):
        tasks = {
            'MS': _task('Milestone', 0, 'Milestone'),
            'T': _task('Task', 5),
        }
        rels = [('T', 'MS', 'FS', 0)]
        result = schedule(tasks, rels, '2026-01-01')

        assert result['tasks']['T']['display_start'] == date(2026, 1, 2)
        assert result['tasks']['T']['display_end'] == date(2026, 1, 6)

    def test_task_to_task_fs0_next_day(self):
        tasks = {
            'A': _task('Task A', 3),
            'B': _task('Task B', 2),
        }
        rels = [('B', 'A', 'FS', 0)]
        result = schedule(tasks, rels, '2026-01-01')

        assert result['tasks']['A']['display_end'] == date(2026, 1, 3)
        assert result['tasks']['B']['display_start'] == date(2026, 1, 4)

    def test_fs_with_lag(self):
        tasks = {
            'A': _task('Task A', 3),
            'B': _task('Task B', 2),
        }
        rels = [('B', 'A', 'FS', 5)]
        result = schedule(tasks, rels, '2026-01-01')

        assert result['tasks']['A']['display_end'] == date(2026, 1, 3)
        assert result['tasks']['B']['display_start'] == date(2026, 1, 9)

    def test_ss_with_lag(self):
        tasks = {
            'A': _task('Task A', 10),
            'B': _task('Task B', 5),
        }
        rels = [('B', 'A', 'SS', 3)]
        result = schedule(tasks, rels, '2026-01-01')

        assert result['tasks']['A']['display_start'] == date(2026, 1, 1)
        assert result['tasks']['B']['display_start'] == date(2026, 1, 4)

    def test_ss_milestone_to_task_adds_one(self):
        tasks = {
            'MS': _task('Milestone', 0, 'Milestone'),
            'T': _task('Task', 5),
        }
        rels = [('T', 'MS', 'SS', 0)]
        result = schedule(tasks, rels, '2026-01-01')

        assert result['tasks']['MS']['display_start'] == date(2026, 1, 1)
        assert result['tasks']['T']['display_start'] == date(2026, 1, 2)  # +1 day

    def test_multiple_predecessors(self):
        tasks = {
            'A': _task('Task A', 3),
            'B': _task('Task B', 5),
            'C': _task('Task C', 2),
        }
        rels = [('C', 'A', 'FS', 0), ('C', 'B', 'FS', 0)]
        result = schedule(tasks, rels, '2026-01-01')

        assert result['tasks']['C']['display_start'] == date(2026, 1, 6)

    def test_cs_mso_constraint(self):
        tasks = {
            'A': _task('Start', 0, 'Milestone', 'CS_MSO', '2026-03-15'),
            'B': _task('Task', 5),
        }
        rels = [('B', 'A', 'FS', 0)]
        result = schedule(tasks, rels, '2026-01-01')

        assert result['tasks']['A']['display_start'] == date(2026, 3, 15)
        assert result['tasks']['B']['display_start'] == date(2026, 3, 16)


class TestBackwardPass:
    def test_simple_chain_all_critical(self):
        tasks = {
            'A': _task('Task A', 5),
            'B': _task('Task B', 3),
        }
        rels = [('B', 'A', 'FS', 0)]
        result = schedule(tasks, rels, '2026-01-01')

        assert result['tasks']['A']['total_float'] == 0
        assert result['tasks']['B']['total_float'] == 0
        assert result['tasks']['A']['is_critical']
        assert result['tasks']['B']['is_critical']

    def test_parallel_path_with_float(self):
        tasks = {
            'START': _task('Start', 0, 'Milestone'),
            'A': _task('Long', 10),
            'B': _task('Short', 3),
            'END': _task('End', 0, 'Milestone'),
        }
        rels = [
            ('A', 'START', 'FS', 0), ('END', 'A', 'FS', 0),
            ('B', 'START', 'FS', 0), ('END', 'B', 'FS', 0),
        ]
        result = schedule(tasks, rels, '2026-01-01')

        assert result['tasks']['A']['is_critical']
        assert result['tasks']['A']['total_float'] == 0
        assert not result['tasks']['B']['is_critical']
        assert result['tasks']['B']['total_float'] > 0

    def test_negative_float_with_constraint(self):
        tasks = {
            'A': _task('Long Task', 30),
            'MS': _task('Deadline', 0, 'Milestone', 'CS_MSO', '2026-01-15'),
        }
        rels = [('MS', 'A', 'FS', 0)]
        result = schedule(tasks, rels, '2026-01-01')

        assert result['tasks']['A']['total_float'] < 0


class TestCriticalPath:
    def test_diamond_critical_path(self):
        tasks = {
            'S': _task('Start', 0, 'Milestone'),
            'A': _task('Path A', 5),
            'B': _task('Path B', 10),
            'E': _task('End', 0, 'Milestone'),
        }
        rels = [
            ('A', 'S', 'FS', 0), ('B', 'S', 'FS', 0),
            ('E', 'A', 'FS', 0), ('E', 'B', 'FS', 0),
        ]
        result = schedule(tasks, rels, '2026-01-01')

        assert result['tasks']['B']['is_critical']
        assert not result['tasks']['A']['is_critical']

        paths = result['critical_path']
        assert len(paths) >= 1
        assert 'B' in paths[0]
        assert 'A' not in paths[0]


class TestMilestoneCheck:
    def test_milestones_meet_contract(self):
        tasks = {
            'MS': _task('Start', 0, 'Milestone', 'CS_MSO', '2026-03-01'),
        }
        rels = []
        milestones = {'MS': date(2026, 3, 1)}
        result = schedule(tasks, rels, '2026-01-01', milestones)

        check = result['milestone_check']
        assert check['MS']['status'] == '✅'

    def test_milestones_miss_contract(self):
        tasks = {
            'A': _task('Task', 10),
            'MS': _task('End', 0, 'Milestone'),
        }
        rels = [('MS', 'A', 'FS', 0)]
        milestones = {'MS': date(2026, 1, 5)}
        result = schedule(tasks, rels, '2026-01-01', milestones)

        check = result['milestone_check']
        assert check['MS']['status'] == '❌'

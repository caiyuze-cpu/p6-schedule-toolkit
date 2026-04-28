"""Tests for CPM network validation."""
import pytest

from p6_schedule.validate import validate_network


def _make_task(code: str) -> dict:
    return {
        'task_name': f'Task {code}',
        'task_type': 'Task',
        'duration_days': 5,
        'wbs_path': 'Root',
        'constraint_type': '',
        'constraint_date': '',
        'row': 1,
    }


def _make_tasks(*codes: str) -> dict:
    return {c: _make_task(c) for c in codes}


class TestBasicValidation:
    def test_valid_chain(self, capsys):
        tasks = _make_tasks('A', 'B', 'C')
        rels = [('B', 'A', 'FS', 0), ('C', 'B', 'FS', 0)]
        validate_network(tasks, rels)
        captured = capsys.readouterr()
        assert 'validation passed' in captured.out

    def test_missing_predecessor(self):
        tasks = _make_tasks('A', 'B')
        rels = [('B', 'Z', 'FS', 0)]
        with pytest.raises(ValueError, match='not found'):
            validate_network(tasks, rels)

    def test_invalid_rel_type(self):
        tasks = _make_tasks('A', 'B')
        rels = [('B', 'A', 'XX', 0)]
        with pytest.raises(ValueError, match='Invalid rel_type'):
            validate_network(tasks, rels)

    def test_circular_dependency(self):
        tasks = _make_tasks('A', 'B', 'C')
        rels = [('B', 'A', 'FS', 0), ('C', 'B', 'FS', 0), ('A', 'C', 'FS', 0)]
        with pytest.raises(ValueError, match='Circular dependency'):
            validate_network(tasks, rels)

    def test_self_loop(self):
        tasks = _make_tasks('A')
        rels = [('A', 'A', 'FS', 0)]
        with pytest.raises(ValueError, match='Circular dependency'):
            validate_network(tasks, rels)

    def test_single_task_no_rels(self, capsys):
        tasks = _make_tasks('A')
        rels = []
        validate_network(tasks, rels)
        captured = capsys.readouterr()
        assert 'validation passed' in captured.out


class TestMultipleEndpoints:
    def test_multiple_starts_warning(self, capsys):
        tasks = _make_tasks('A', 'B', 'C')
        rels = [('C', 'A', 'FS', 0)]
        validate_network(tasks, rels)
        captured = capsys.readouterr()
        assert 'Warning' in captured.out
        assert 'start' in captured.out.lower()

    def test_multiple_ends_warning(self, capsys):
        tasks = _make_tasks('A', 'B', 'C')
        rels = [('B', 'A', 'FS', 0)]
        validate_network(tasks, rels)
        captured = capsys.readouterr()
        assert 'Warning' in captured.out
        assert 'end' in captured.out.lower()


class TestRelationshipTypes:
    @pytest.mark.parametrize('rel_type', ['FS', 'SS', 'FF', 'SF'])
    def test_all_valid_rel_types(self, capsys, rel_type):
        tasks = _make_tasks('A', 'B')
        rels = [('B', 'A', rel_type, 0)]
        validate_network(tasks, rels)
        captured = capsys.readouterr()
        assert 'validation passed' in captured.out

    def test_lag_days(self, capsys):
        tasks = _make_tasks('A', 'B')
        rels = [('B', 'A', 'FS', 5)]
        validate_network(tasks, rels)
        captured = capsys.readouterr()
        assert 'validation passed' in captured.out


class TestComplexNetworks:
    def test_diamond_dependency(self, capsys):
        tasks = _make_tasks('A', 'B', 'C', 'D')
        rels = [
            ('B', 'A', 'FS', 0),
            ('C', 'A', 'FS', 0),
            ('D', 'B', 'FS', 0),
            ('D', 'C', 'FS', 0),
        ]
        validate_network(tasks, rels)
        captured = capsys.readouterr()
        assert 'validation passed' in captured.out

    def test_parallel_chains(self, capsys):
        tasks = _make_tasks('START', 'A1', 'A2', 'A3', 'B1', 'B2', 'END')
        rels = [
            ('A1', 'START', 'FS', 0),
            ('A2', 'A1', 'FS', 0),
            ('A3', 'A2', 'FS', 0),
            ('B1', 'START', 'FS', 0),
            ('B2', 'B1', 'FS', 0),
            ('END', 'A3', 'FS', 0),
            ('END', 'B2', 'FS', 0),
        ]
        validate_network(tasks, rels)
        captured = capsys.readouterr()
        assert 'validation passed' in captured.out

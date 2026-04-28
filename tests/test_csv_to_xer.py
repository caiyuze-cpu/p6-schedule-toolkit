"""Tests for CSV to XER conversion."""
import os
import tempfile

import pytest

from p6_schedule.csv_to_xer import parse_csv, build_tasks_and_rels, generate_xer


class TestParseCSV:
    def test_basic_csv(self, tmp_path):
        csv_content = (
            "wbs_path,task_code,task_name,task_type,duration_days,"
            "predecessor_code,rel_type,lag_days,constraint_type,constraint_date\n"
            "Root,A1000,Start Milestone,Milestone,0,,,,\n"
            "Root,P1010,Site Prep,Task,10,A1000,FS,0,,\n"
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')

        rows = parse_csv(str(csv_file))
        assert len(rows) == 2

        assert rows[0]['task_code'] == 'A1000'
        assert rows[0]['task_type'] == 'Milestone'
        assert rows[0]['duration_days'] == 0
        assert rows[0]['pred_code'] == ''

        assert rows[1]['task_code'] == 'P1010'
        assert rows[1]['task_type'] == 'Task'
        assert rows[1]['duration_days'] == 10
        assert rows[1]['pred_code'] == 'A1000'
        assert rows[1]['rel_type'] == 'FS'
        assert rows[1]['lag_days'] == 0

    def test_csv_with_constraints(self, tmp_path):
        csv_content = (
            "wbs_path,task_code,task_name,task_type,duration_days,"
            "predecessor_code,rel_type,lag_days,constraint_type,constraint_date\n"
            "Root,A1000,Start,Milestone,0,,,,CS_MSO,2026-05-20\n"
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')

        rows = parse_csv(str(csv_file))
        assert rows[0]['constraint_type'] == 'CS_MSO'
        assert rows[0]['constraint_date'] == '2026-05-20'

    def test_csv_with_lag(self, tmp_path):
        csv_content = (
            "wbs_path,task_code,task_name,task_type,duration_days,"
            "predecessor_code,rel_type,lag_days,constraint_type,constraint_date\n"
            "Root,B2_F,B2 Foundation,Task,30,B1_F,SS,5,,\n"
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')

        rows = parse_csv(str(csv_file))
        assert rows[0]['lag_days'] == 5
        assert rows[0]['rel_type'] == 'SS'


class TestBuildTasksAndRels:
    def test_deduplicates_tasks(self):
        rows = [
            {'task_code': 'A', 'task_name': 'Task A', 'task_type': 'Task',
             'duration_days': 10, 'wbs_path': 'Root', 'pred_code': '',
             'rel_type': 'FS', 'lag_days': 0, 'constraint_type': '',
             'constraint_date': '', 'row': 1},
            {'task_code': 'A', 'task_name': 'Task A', 'task_type': 'Task',
             'duration_days': 10, 'wbs_path': 'Root', 'pred_code': 'B',
             'rel_type': 'FS', 'lag_days': 0, 'constraint_type': '',
             'constraint_date': '', 'row': 2},
        ]
        tasks, rels = build_tasks_and_rels(rows)
        assert len(tasks) == 1
        assert len(rels) == 1

    def test_inconsistent_task_raises(self):
        rows = [
            {'task_code': 'A', 'task_name': 'Task A', 'task_type': 'Task',
             'duration_days': 10, 'wbs_path': 'Root', 'pred_code': '',
             'rel_type': 'FS', 'lag_days': 0, 'constraint_type': '',
             'constraint_date': '', 'row': 1},
            {'task_code': 'A', 'task_name': 'Different Name', 'task_type': 'Task',
             'duration_days': 10, 'wbs_path': 'Root', 'pred_code': 'B',
             'rel_type': 'FS', 'lag_days': 0, 'constraint_type': '',
             'constraint_date': '', 'row': 2},
        ]
        with pytest.raises(ValueError, match='inconsistent'):
            build_tasks_and_rels(rows)


class TestGenerateXER:
    def test_generates_valid_xer(self):
        tasks = {
            'A1000': {
                'task_name': 'Start', 'task_type': 'Milestone', 'duration_days': 0,
                'wbs_path': 'Root', 'constraint_type': '', 'constraint_date': '', 'row': 1,
            },
            'P1010': {
                'task_name': 'Site Prep', 'task_type': 'Task', 'duration_days': 10,
                'wbs_path': 'Root', 'constraint_type': '', 'constraint_date': '', 'row': 2,
            },
        }
        rels = [('P1010', 'A1000', 'FS', 0)]

        xer = generate_xer(tasks, rels, 'Test Project', '2026-05-20')

        assert 'ERMHDR' in xer
        assert '%T\tOBS' in xer
        assert '%T\tPROJECT' in xer
        assert '%T\tCALENDAR' in xer
        assert '%T\tSCHEDOPTIONS' in xer
        assert '%T\tPROJWBS' in xer
        assert '%T\tTASK' in xer
        assert '%T\tTASKPRED' in xer
        assert 'TT_FinMile' in xer
        assert 'TT_Task' in xer
        assert 'PR_FS' in xer

    def test_xer_line_endings(self):
        tasks = {
            'A': {
                'task_name': 'Task', 'task_type': 'Task', 'duration_days': 5,
                'wbs_path': 'Root', 'constraint_type': '', 'constraint_date': '', 'row': 1,
            },
        }
        rels = []
        xer = generate_xer(tasks, rels, 'Test', '2026-01-01')
        assert '\r\n' in xer

    def test_constraint_in_xer(self):
        tasks = {
            'A1000': {
                'task_name': 'Start', 'task_type': 'Milestone', 'duration_days': 0,
                'wbs_path': 'Root', 'constraint_type': 'CS_MSO',
                'constraint_date': '2026-05-20', 'row': 1,
            },
        }
        rels = []
        xer = generate_xer(tasks, rels, 'Test', '2026-05-20')
        assert 'CS_MSO' in xer
        assert '2026-05-20 08:00' in xer

    def test_no_plan_end_date(self):
        tasks = {
            'A': {
                'task_name': 'Task', 'task_type': 'Task', 'duration_days': 5,
                'wbs_path': 'Root', 'constraint_type': '', 'constraint_date': '', 'row': 1,
            },
        }
        rels = []
        xer = generate_xer(tasks, rels, 'Test', '2026-01-01')
        lines = xer.split('\r\n')
        project_f_idx = None
        for i, line in enumerate(lines):
            if line.startswith('%F\tproj_id'):
                project_f_idx = i
                break
        assert project_f_idx is not None
        f_fields = lines[project_f_idx].split('\t')
        plan_end_idx = f_fields.index('plan_end_date')
        project_r_idx = project_f_idx + 1
        r_fields = lines[project_r_idx].split('\t')
        assert r_fields[plan_end_idx] == ''

    def test_wbs_hierarchy(self):
        tasks = {
            'A': {
                'task_name': 'Task', 'task_type': 'Task', 'duration_days': 5,
                'wbs_path': 'Root.Phase1', 'constraint_type': '',
                'constraint_date': '', 'row': 1,
            },
            'B': {
                'task_name': 'Task B', 'task_type': 'Task', 'duration_days': 3,
                'wbs_path': 'Root.Phase2', 'constraint_type': '',
                'constraint_date': '', 'row': 2,
            },
        }
        rels = [('B', 'A', 'FS', 0)]
        xer = generate_xer(tasks, rels, 'Test', '2026-01-01')
        wbs_r_lines = [l for l in xer.split('\r\n')
                       if l.startswith('%R') and l.count('\t') >= 10 and 'WS_Open' in l]
        assert len(wbs_r_lines) >= 3  # Root, Phase1, Phase2

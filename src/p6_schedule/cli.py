"""CLI entry points for p6-schedule-toolkit."""
import argparse
import sys

from .csv_to_xer import convert
from .cpm_scheduler import schedule, print_schedule, print_critical_paths, print_milestone_check
from .deploy import deploy


def to_xer() -> None:
    parser = argparse.ArgumentParser(
        prog='p6-to-xer',
        description='Convert CSV construction schedule to P6-importable XER file',
    )
    parser.add_argument('csv_file', help='Input CSV file path')
    parser.add_argument('xer_file', help='Output XER file path')
    parser.add_argument('--project', '-p', default='Construction Schedule', help='Project name')
    parser.add_argument('--start', '-s', default='2026-01-01', help='Project start date (YYYY-MM-DD)')
    args = parser.parse_args()

    try:
        convert(args.csv_file, args.xer_file, args.project, args.start)
    except (ValueError, FileNotFoundError) as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


def cpm_schedule() -> None:
    parser = argparse.ArgumentParser(
        prog='p6-schedule',
        description='Run CPM scheduling on CSV (forward + backward pass)',
    )
    parser.add_argument('csv_file', help='Input CSV file path')
    parser.add_argument('--start', '-s', default='2026-01-01', help='Project start date (YYYY-MM-DD)')
    parser.add_argument('--critical', '-c', action='store_true', help='Show critical path')
    parser.add_argument('--milestones', '-m', action='store_true', help='Show milestone check')
    parser.add_argument('--all', '-a', action='store_true', help='Show everything')
    args = parser.parse_args()

    from .csv_to_xer import parse_csv, build_tasks_and_rels

    try:
        rows = parse_csv(args.csv_file)
        tasks, rels = build_tasks_and_rels(rows)
    except (ValueError, FileNotFoundError) as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    milestone_defs = {}
    for code, t in tasks.items():
        if t.get('constraint_type') == 'CS_MSO' and t.get('constraint_date'):
            from datetime import date
            milestone_defs[code] = date.fromisoformat(t['constraint_date'])

    result = schedule(tasks, rels, args.start, milestone_defs or None)

    if args.milestones or args.all:
        print_milestone_check(result)
        print()

    if args.critical or args.all:
        print_critical_paths(result)
        print()

    print_schedule(result)


def p6_deploy() -> None:
    parser = argparse.ArgumentParser(
        prog='p6-deploy',
        description='CPM validation + generate XER for P6 import',
    )
    parser.add_argument('csv_file', help='Input CSV file path')
    parser.add_argument('--project', '-p', default='Construction Schedule', help='Project name')
    parser.add_argument('--start', '-s', default='2026-01-01', help='Project start date (YYYY-MM-DD)')
    parser.add_argument('--xer', '-x', help='Output XER file path (default: auto)')
    args = parser.parse_args()

    try:
        deploy(args.csv_file, args.project, args.start, args.xer)
    except (ValueError, FileNotFoundError) as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


def read_results() -> None:
    parser = argparse.ArgumentParser(
        prog='p6-results',
        description='Read P6 schedule results from SQLite database (read-only)',
    )
    parser.add_argument('--db', '-d', default='PPMDBSQLite.db', help='P6 database path')
    parser.add_argument('--project', '-p', help='Project name (fuzzy match)')
    parser.add_argument('--critical', '-c', action='store_true', help='Show critical path only')
    parser.add_argument('--milestones', '-m', action='store_true', help='Show milestones only')
    parser.add_argument('--gantt', '-g', action='store_true', help='Show text Gantt chart')
    parser.add_argument('--rels', '-r', action='store_true', help='Show all relationships')
    parser.add_argument('--path', action='store_true', help='Show critical path analysis')
    args = parser.parse_args()

    from .read_results import (
        connect_db, list_projects, get_project, get_tasks, get_relationships,
        print_projects, print_task_table, print_gantt, print_critical_path,
        print_relationships,
    )

    try:
        conn = connect_db(args.db)
    except Exception as e:
        print(f'Cannot open database: {e}')
        print(f'Path: {args.db}')
        sys.exit(1)

    if not args.project:
        print_projects(list_projects(conn))
        conn.close()
        return

    proj = get_project(conn, args.project)
    if not proj:
        print(f'Project not found: {args.project}')
        print('Available projects:')
        print_projects(list_projects(conn))
        conn.close()
        return

    proj_id = proj['proj_id']
    print(f'Project: {proj["proj_short_name"]} (ID={proj_id})')
    print()

    tasks = get_tasks(conn, proj_id)
    db_rels = get_relationships(conn, proj_id)

    if args.critical or args.path:
        print_critical_path(tasks, db_rels)
    elif args.milestones:
        print_task_table(tasks, show_milestones_only=True)
    elif args.gantt:
        print_gantt(tasks)
    elif args.rels:
        print_relationships(db_rels)
    else:
        print_task_table(tasks)

    conn.close()

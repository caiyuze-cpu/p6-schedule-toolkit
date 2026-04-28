"""
Deploy schedule: CPM validation + XER generation for P6 import.

Usage:
    from p6_schedule.deploy import deploy
    deploy('schedule.csv', project_name='My Project', project_start='2026-01-01')
"""
import os

from .cpm_scheduler import schedule as cpm_schedule, print_schedule, print_critical_paths
from .csv_to_xer import parse_csv, build_tasks_and_rels, generate_xer


def deploy(
    csv_path: str,
    project_name: str = 'Construction Schedule',
    project_start: str = '2026-01-01',
    xer_path: str | None = None,
) -> dict:
    """
    Validate CSV, run CPM, generate XER for P6 import.

    Steps:
    1. Parse CSV and validate network
    2. Run CPM (forward + backward pass)
    3. Print schedule summary
    4. Generate XER file

    Returns dict with stats and CPM results.
    """
    from .validate import validate_network

    rows = parse_csv(csv_path)
    tasks, rels = build_tasks_and_rels(rows)
    print(f'Parsed: {len(tasks)} tasks, {len(rels)} relationships')
    validate_network(tasks, rels)

    result = cpm_schedule(tasks, rels, project_start)
    print()
    print_schedule(result)
    print()
    print_critical_paths(result)

    if not xer_path:
        base = os.path.splitext(csv_path)[0]
        xer_path = f'{base}_{project_start}.xer'

    xer = generate_xer(tasks, rels, project_name, project_start)
    # Replace long project name with short WBS root name in XER
    wbs_root = list(tasks.values())[0]['wbs_path'].split('.')[0]
    xer = xer.replace(f'\t{project_name}\t', f'\t{wbs_root}\t')
    with open(xer_path, 'w', encoding='utf-8') as f:
        f.write(xer)

    print(f'\nXER generated: {xer_path} ({len(xer)} bytes)')
    print(f'Next: P6 → File → Import → select XER → F9 to schedule')

    return {
        'tasks': len(tasks),
        'rels': len(rels),
        'xer_path': xer_path,
        'project_end': result['project_end'],
        'result': result,
    }
